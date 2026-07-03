# Decision Log: FinAPI

This document logs significant architectural and engineering decisions made during
development.  Each entry records the context, the option chosen, and the key
trade-offs accepted.

---

## 1. CircuitBreaker thread-safety — `threading.RLock`

- **Date**: 2026-07-03
- **Status**: Implemented
- **Context**: `CircuitBreaker` docstring claimed thread-safety but `_failure_count`,
  `_state`, and `_last_state_change` were plain instance variables with no
  synchronisation. Concurrent `record_failure()` calls could lose increments via a
  non-atomic read-modify-write; concurrent `state` reads could race through the
  OPEN → HALF_OPEN transition.
- **Decision**: Protect all mutable state with a single `threading.RLock`.
  `RLock` (reentrant) rather than `Lock` was chosen because `allow_request()` calls
  `self.state`, which itself acquires the lock — a plain `Lock` would deadlock on
  same-thread re-entry.
- **Consequences**:
  - All three race conditions (lost increment, double state transition, partial
    reset) are eliminated.
  - Minor lock contention overhead is negligible relative to the network I/O the
    circuit breaker wraps.

---

## 2. Async providers — `asyncio.to_thread` + `asyncio.sleep`

- **Date**: 2026-07-03
- **Status**: Implemented
- **Context**: `YFinanceProvider` and `EodhdProvider` called `time.sleep()` inside
  synchronous `fetch_snapshot` methods.  FastAPI's async route was suspended while
  the sleep held the event loop (or a threadpool slot), blocking all other in-flight
  requests during retry back-off.
- **Decision**: Make `BaseMarketDataProvider.fetch_snapshot` an `async def` throughout.
  Blocking third-party SDK calls (`yf.Ticker`, `APIClient.get_live_stock_prices`) are
  offloaded to `asyncio.to_thread()`; inter-retry delays use `await asyncio.sleep()`.
  The route handler in `service_b/main.py` is upgraded to `async def` and `await`s
  the provider.
- **Consequences**:
  - The event loop is never blocked — concurrent requests proceed during network I/O
    and retry delays.
  - Both SDK clients remain synchronous (no async variant exists); `asyncio.to_thread`
    is the correct bridge rather than introducing a fake async wrapper.
  - All existing tests were converted to `async def` with `pytest-asyncio` (`asyncio_mode = auto`).
    Retry tests now assert on `asyncio.sleep` being awaited, not `time.sleep` being called.

---

## 3. Persistent `httpx.Client` singleton

- **Date**: 2026-07-03
- **Status**: Implemented
- **Context**: `ServiceBClient` and `ServiceCClient` in service_a, and `ServiceBClient`
  in service_c, each created a new `with httpx.Client(...) as client:` inside every
  `fetch_*` call.  This paid the cost of a TCP connection establishment and full TLS
  handshake on every single request, with no connection pooling or keep-alive.
- **Decision**: Move `httpx.Client` creation to `__init__`, configured once with
  `base_url`, `headers` (auth), and `timeout`.  A `close()` method is exposed and
  called from each app's `lifespan` context manager on shutdown.
- **Consequences**:
  - Connection pooling and keep-alive are enabled automatically by `httpx`.
  - Auth header and base URL are pre-set; call-site code is simpler.
  - The lifespan teardown ensures the underlying socket pool is drained cleanly on
    `SIGTERM` rather than being garbage-collected mid-flight.
  - Tests inject a mock directly onto `_http_client` rather than patching the class
    constructor; a regression-guard test asserts the constructor is called exactly
    once regardless of how many `fetch_*` calls are made.

---

## 4. SQLite single-worker constraint — stay with Option A (document, don't fix)

- **Date**: 2026-07-03
- **Status**: Accepted constraint, documented
- **Context**: `service_b` uses SQLite for its market data cache.  SQLite's file-level
  write lock means only one OS process may write at a time.  Running with
  `--workers > 1` or multiple container replicas sharing the same database volume
  would produce intermittent `database is locked` errors under concurrent writes.
  `check_same_thread=False` only addresses intra-process thread-safety — it does not
  resolve cross-process locking.
- **Decision**: Accept the single-worker constraint.  Do not migrate to PostgreSQL or
  Redis at this time.  Document the limitation inline (in `service_b/app/main.py`)
  and in `docker-compose.yml` so operators are aware, and note PostgreSQL as the
  migration path if multi-worker deployments become necessary.
- **Consequences**:
  - Zero code or infrastructure changes required.
  - The service must always be started without `--workers N` (N > 1).
  - If traffic growth requires horizontal scaling, the migration path is a
    `DATABASE_URL` swap to PostgreSQL — the SQLModel/SQLAlchemy schema and query
    code are driver-agnostic and require no changes.

---

## 5. Health checks — deferred to backlog (TICKET-001)

- **Date**: 2026-07-03
- **Status**: Deferred — tracked in `TICKETS.md`
- **Context**: No service exposes a `/health` endpoint; `docker-compose.yml` uses
  bare `depends_on` which only waits for a container to start, not for uvicorn to be
  ready.  This produces spurious 502s at startup and provides no runtime health signal
  for load balancers or orchestrators.
- **Decision**: Do not implement now.  Record as a nice-to-have in `TICKETS.md`
  (TICKET-001).  When implemented, the recommended approach is: unauthenticated
  `GET /health` per service (with a SQLite `SELECT 1` check in service_b), Docker
  Compose `healthcheck:` blocks with a `start_period` grace window, and
  `depends_on: condition: service_healthy` on service_a.  service_a's own health
  endpoint should check process liveness only — not probe service_b — to avoid
  cascade failures.
- **Consequences**:
  - Startup race condition remains possible (mitigated in practice by the ~15 s
    SQLite + uvicorn startup window being shorter than a client retry timeout).
  - No operational regression; the system behaves exactly as before.

# Backlog Tickets

A running list of non-blocking improvements and nice-to-have tasks that have been
identified but are not required for current functionality.

---

## TICKET-001 — Add Health Check Endpoints & Docker Compose Readiness Gating

| Field        | Value                             |
|--------------|-----------------------------------|
| **Type**     | Enhancement                       |
| **Priority** | Nice-to-have                      |
| **Area**     | Observability / Infrastructure    |
| **Status**   | Open                              |

### Background

Currently no service exposes a `/health` endpoint, and `docker-compose.yml` uses
bare `depends_on` which only waits for a container to *start*, not for the uvicorn
process inside it to be ready to serve requests. As a result:

- Service A can come up and immediately attempt calls to Service B before Service B's
  event loop is accepting connections, producing spurious 502 errors at startup.
- There is no way for a load balancer, orchestrator (Docker Compose, k8s, etc.), or
  an on-call engineer to programmatically verify that a service is healthy at runtime.

### Proposed Solution

#### 1. Add a `GET /health` liveness endpoint to each service

Each service gets a lightweight endpoint that returns `HTTP 200` when the process is
alive and the event loop is responsive. The check content differs per service:

| Service   | Endpoint      | Check                                                                          |
|-----------|---------------|--------------------------------------------------------------------------------|
| service_b | `GET /health` | Execute `SELECT 1` on SQLite to confirm the DB engine is reachable             |
| service_c | `GET /health` | Process alive — no external deps checked at startup                            |
| service_a | `GET /health` | Process alive **only** — do NOT probe service_b here; doing so would create cascade failures where service_b slowness incorrectly marks service_a as unhealthy |

Example response body (all services):

```json
{ "status": "ok" }
```

#### 2. Add `healthcheck:` blocks to `docker-compose.yml`

```yaml
# service_b
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 15s   # grace period for SQLite table creation + uvicorn startup
```

The `start_period` field is important — without it Docker registers failures during
the normal startup window and restarts the container in a loop.

#### 3. Upgrade `depends_on` in service_a and service_c to `condition: service_healthy`

```yaml
# service_a — docker-compose.yml
depends_on:
  service_b:
    condition: service_healthy
  service_c:
    condition: service_healthy
```

This makes Docker Compose wait until service_b and service_c have passed their
healthcheck before starting service_a's container, replacing the current
"container started" guarantee with "container is serving traffic".

### Acceptance Criteria

- [ ] `GET /health` returns `200 {"status": "ok"}` on all three services when running normally.
- [ ] `GET /health` on service_b returns `503 Service Unavailable` if the SQLite engine cannot execute a query.
- [ ] `docker-compose up` starts services in the correct order; service_a does not
      attempt any upstream calls until service_b and service_c are confirmed healthy.
- [ ] `docker inspect <container>` shows `Status: healthy` for service_b and service_c
      within ~30 seconds of `docker-compose up`.
- [ ] Unit tests cover the `/health` route for each service (200 happy path; 503 DB-error path for service_b).

### Implementation Notes

- The `/health` endpoint **must be unauthenticated** — load balancers and Docker's
  healthcheck runner do not carry Bearer tokens. Keep it outside any auth `Depends` chain.
- If a liveness/readiness split is needed in future (e.g. Kubernetes), the convention
  is `GET /health/live` (restart signal) and `GET /health/ready` (traffic routing signal).
  A single `/health` endpoint is sufficient for the current Docker Compose deployment.
- `curl` must be available inside the container images for the `healthcheck: test` command.
  If the base image does not include it, either add `RUN apt-get install -y curl` to the
  Dockerfile, or use a Python-based fallback:
  ```
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
  ```

### References

- Docker Compose healthcheck spec: https://docs.docker.com/compose/compose-file/05-services/#healthcheck
- Analysis: conversation 2026-07-03, issue 3/3 — "No health checks anywhere"

# FinAPI: Multi-Service Market Data Backend

FinAPI is a secure, resilient, multi-service backend system built in Python using FastAPI. It exposes a client-facing REST API gateway, protects endpoint access with API Key Bearer authentication, and integrates with Yahoo Finance (`yfinance`) for market data retrieval.

The project is structured as a two-service architecture to separate concerns, enforce clean boundaries, and implement localized caching to prevent external API rate-limiting.

---

## Architecture Overview

```mermaid
graph TD
    Client[Client / Consumer] -->|REST + Bearer Client Key| ServiceA(Service A: API Gateway)
    ServiceA -->|REST + Bearer Signal Key| ServiceC(Service C: Market Signal Service)
    ServiceC -->|REST + Bearer Internal Key| ServiceB(Service B: Market Data Service)
    ServiceB -->|yfinance / external API| PublicAPI(Public Market API)
    ServiceB -->|Read/Write| CacheDB[(SQLite Cache DB)]
```

### 1. Service A — API Gateway (Port `8000`)
* **Role**: Public-facing entry point.
* **Responsibilities**:
  * Validates client Bearer API keys (`Authorization: Bearer <key>`).
  * Rejects unauthenticated requests with `HTTP 401 Unauthorized`.
  * Proxies authorized signal requests to Service C, or raw market data requests to Service B.
  * Ensures external clients have no direct visibility or access to upstream API engines or database layers.

### 2. Service C — Market Signal Service (Port `8002`)
* **Role**: Rule-based calculation service.
* **Responsibilities**:
  * Protects internal endpoints with a separate signal Bearer token.
  * Queries Service B over internal REST to obtain normalized market snapshot.
  * Derives a simple sentiment signal (`bullish` / `neutral` / `bearish`) based on daily percentage price changes.
  * Outputs clear labeling marking it as a rule-based indicator, not financial advice.

### 3. Service B — Market Data Service (Port `8001`)
* **Role**: Internal integration layer.
* **Responsibilities**:
  * Protects internal endpoints with a separate internal Bearer token.
  * Interacts with `yfinance` to fetch real-time stock or crypto details.
  * Normalizes the external payloads into a stable, internal `MarketSnapshot` DTO with `previous_close` field.
  * Caches responses in a local SQLite database with a configurable Time-to-Live (TTL) to limit external API pressure and minimize response latency.
  * Employs timeout and retry resilience for upstream HTTP requests.

---

## Technical Stack
- **Framework**: FastAPI (Python 3.12)
- **Data Modeling / ORM**: Pydantic v2 & SQLModel (SQLAlchemy)
- **Market Integration**: `yfinance`
- **Dependency Manager**: `uv`
- **Containerization**: Docker & Docker Compose

---

## Setup & Running

### 1. Configure Environment Variables
Copy the template configuration and customize if needed:
```bash
cp .env.example .env
```
Default keys are pre-configured:
* `CLIENT_API_KEY=test_client_key` (used by clients to call Service A)
* `INTERNAL_API_KEY=test_internal_key` (used by Service A to call Service B)
* `CACHE_TTL_SECONDS=300` (5-minute cache expiration)

---

### Option A: Run via Docker Compose (Recommended)
You can run both services together using Docker Compose:
```bash
docker compose up --build
```
* **Service A (Gateway)** is exposed publicly at: `http://localhost:8000`
* **Service B (Internal)** is exposed internally/locally at: `http://localhost:8001`
* The cache database is persisted under a volume named `cache_data`.

---

### Option B: Run Locally with `uv`
If you prefer running the services directly in your local environment:

1. **Install Dependencies**:
   Ensure `uv` is installed, then run:
   ```bash
   uv venv
   uv pip install -r requirements.txt
   ```

2. **Start Service B (Market Data)**:
   ```bash
   # In Windows PowerShell:
   $env:PORT="8001"
   $env:INTERNAL_API_KEY="test_internal_key"
   $env:DATABASE_URL="sqlite:///market_cache.db"
   uv run uvicorn service_b.app.main:app --port 8001
   ```

3. **Start Service C (Market Signal)**:
   ```bash
   # In Windows PowerShell:
   $env:PORT="8002"
   $env:SIGNAL_API_KEY="test_signal_key"
   $env:INTERNAL_API_KEY="test_internal_key"
   $env:SERVICE_B_URL="http://localhost:8001"
   uv run uvicorn service_c.app.main:app --port 8002
   ```

4. **Start Service A (Gateway)**:
   ```bash
   # In Windows PowerShell:
   $env:PORT="8000"
   $env:CLIENT_API_KEY="test_client_key"
   $env:SIGNAL_API_KEY="test_signal_key"
   $env:SERVICE_C_URL="http://localhost:8002"
   uv run uvicorn service_a.app.main:app --port 8000
   ```
---

### 3. Managing the Services

#### Restarting & Rebuilding

* **If running via Docker Compose**:
  * **Quick Restart** (restarts the containers without rebuilding):
    ```bash
    docker compose restart
    ```
  * **Rebuild & Restart** (required if source code or dependency configuration changes):
    ```bash
    docker compose up --build -d
    ```
* **If running locally with `uv`**:
  * Stop the running processes using `Ctrl+C` in their respective terminal windows.
  * Start them again using the run commands:
    ```bash
    uv run uvicorn service_b.app.main:app --port 8001
    uv run uvicorn service_a.app.main:app --port 8000
    ```
  * If dependencies in [requirements.txt](file:///d:/gits/finapi/requirements.txt) have changed, re-install them first:
    ```bash
    uv pip install -r requirements.txt
    ```

#### Shutdown & Freeing Ports

* **If running via Docker Compose**:
  * **Stop services** (keeps containers and persists the cache data volume):
    ```bash
    docker compose stop
    ```
  * **Stop and remove containers** (fully frees up ports `8000` and `8001`):
    ```bash
    docker compose down
    ```
  * **Remove cached data volume** (warning: deletes all cached data):
    ```bash
    docker compose down -v
    ```
* **If running locally with `uv`**:
  * Press `Ctrl+C` in the active terminal windows.
  * If a process is hung or running in the background and you need to force-free ports `8000` or `8001` on Windows:
    ```powershell
    # Find processes using the ports
    Get-NetTCPConnection -LocalPort 8000, 8001 -ErrorAction SilentlyContinue | Select-Object OwningProcess -Unique

    # Kill a specific process by PID
    Stop-Process -Id <PID> -Force
    ```

#### When is a Restart/Rebuild Needed?

| Scenario | Local (`uv`) Action | Docker Compose Action |
| :--- | :--- | :--- |
| **API Key or configuration changes** (modifying [.env](file:///d:/gits/finapi/.env) or environment variables) | Update environment variables in the terminals and restart the services. | Run `docker compose down` and `docker compose up -d` to recreate containers with the new [.env](file:///d:/gits/finapi/.env) values. |
| **Source code updates** | Restart the running Uvicorn server processes (or use `--reload` during development). | Run `docker compose up --build -d` to rebuild the Docker images with the new code. |
| **Dependency updates** (updating [requirements.txt](file:///d:/gits/finapi/requirements.txt)) | Run `uv pip install -r requirements.txt` and restart the services. | Run `docker compose up --build -d` to trigger a new container image build. |
| **Ports already in use / conflicts** | Stop any existing services or processes running on ports `8000` or `8001`. | Run `docker compose down` to release the ports. |
| **Reset/Clear Cache Database** | Delete the local [market_cache.db](file:///d:/gits/finapi/market_cache.db) file. | Run `docker compose down -v` to remove the persistent cache volume, then start up again. |

---

## Running Tests
Unit and integration tests are written using `pytest` and mock external calls to Yahoo Finance and SQLite.
Run the complete test suite:
```bash
uv run pytest
```

---

## API Request Examples

### 1. Request Market Snapshot from Gateway (Service A)
Request a normalized snapshot for Apple (`AAPL`):
```bash
curl -i -H "Authorization: Bearer test_client_key" "http://localhost:8000/api/v1/market-snapshot?symbol=AAPL"
```

**Expected Response (HTTP 200)**:
```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "price": 175.50,
  "currency": "USD",
  "high": 176.00,
  "low": 174.00,
  "open": 174.50,
  "volume": 52000000.0,
  "market_cap": 2700000000000.0,
  "previous_close": 174.00,
  "timestamp": 1700000000.0
}
```

### 2. Request Market Signal from Gateway (Service A)
Request the rule-based market signal for Apple (`AAPL`):
```bash
curl -i -H "Authorization: Bearer test_client_key" "http://localhost:8000/api/v1/market-signal?symbol=AAPL"
```

**Expected Response (HTTP 200)**:
```json
{
  "symbol": "AAPL",
  "signal": "bullish",
  "change_percent": 0.8621,
  "indicator_type": "rule-based",
  "disclaimer": "Disclaimer: This is a rule-based indicator derived from recent price changes and does not constitute financial advice. Use at your own risk.",
  "timestamp": 1700000000.0
}
```

### 3. Unauthorized Requests (Service A)
Requests without a valid Bearer token are rejected:
```bash
# Missing token
curl -i "http://localhost:8000/api/v1/market-snapshot?symbol=AAPL"

# Invalid token
curl -i -H "Authorization: Bearer wrong_key" "http://localhost:8000/api/v1/market-snapshot?symbol=AAPL"
```
**Expected Response (HTTP 401 Unauthorized)**:
```json
{
  "detail": "Unauthorized: Invalid or missing token"
}
```

### 4. Direct Request to Internal Service C (For Testing)
To query the isolated internal signal service directly:
```bash
curl -i -H "Authorization: Bearer test_signal_key" "http://localhost:8002/internal/market-signal?symbol=AAPL"
```

### 5. Direct Request to Internal Service B (For Testing)
To query the isolated internal data service directly:
```bash
curl -i -H "Authorization: Bearer test_internal_key" "http://localhost:8001/internal/market-data?symbol=BTC-USD"
```
*(Direct client access should be blocked in production environments by restricting firewall rules on ports `8001` and `8002`).*

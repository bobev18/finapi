import httpx
from service_a.app.config import settings
from service_a.app.schemas.market import MarketSnapshot

class UpstreamHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Upstream returned HTTP {status_code}: {detail}")

class ServiceBClient:
    """
    HTTP client responsible for making authorized REST calls to Service B.

    A single ``httpx.Client`` is created at construction time and reused
    across all calls, enabling TCP connection pooling and keep-alive.
    Call ``close()`` (or use the instance as a context manager) to release
    the underlying connection pool when the application shuts down.
    """
    def __init__(self, service_b_url: str, internal_key: str, timeout: float = 5.0):
        self._service_b_url = service_b_url
        # Build a persistent client once so every request reuses the same
        # connection pool instead of paying for a new TCP + TLS handshake.
        self._http_client = httpx.Client(
            base_url=service_b_url,
            headers={"Authorization": f"Bearer {internal_key}"},
            timeout=timeout,
        )

    def fetch_market_data(self, symbol: str) -> MarketSnapshot:
        """
        Queries Service B for the market snapshot of a given symbol.
        Reuses the persistent HTTP connection pool held on this instance.
        Propagates custom exceptions on HTTP or communication failures.
        """
        try:
            response = self._http_client.get(
                "/internal/market-data",
                params={"symbol": symbol},
            )
            if response.status_code == 200:
                return MarketSnapshot.model_validate(response.json())
            else:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                raise UpstreamHTTPException(status_code=response.status_code, detail=detail)
        except httpx.RequestError as e:
            raise Exception(f"Failed to communicate with Service B: {str(e)}")

    def close(self) -> None:
        """Release the underlying connection pool.  Call from the app lifespan."""
        self._http_client.close()

service_b_client = ServiceBClient(
    service_b_url=settings.service_b_url,
    internal_key=settings.internal_api_key
)

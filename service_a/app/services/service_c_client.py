import httpx
from service_a.app.config import settings

class UpstreamHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Upstream returned HTTP {status_code}: {detail}")

class ServiceCClient:
    """
    HTTP client responsible for making authorized REST calls to Service C
    (Market Signal Service).

    A single ``httpx.Client`` is created at construction time and reused
    across all calls, enabling TCP connection pooling and keep-alive.
    Call ``close()`` (or use the instance as a context manager) to release
    the underlying connection pool when the application shuts down.
    """
    def __init__(self, service_c_url: str, signal_key: str, timeout: float = 5.0):
        self._service_c_url = service_c_url
        # Build a persistent client once so every request reuses the same
        # connection pool instead of paying for a new TCP + TLS handshake.
        self._http_client = httpx.Client(
            base_url=service_c_url,
            headers={"Authorization": f"Bearer {signal_key}"},
            timeout=timeout,
        )

    def fetch_market_signal(self, symbol: str) -> dict:
        """
        Queries Service C for the rule-based market signal of a given symbol.
        Reuses the persistent HTTP connection pool held on this instance.
        Propagates custom exceptions on HTTP or communication failures.
        """
        try:
            response = self._http_client.get(
                "/internal/market-signal",
                params={"symbol": symbol},
            )
            if response.status_code == 200:
                return response.json()
            else:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                raise UpstreamHTTPException(status_code=response.status_code, detail=detail)
        except httpx.RequestError as e:
            raise Exception(f"Failed to communicate with Service C: {str(e)}")

    def close(self) -> None:
        """Release the underlying connection pool.  Call from the app lifespan."""
        self._http_client.close()

service_c_client = ServiceCClient(
    service_c_url=settings.service_c_url,
    signal_key=settings.signal_api_key
)

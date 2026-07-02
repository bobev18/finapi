import httpx
from service_a.app.config import settings

class ServiceCClient:
    """
    HTTP client responsible for making authorized REST calls to Service C (Market Signal Service).
    """
    def __init__(self, service_c_url: str, signal_key: str):
        self._service_c_url = service_c_url
        self._signal_key = signal_key

    def fetch_market_signal(self, symbol: str) -> dict:
        """
        Queries Service C for the rule-based market signal of a given symbol.
        Propagates custom exceptions on HTTP or communication failures.
        """
        url = f"{self._service_c_url}/internal/market-signal"
        headers = {"Authorization": f"Bearer {self._signal_key}"}
        params = {"symbol": symbol}
        
        try:
            # Establish client connection with a 5-second timeout
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    try:
                        detail = response.json().get("detail", response.text)
                    except Exception:
                        detail = response.text
                    raise Exception(f"Service C returned HTTP {response.status_code}: {detail}")
        except httpx.RequestError as e:
            raise Exception(f"Failed to communicate with Service C: {str(e)}")

service_c_client = ServiceCClient(
    service_c_url=settings.service_c_url,
    signal_key=settings.signal_api_key
)

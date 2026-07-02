import httpx
from service_a.app.config import settings

class ServiceBClient:
    """
    HTTP client responsible for making authorized REST calls to Service B.
    """
    def __init__(self, service_b_url: str, internal_key: str):
        self._service_b_url = service_b_url
        self._internal_key = internal_key

    def fetch_market_data(self, symbol: str) -> dict:
        """
        Queries Service B for the market snapshot of a given symbol.
        Propagates custom exceptions on HTTP or communication failures.
        """
        url = f"{self._service_b_url}/internal/market-data"
        headers = {"Authorization": f"Bearer {self._internal_key}"}
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
                    raise Exception(f"Service B returned HTTP {response.status_code}: {detail}")
        except httpx.RequestError as e:
            raise Exception(f"Failed to communicate with Service B: {str(e)}")

service_b_client = ServiceBClient(
    service_b_url=settings.service_b_url,
    internal_key=settings.internal_api_key
)

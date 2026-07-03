import pytest
import httpx
from unittest.mock import MagicMock, patch
from service_c.app.services.service_b_client import ServiceBClient, UpstreamHTTPException
from service_c.app.schemas.market import MarketSnapshot


def _make_client(mock_http: MagicMock) -> ServiceBClient:
    """Construct a ServiceBClient with a pre-injected mock HTTP client."""
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    client._http_client = mock_http
    return client


def test_service_b_client_constructed_once():
    """
    Regression guard: the httpx.Client must be instantiated exactly once at
    construction time, not once per ``fetch_market_data`` call.
    """
    with patch("service_c.app.services.service_b_client.httpx.Client") as mock_cls:
        mock_cls.return_value = MagicMock()
        client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="k")
        mock_cls.assert_called_once()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "symbol": "AAPL", "name": "Apple", "price": 1.0,
            "currency": "USD", "timestamp": 0.0
        }
        client._http_client.get.return_value = mock_response

        client.fetch_market_data("AAPL")
        client.fetch_market_data("MSFT")

        assert mock_cls.call_count == 1, (
            "httpx.Client was re-instantiated on every call — connection pooling is broken"
        )


def test_service_b_client_success():
    mock_http = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 150.0,
        "currency": "USD",
        "timestamp": 1693941000.0
    }
    mock_http.get.return_value = mock_response

    client = _make_client(mock_http)
    result = client.fetch_market_data("AAPL")

    assert isinstance(result, MarketSnapshot)
    assert result.symbol == "AAPL"
    assert result.price == 150.0
    mock_http.get.assert_called_once_with(
        "/internal/market-data",
        params={"symbol": "AAPL"},
    )


def test_service_b_client_http_error_json():
    mock_http = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"detail": "Symbol not found"}
    mock_http.get.return_value = mock_response

    client = _make_client(mock_http)

    with pytest.raises(UpstreamHTTPException) as exc_info:
        client.fetch_market_data("INVALID")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Symbol not found"


def test_service_b_client_http_error_text():
    mock_http = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = Exception("No JSON")
    mock_response.text = "Internal Server Error"
    mock_http.get.return_value = mock_response

    client = _make_client(mock_http)

    with pytest.raises(UpstreamHTTPException) as exc_info:
        client.fetch_market_data("AAPL")

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal Server Error"


def test_service_b_client_connection_error():
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.RequestError("Connection failed")

    client = _make_client(mock_http)

    with pytest.raises(Exception) as exc_info:
        client.fetch_market_data("AAPL")

    assert "Failed to communicate with Service B" in str(exc_info.value)

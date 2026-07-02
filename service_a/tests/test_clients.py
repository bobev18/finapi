import pytest
import httpx
from unittest.mock import MagicMock, patch
from service_a.app.services.service_b_client import ServiceBClient, UpstreamHTTPException as UpstreamHTTPExceptionB
from service_a.app.services.service_c_client import ServiceCClient, UpstreamHTTPException as UpstreamHTTPExceptionC
from service_a.app.schemas.market import MarketSnapshot

@patch("service_a.app.services.service_b_client.httpx.Client")
def test_service_b_client_success(mock_client_class):
    # Setup mock client and response
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 150.0,
        "currency": "USD",
        "timestamp": 1693941000.0
    }
    mock_client.get.return_value = mock_response
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    result = client.fetch_market_data("AAPL")
    
    assert isinstance(result, MarketSnapshot)
    assert result.symbol == "AAPL"
    assert result.price == 150.0
    mock_client.get.assert_called_once_with(
        "http://localhost:8001/internal/market-data",
        headers={"Authorization": "Bearer test_key"},
        params={"symbol": "AAPL"}
    )

@patch("service_a.app.services.service_b_client.httpx.Client")
def test_service_b_client_http_error_json(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"detail": "Symbol not found"}
    mock_client.get.return_value = mock_response
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    
    with pytest.raises(UpstreamHTTPExceptionB) as exc_info:
        client.fetch_market_data("INVALID")
        
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Symbol not found"

@patch("service_a.app.services.service_b_client.httpx.Client")
def test_service_b_client_http_error_text(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = Exception("No JSON")
    mock_response.text = "Internal Server Error"
    mock_client.get.return_value = mock_response
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    
    with pytest.raises(UpstreamHTTPExceptionB) as exc_info:
        client.fetch_market_data("AAPL")
        
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal Server Error"

@patch("service_a.app.services.service_b_client.httpx.Client")
def test_service_b_client_connection_error(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = httpx.RequestError("Connection failed")
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    
    with pytest.raises(Exception) as exc_info:
        client.fetch_market_data("AAPL")
        
    assert "Failed to communicate with Service B" in str(exc_info.value)


@patch("service_a.app.services.service_c_client.httpx.Client")
def test_service_c_client_success(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"symbol": "AAPL", "signal": "bullish"}
    mock_client.get.return_value = mock_response
    
    client = ServiceCClient(service_c_url="http://localhost:8002", signal_key="test_key")
    result = client.fetch_market_signal("AAPL")
    
    assert result == {"symbol": "AAPL", "signal": "bullish"}
    mock_client.get.assert_called_once_with(
        "http://localhost:8002/internal/market-signal",
        headers={"Authorization": "Bearer test_key"},
        params={"symbol": "AAPL"}
    )

@patch("service_a.app.services.service_c_client.httpx.Client")
def test_service_c_client_http_error_json(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"detail": "Signal not found"}
    mock_client.get.return_value = mock_response
    
    client = ServiceCClient(service_c_url="http://localhost:8002", signal_key="test_key")
    
    with pytest.raises(UpstreamHTTPExceptionC) as exc_info:
        client.fetch_market_signal("INVALID")
        
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Signal not found"

@patch("service_a.app.services.service_c_client.httpx.Client")
def test_service_c_client_http_error_text(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = Exception("No JSON")
    mock_response.text = "Internal Server Error"
    mock_client.get.return_value = mock_response
    
    client = ServiceCClient(service_c_url="http://localhost:8002", signal_key="test_key")
    
    with pytest.raises(UpstreamHTTPExceptionC) as exc_info:
        client.fetch_market_signal("AAPL")
        
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal Server Error"

@patch("service_a.app.services.service_c_client.httpx.Client")
def test_service_c_client_connection_error(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = httpx.RequestError("Connection failed")
    
    client = ServiceCClient(service_c_url="http://localhost:8002", signal_key="test_key")
    
    with pytest.raises(Exception) as exc_info:
        client.fetch_market_signal("AAPL")
        
    assert "Failed to communicate with Service C" in str(exc_info.value)

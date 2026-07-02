import pytest
import httpx
from unittest.mock import MagicMock, patch
from service_c.app.services.service_b_client import ServiceBClient, UpstreamHTTPException

@patch("service_c.app.services.service_b_client.httpx.Client")
def test_service_b_client_success(mock_client_class):
    # Setup mock client and response
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"symbol": "AAPL", "price": 150.0}
    mock_client.get.return_value = mock_response
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    result = client.fetch_market_data("AAPL")
    
    assert result == {"symbol": "AAPL", "price": 150.0}
    mock_client.get.assert_called_once_with(
        "http://localhost:8001/internal/market-data",
        headers={"Authorization": "Bearer test_key"},
        params={"symbol": "AAPL"}
    )

@patch("service_c.app.services.service_b_client.httpx.Client")
def test_service_b_client_http_error_json(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"detail": "Symbol not found"}
    mock_client.get.return_value = mock_response
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    
    with pytest.raises(UpstreamHTTPException) as exc_info:
        client.fetch_market_data("INVALID")
        
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Symbol not found"

@patch("service_c.app.services.service_b_client.httpx.Client")
def test_service_b_client_http_error_text(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = Exception("No JSON")
    mock_response.text = "Internal Server Error"
    mock_client.get.return_value = mock_response
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    
    with pytest.raises(UpstreamHTTPException) as exc_info:
        client.fetch_market_data("AAPL")
        
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal Server Error"

@patch("service_c.app.services.service_b_client.httpx.Client")
def test_service_b_client_connection_error(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = httpx.RequestError("Connection failed")
    
    client = ServiceBClient(service_b_url="http://localhost:8001", internal_key="test_key")
    
    with pytest.raises(Exception) as exc_info:
        client.fetch_market_data("AAPL")
        
    assert "Failed to communicate with Service B" in str(exc_info.value)

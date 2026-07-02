import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from service_a.app.main import app
from service_a.app.config import settings

@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as test_client:
        yield test_client

def test_gateway_unauthorized(client):
    response = client.get("/api/v1/market-snapshot?symbol=AAPL")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized: Invalid or missing token"}

def test_gateway_invalid_token(client):
    response = client.get(
        "/api/v1/market-snapshot?symbol=AAPL",
        headers={"Authorization": "Bearer invalid_client_key"}
    )
    assert response.status_code == 401

def test_gateway_missing_symbol(client):
    # Verify that we validate the symbol query parameter
    response = client.get(
        "/api/v1/market-snapshot",
        headers={"Authorization": f"Bearer {settings.client_api_key}"}
    )
    assert response.status_code == 422

@patch("service_a.app.main.service_b_client")
def test_gateway_forwarding_success(mock_service_b_client, client):
    # Mock successful response from Service B client
    mock_data = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 175.50,
        "currency": "USD",
        "high": 176.00,
        "low": 174.00,
        "open": 174.50,
        "volume": 52000000.0,
        "market_cap": 2700000000000.0,
        "timestamp": 1700000000.0
    }
    mock_service_b_client.fetch_market_data.return_value = mock_data
    
    response = client.get(
        "/api/v1/market-snapshot?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.client_api_key}"}
    )
    
    assert response.status_code == 200
    assert response.json() == mock_data
    mock_service_b_client.fetch_market_data.assert_called_once_with("AAPL")

@patch("service_a.app.main.service_b_client")
def test_gateway_forwarding_failure(mock_service_b_client, client):
    # Mock failure when contacting Service B
    mock_service_b_client.fetch_market_data.side_effect = Exception("Service B connection failed")
    
    response = client.get(
        "/api/v1/market-snapshot?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.client_api_key}"}
    )
    
    assert response.status_code == 502
    assert response.json()["detail"] == "Gateway routing error: unavailable downstream service"

def test_gateway_signal_unauthorized(client):
    response = client.get("/api/v1/market-signal?symbol=AAPL")
    assert response.status_code == 401

@patch("service_a.app.main.service_c_client")
def test_gateway_signal_success(mock_service_c_client, client):
    mock_signal_data = {
        "symbol": "AAPL",
        "signal": "bullish",
        "change_percent": 3.0,
        "indicator_type": "rule-based",
        "disclaimer": "Disclaimer info",
        "timestamp": 1700000000.0
    }
    mock_service_c_client.fetch_market_signal.return_value = mock_signal_data
    
    response = client.get(
        "/api/v1/market-signal?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.client_api_key}"}
    )
    
    assert response.status_code == 200
    assert response.json() == mock_signal_data
    mock_service_c_client.fetch_market_signal.assert_called_once_with("AAPL")

@patch("service_a.app.main.service_c_client")
def test_gateway_signal_failure(mock_service_c_client, client):
    mock_service_c_client.fetch_market_signal.side_effect = Exception("Service C connection failed")
    
    response = client.get(
        "/api/v1/market-signal?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.client_api_key}"}
    )
    
    assert response.status_code == 502
    assert response.json()["detail"] == "Gateway routing error: unavailable downstream service"

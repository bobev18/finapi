import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from service_c.app.main import app
from service_c.app.config import settings

@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as test_client:
        yield test_client

def test_signal_endpoint_unauthorized(client):
    response = client.get("/internal/market-signal?symbol=AAPL")
    assert response.status_code == 401

def test_signal_endpoint_invalid_token(client):
    response = client.get(
        "/internal/market-signal?symbol=AAPL",
        headers={"Authorization": "Bearer invalid_signal_key"}
    )
    assert response.status_code == 401

@patch("service_c.app.main.service_b_client")
def test_signal_bullish_via_previous_close(mock_service_b_client, client):
    # Mock Service B response
    mock_service_b_client.fetch_market_data.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 103.0,
        "currency": "USD",
        "open": 100.0,
        "previous_close": 100.0,
        "timestamp": 1700000000.0
    }
    
    response = client.get(
        "/internal/market-signal?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.signal_api_key}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["signal"] == "bullish"
    assert data["change_percent"] == 3.0
    assert "disclaimer" in data
    assert data["indicator_type"] == "rule-based"

@patch("service_c.app.main.service_b_client")
def test_signal_bearish_via_previous_close(mock_service_b_client, client):
    mock_service_b_client.fetch_market_data.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 97.0,
        "currency": "USD",
        "open": 100.0,
        "previous_close": 100.0,
        "timestamp": 1700000000.0
    }
    
    response = client.get(
        "/internal/market-signal?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.signal_api_key}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] == "bearish"
    assert data["change_percent"] == -3.0

@patch("service_c.app.main.service_b_client")
def test_signal_neutral_via_previous_close(mock_service_b_client, client):
    mock_service_b_client.fetch_market_data.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 101.5,
        "currency": "USD",
        "open": 100.0,
        "previous_close": 100.0,
        "timestamp": 1700000000.0
    }
    
    response = client.get(
        "/internal/market-signal?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.signal_api_key}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] == "neutral"
    assert data["change_percent"] == 1.5

@patch("service_c.app.main.service_b_client")
def test_signal_fallback_to_open(mock_service_b_client, client):
    # previous_close is None, so it should use open
    mock_service_b_client.fetch_market_data.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 105.0,
        "currency": "USD",
        "open": 100.0,
        "previous_close": None,
        "timestamp": 1700000000.0
    }
    
    response = client.get(
        "/internal/market-signal?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.signal_api_key}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] == "bullish"
    assert data["change_percent"] == 5.0

@patch("service_c.app.main.service_b_client")
def test_signal_fallback_both_missing(mock_service_b_client, client):
    # Both are None/0, should result in 0.0 change and neutral signal
    mock_service_b_client.fetch_market_data.return_value = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 100.0,
        "currency": "USD",
        "open": None,
        "previous_close": None,
        "timestamp": 1700000000.0
    }
    
    response = client.get(
        "/internal/market-signal?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.signal_api_key}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] == "neutral"
    assert data["change_percent"] == 0.0


@patch("service_c.app.main.service_b_client")
def test_signal_endpoint_forward_404(mock_service_b_client, client):
    from service_c.app.services.service_b_client import UpstreamHTTPException
    mock_service_b_client.fetch_market_data.side_effect = UpstreamHTTPException(
        status_code=404, detail="Symbol not found at provider"
    )
    
    response = client.get(
        "/internal/market-signal?symbol=INVALID",
        headers={"Authorization": f"Bearer {settings.signal_api_key}"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Symbol not found at provider"


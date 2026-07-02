import time
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlmodel import SQLModel, create_engine, Session
from service_b.app.main import app, get_db_session
from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.market_data import UpstreamAPIError
from service_b.app.services.cache import CachedSnapshot

from sqlalchemy.pool import StaticPool

# Define test database engine
@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(db_session):
    # Override database session dependency in FastAPI
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_get_market_data_unauthorized(client):
    response = client.get("/internal/market-data?symbol=AAPL")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized: Invalid or missing token"}

def test_get_market_data_invalid_token(client):
    response = client.get(
        "/internal/market-data?symbol=AAPL",
        headers={"Authorization": "Bearer invalid_internal_token"}
    )
    assert response.status_code == 401

def test_get_market_data_missing_symbol(client):
    # We use a mock token check or override settings for the test. 
    # Let's pass the correct expected token: "test_internal_key" (configured in test settings/env)
    response = client.get(
        "/internal/market-data",
        headers={"Authorization": "Bearer test_internal_key"}
    )
    assert response.status_code == 422 # FastAPI validation error for missing query param

@patch("service_b.app.main.market_client")
def test_get_market_data_cache_hit(mock_market_client, client, db_session):
    # Populate the cache database directly
    from service_b.app.services.cache import CachedSnapshot
    
    cached_item = CachedSnapshot(
        symbol="AAPL",
        name="Apple Inc.",
        price=150.0,
        currency="USD",
        timestamp=time.time() # Valid timestamp (not expired)
    )
    db_session.add(cached_item)
    db_session.commit()
    
    response = client.get(
        "/internal/market-data?symbol=AAPL",
        headers={"Authorization": "Bearer test_internal_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["price"] == 150.0
    assert data["name"] == "Apple Inc."
    # The external market client should NOT have been called
    mock_market_client.fetch_snapshot.assert_not_called()

@patch("service_b.app.main.market_client")
def test_get_market_data_cache_miss_success(mock_market_client, client, db_session):
    # Mock external client fetch
    mock_snapshot = MarketSnapshot(
        symbol="GOOG",
        name="Alphabet Inc.",
        price=2800.0,
        currency="USD",
        timestamp=time.time()
    )
    mock_market_client.fetch_snapshot.return_value = mock_snapshot
    
    response = client.get(
        "/internal/market-data?symbol=GOOG",
        headers={"Authorization": "Bearer test_internal_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "GOOG"
    assert data["price"] == 2800.0
    
    # External client should have been called
    mock_market_client.fetch_snapshot.assert_called_once_with("GOOG")
    
    # The cache should now contain this item
    from service_b.app.services.cache import CachedSnapshot
    cached = db_session.get(CachedSnapshot, "GOOG")
    assert cached is not None
    assert cached.price == 2800.0

@patch("service_b.app.main.market_client")
def test_get_market_data_upstream_failure(mock_market_client, client):
    # Mock external client to raise an error
    mock_market_client.fetch_snapshot.side_effect = UpstreamAPIError("Upstream service unavailable")
    
    response = client.get(
        "/internal/market-data?symbol=MSFT",
        headers={"Authorization": "Bearer test_internal_key"}
    )
    
    assert response.status_code == 502
    assert "Upstream service unavailable" in response.json()["detail"]

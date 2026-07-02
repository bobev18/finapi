import time
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlmodel import SQLModel, create_engine, Session, select
from service_b.app.main import app, get_db_session
from service_b.app.config import settings
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
    # Let's pass the correct expected token
    response = client.get(
        "/internal/market-data",
        headers={"Authorization": f"Bearer {settings.internal_api_key}"}
    )
    assert response.status_code == 422 # FastAPI validation error for missing query param

@patch("service_b.app.main.market_client")
def test_get_market_data_cache_hit(mock_market_client, client, db_session):
    # Populate the cache database directly
    from service_b.app.services.cache import CachedSnapshot
    
    cached_item = CachedSnapshot(
        symbol="AAPL",
        provider="yfinance",
        name="Apple Inc.",
        price=150.0,
        currency="USD",
        timestamp=time.time() # Valid timestamp (not expired)
    )
    db_session.add(cached_item)
    db_session.commit()
    
    response = client.get(
        "/internal/market-data?symbol=AAPL",
        headers={"Authorization": f"Bearer {settings.internal_api_key}"}
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
        headers={"Authorization": f"Bearer {settings.internal_api_key}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "GOOG"
    assert data["price"] == 2800.0
    
    # External client should have been called
    mock_market_client.fetch_snapshot.assert_called_once_with("GOOG")
    
    # The cache should now contain this item
    from service_b.app.services.cache import CachedSnapshot
    statement = select(CachedSnapshot).where(CachedSnapshot.symbol == "GOOG")
    cached = db_session.exec(statement).first()
    assert cached is not None
    assert cached.price == 2800.0

@patch("service_b.app.main.market_client")
def test_get_market_data_upstream_failure(mock_market_client, client):
    # Mock external client to raise an error
    mock_market_client.fetch_snapshot.side_effect = UpstreamAPIError("Upstream service unavailable")
    
    response = client.get(
        "/internal/market-data?symbol=MSFT",
        headers={"Authorization": f"Bearer {settings.internal_api_key}"}
    )
    
    assert response.status_code == 502
    assert "Upstream service unavailable" in response.json()["detail"]


@patch("service_b.app.main.market_client")
def test_get_market_data_symbol_not_found(mock_market_client, client):
    mock_market_client.fetch_snapshot.side_effect = UpstreamAPIError("Could not find price in raw ticker info")
    
    response = client.get(
        "/internal/market-data?symbol=INVALID",
        headers={"Authorization": f"Bearer {settings.internal_api_key}"}
    )
    
    assert response.status_code == 404
    assert "Symbol not found at provider" in response.json()["detail"]



def test_get_market_provider_resolution():
    from service_b.app.main import get_market_provider
    from service_b.app.services.market_data import YFinanceProvider, EodhdProvider, FallbackProvider
    
    # Test case 1: yfinance only
    with patch("service_b.app.main.settings") as mock_settings:
        mock_settings.primary_provider = "yfinance"
        mock_settings.fallback_provider = "none"
        provider = get_market_provider()
        assert isinstance(provider, YFinanceProvider)
        
    # Test case 2: eodhd only (with key)
    with patch("service_b.app.main.settings") as mock_settings:
        mock_settings.primary_provider = "eodhd"
        mock_settings.fallback_provider = "none"
        mock_settings.eodhd_api_key = "demo"
        provider = get_market_provider()
        assert isinstance(provider, EodhdProvider)
        
    # Test case 3: eodhd only (missing key)
    with patch("service_b.app.main.settings") as mock_settings:
        mock_settings.primary_provider = "eodhd"
        mock_settings.fallback_provider = "none"
        mock_settings.eodhd_api_key = None
        with pytest.raises(ValueError, match="eodhd_api_key must be set when eodhd is used as a provider"):
            get_market_provider()
            
    # Test case 4: fallback setup
    with patch("service_b.app.main.settings") as mock_settings:
        mock_settings.primary_provider = "eodhd"
        mock_settings.fallback_provider = "yfinance"
        mock_settings.eodhd_api_key = "demo"
        provider = get_market_provider()
        assert isinstance(provider, FallbackProvider)
        assert isinstance(provider._primary, EodhdProvider)
        assert isinstance(provider._fallback, YFinanceProvider)


@patch("service_b.app.main.market_client")
def test_get_market_data_fallback_cache_hit(mock_market_client, client, db_session):
    from service_b.app.services.cache import CachedSnapshot
    
    # 1. Populate fallback cache directly
    cached_item = CachedSnapshot(
        symbol="AAPL",
        provider="eodhd",
        name="Apple Inc. Eodhd Cache",
        price=152.0,
        currency="USD",
        timestamp=time.time()
    )
    db_session.add(cached_item)
    db_session.commit()
    
    # 2. Mock settings to have fallback configured
    with patch("service_b.app.main.settings") as mock_settings:
        mock_settings.primary_provider = "yfinance"
        mock_settings.fallback_provider = "eodhd"
        mock_settings.internal_api_key = settings.internal_api_key
        mock_settings.cache_ttl_seconds = 300
        
        response = client.get(
            "/internal/market-data?symbol=AAPL",
            headers={"Authorization": f"Bearer {settings.internal_api_key}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["price"] == 152.0
        assert data["name"] == "Apple Inc. Eodhd Cache"
        assert data["provider"] == "eodhd"
        
        # Verify that market client was NOT queried (it was a fallback cache hit)
        mock_market_client.fetch_snapshot.assert_not_called()


def test_get_db_session_yield():
    from service_b.app.main import get_db_session
    from sqlmodel import Session, create_engine
    
    test_engine = create_engine("sqlite:///:memory:")
    with patch("service_b.app.main.engine", test_engine):
        db_gen = get_db_session()
        session = next(db_gen)
        assert isinstance(session, Session)
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_get_market_provider_invalid():
    from service_b.app.main import get_market_provider
    with patch("service_b.app.main.settings") as mock_settings:
        mock_settings.primary_provider = "invalid_provider"
        mock_settings.fallback_provider = "none"
        with pytest.raises(ValueError, match="Unknown market data provider: invalid_provider"):
            get_market_provider()



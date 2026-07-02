import time
import pytest
from sqlmodel import SQLModel, create_engine, Session
from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.cache import CacheService

@pytest.fixture(name="db_session")
def db_session_fixture():
    # Set up an in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_cache_get_miss(db_session):
    cache_service = CacheService(session=db_session, provider="yfinance", ttl_seconds=60)
    assert cache_service.get("AAPL") is None

def test_cache_set_and_get_hit(db_session):
    cache_service = CacheService(session=db_session, provider="yfinance", ttl_seconds=60)
    
    snapshot = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc.",
        price=150.0,
        currency="USD",
        high=152.0,
        low=148.0,
        open=149.0,
        volume=1000000.0,
        market_cap=2000000000.0,
        previous_close=147.50,
        timestamp=time.time()
    )
    
    cache_service.set(snapshot)
    
    cached = cache_service.get("AAPL")
    assert cached is not None
    assert cached.symbol == "AAPL"
    assert cached.price == 150.0
    assert cached.name == "Apple Inc."
    assert cached.previous_close == 147.50

def test_cache_expiration(db_session):
    # Set TTL to 2 seconds
    cache_service = CacheService(session=db_session, provider="yfinance", ttl_seconds=2)
    
    snapshot = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc.",
        price=150.0,
        currency="USD",
        timestamp=time.time() - 3  # Created 3 seconds ago, already expired
    )
    
    cache_service.set(snapshot)
    
    # Get should return None because it is expired
    assert cache_service.get("AAPL") is None

def test_cache_overwrite(db_session):
    cache_service = CacheService(session=db_session, provider="yfinance", ttl_seconds=60)
    
    snapshot1 = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc.",
        price=150.0,
        currency="USD",
        timestamp=time.time()
    )
    cache_service.set(snapshot1)
    
    snapshot2 = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc. Updated",
        price=155.0,
        currency="USD",
        timestamp=time.time()
    )
    cache_service.set(snapshot2)
    
    cached = cache_service.get("AAPL")
    assert cached is not None
    assert cached.price == 155.0
    assert cached.name == "Apple Inc. Updated"

def test_cache_provider_isolation(db_session):
    cache_yf = CacheService(session=db_session, provider="yfinance", ttl_seconds=60)
    cache_eodhd = CacheService(session=db_session, provider="eodhd", ttl_seconds=60)
    
    snapshot_yf = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc. yf",
        price=150.0,
        currency="USD",
        timestamp=time.time()
    )
    snapshot_eodhd = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc. eodhd",
        price=152.0,
        currency="USD",
        timestamp=time.time()
    )
    
    cache_yf.set(snapshot_yf)
    cache_eodhd.set(snapshot_eodhd)
    
    # Verify we get the correct data scoped by provider
    cached_yf = cache_yf.get("AAPL")
    cached_eodhd = cache_eodhd.get("AAPL")
    
    assert cached_yf is not None
    assert cached_yf.price == 150.0
    assert cached_yf.name == "Apple Inc. yf"
    
    assert cached_eodhd is not None
    assert cached_eodhd.price == 152.0
    assert cached_eodhd.name == "Apple Inc. eodhd"


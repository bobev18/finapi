import time
from typing import Optional
from sqlmodel import SQLModel, Field, Session, select
from service_b.app.schemas.market import MarketSnapshot

class CachedSnapshot(SQLModel, table=True):
    """
    SQLModel representation of a cached market snapshot in the SQLite database.
    """
    __tablename__ = "market_cache"  # type: ignore
    
    symbol: str = Field(primary_key=True)
    provider: str = Field(primary_key=True)
    name: str
    price: float
    currency: str
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    previous_close: Optional[float] = None
    timestamp: float

class CacheService:
    """
    Service layer responsible for caching market snapshots in SQLite and managing TTL expiration.
    """
    def __init__(self, session: Session, provider: str = "yfinance", ttl_seconds: int = 300):
        self._session = session
        self._provider = provider
        self._ttl_seconds = ttl_seconds

    def get(self, symbol: str, provider: Optional[str] = None) -> Optional[MarketSnapshot]:
        """
        Retrieves a cached snapshot if it exists and has not expired.
        """
        target_provider = provider or self._provider
        statement = select(CachedSnapshot).where(
            CachedSnapshot.symbol == symbol,
            CachedSnapshot.provider == target_provider
        )
        result = self._session.exec(statement).first()
        
        if not result:
            return None
            
        # Check if the cache entry has expired
        if time.time() - result.timestamp > self._ttl_seconds:
            return None
            
        return MarketSnapshot(
            symbol=result.symbol,
            name=result.name,
            price=result.price,
            currency=result.currency,
            high=result.high,
            low=result.low,
            open=result.open,
            volume=result.volume,
            market_cap=result.market_cap,
            previous_close=result.previous_close,
            timestamp=result.timestamp,
            provider=result.provider
        )

    def set(self, snapshot: MarketSnapshot, provider: Optional[str] = None) -> None:
        """
        Saves or updates a market snapshot in the cache database.
        """
        target_provider = provider or snapshot.provider or self._provider
        statement = select(CachedSnapshot).where(
            CachedSnapshot.symbol == snapshot.symbol,
            CachedSnapshot.provider == target_provider
        )
        existing = self._session.exec(statement).first()
        
        if existing:
            existing.name = snapshot.name
            existing.price = snapshot.price
            existing.currency = snapshot.currency
            existing.high = snapshot.high
            existing.low = snapshot.low
            existing.open = snapshot.open
            existing.volume = snapshot.volume
            existing.market_cap = snapshot.market_cap
            existing.previous_close = snapshot.previous_close
            existing.timestamp = snapshot.timestamp
            self._session.add(existing)
        else:
            cached = CachedSnapshot(
                symbol=snapshot.symbol,
                provider=target_provider,
                name=snapshot.name,
                price=snapshot.price,
                currency=snapshot.currency,
                high=snapshot.high,
                low=snapshot.low,
                open=snapshot.open,
                volume=snapshot.volume,
                market_cap=snapshot.market_cap,
                previous_close=snapshot.previous_close,
                timestamp=snapshot.timestamp
            )
            self._session.add(cached)
            
        self._session.commit()

import time
from typing import Optional
from sqlmodel import SQLModel, Field, Session, select
from service_b.app.schemas.market import MarketSnapshot

class CachedSnapshot(SQLModel, table=True):
    """
    SQLModel representation of a cached market snapshot in the SQLite database.
    """
    __tablename__ = "market_cache"
    
    symbol: str = Field(primary_key=True)
    name: str
    price: float
    currency: str
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    timestamp: float

class CacheService:
    """
    Service layer responsible for caching market snapshots in SQLite and managing TTL expiration.
    """
    def __init__(self, session: Session, ttl_seconds: int = 300):
        self._session = session
        self._ttl_seconds = ttl_seconds

    def get(self, symbol: str) -> Optional[MarketSnapshot]:
        """
        Retrieves a cached snapshot if it exists and has not expired.
        """
        statement = select(CachedSnapshot).where(CachedSnapshot.symbol == symbol)
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
            timestamp=result.timestamp
        )

    def set(self, snapshot: MarketSnapshot) -> None:
        """
        Saves or updates a market snapshot in the cache database.
        """
        statement = select(CachedSnapshot).where(CachedSnapshot.symbol == snapshot.symbol)
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
            existing.timestamp = snapshot.timestamp
            self._session.add(existing)
        else:
            cached = CachedSnapshot(
                symbol=snapshot.symbol,
                name=snapshot.name,
                price=snapshot.price,
                currency=snapshot.currency,
                high=snapshot.high,
                low=snapshot.low,
                open=snapshot.open,
                volume=snapshot.volume,
                market_cap=snapshot.market_cap,
                timestamp=snapshot.timestamp
            )
            self._session.add(cached)
            
        self._session.commit()

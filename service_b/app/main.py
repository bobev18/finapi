from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query, Request, HTTPException, status
from sqlmodel import Session, create_engine, SQLModel
from service_b.app.config import settings
from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.cache import CacheService
from service_b.app.services.market_data import (
    BaseMarketDataProvider,
    YFinanceProvider,
    EodhdProvider,
    FallbackProvider,
    UpstreamAPIError
)

# Create the SQLite engine
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

def get_db_session():
    """
    Dependency generator for SQLModel database sessions.
    """
    with Session(engine) as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database tables at startup
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(
    title="Service B - Market Data Service",
    description="Internal service that integrates with yfinance and caches normalized data.",
    lifespan=lifespan
)

# Initialize singletons
def get_market_provider() -> BaseMarketDataProvider:
    """
    Factory function to resolve primary and fallback market data providers based on config settings.
    """
    def instantiate_provider(provider_name: str) -> BaseMarketDataProvider:
        name = provider_name.lower()
        if name == "yfinance":
            return YFinanceProvider(retries=3, delay_seconds=1.0)
        elif name == "eodhd":
            if not settings.eodhd_api_key:
                raise ValueError("eodhd_api_key must be set when eodhd is used as a provider")
            return EodhdProvider(api_key=settings.eodhd_api_key, retries=3, delay_seconds=1.0)
        else:
            raise ValueError(f"Unknown market data provider: {provider_name}")

    primary = instantiate_provider(settings.primary_provider)
    
    if settings.fallback_provider and settings.fallback_provider.lower() != "none":
        fallback = instantiate_provider(settings.fallback_provider)
        return FallbackProvider(primary=primary, fallback=fallback)
        
    return primary

market_client = get_market_provider()

def verify_internal_token(request: Request):
    """
    Custom security dependency that validates the internal service-to-service Bearer token.
    Raises 401 Unauthorized for both missing and invalid keys.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing token"
        )
    token = auth_header.split(" ", 1)[1]
    if token != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing token"
        )

@app.get(
    "/internal/market-data",
    response_model=MarketSnapshot,
    dependencies=[Depends(verify_internal_token)]
)
def get_market_data(
    symbol: str = Query(..., min_length=1, description="Ticker symbol to query"),
    db: Session = Depends(get_db_session)
):
    """
    Fetches normalized market snapshot for the given symbol.
    Checks the local cache database first, then queries yfinance if it's a miss/expired.
    """
    cache_service = CacheService(
        db,
        provider=settings.primary_provider,
        ttl_seconds=settings.cache_ttl_seconds
    )
    
    # 1. Attempt cache lookup: try primary provider first
    cached = cache_service.get(symbol, provider=settings.primary_provider)
    if cached:
        return cached

    # Try fallback provider second
    if settings.fallback_provider and settings.fallback_provider.lower() != "none":
        cached = cache_service.get(symbol, provider=settings.fallback_provider)
        if cached:
            return cached

    # 2. Cache miss -> Fetch from external API
    try:
        snapshot = market_client.fetch_snapshot(symbol)
        # Cache under the provider that actually retrieved the data
        cache_service.set(snapshot, provider=snapshot.provider)
        return snapshot
    except UpstreamAPIError as e:
        if e.is_client_error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Symbol not found at provider"
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream API failure: {str(e)}"
        )


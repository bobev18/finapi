from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query, Request, HTTPException, status
from sqlmodel import Session, create_engine, SQLModel
from service_b.app.config import settings
from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.cache import CacheService
from service_b.app.services.market_data import MarketDataClient, UpstreamAPIError

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
market_client = MarketDataClient(retries=3, delay_seconds=1.0)

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
    cache_service = CacheService(db, ttl_seconds=settings.cache_ttl_seconds)
    
    # 1. Attempt cache lookup
    cached = cache_service.get(symbol)
    if cached:
        return cached

    # 2. Cache miss -> Fetch from external API
    try:
        snapshot = market_client.fetch_snapshot(symbol)
        cache_service.set(snapshot)
        return snapshot
    except UpstreamAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream API failure: {str(e)}"
        )

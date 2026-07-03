import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, Query, Request, HTTPException, status
from pydantic import BaseModel, Field
from service_c.app.config import settings
from service_c.app.services.service_b_client import service_b_client, UpstreamHTTPException

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Release shared HTTP connection pools on application shutdown."""
    yield
    service_b_client.close()

app = FastAPI(
    title="Service C - Market Signal Service",
    description="Internal service that derives rule-based market signals from snapshots fetched via Service B.",
    lifespan=lifespan
)

class MarketSignalResponse(BaseModel):
    """
    Response model for rule-based market signal details.
    """
    symbol: str = Field(..., description="Ticker symbol of the asset")
    signal: str = Field(..., description="Calculated rule-based signal (bullish / neutral / bearish)")
    change_percent: float = Field(..., description="Calculated percentage change used for the signal")
    indicator_type: str = Field("rule-based", description="Type of indicator")
    disclaimer: str = Field(
        "Disclaimer: This is a rule-based indicator derived from recent price changes and does not constitute financial advice. Use at your own risk.",
        description="Required disclaimer message"
    )
    timestamp: float = Field(..., description="Unix timestamp of signal calculation")

def verify_signal_token(request: Request):
    """
    Custom security dependency that validates the service-to-service Bearer token for Service C.
    Raises 401 Unauthorized for both missing and invalid keys.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing token"
        )
    token = auth_header.split(" ", 1)[1]
    if token != settings.signal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing token"
        )

@app.get(
    "/internal/market-signal",
    response_model=MarketSignalResponse,
    dependencies=[Depends(verify_signal_token)]
)
def get_market_signal(
    symbol: str = Query(..., min_length=1, description="Ticker symbol to fetch market signal for")
):
    """
    Internal endpoint that queries Service B, calculates the daily/24h percent change,
    and returns a rule-based signal (bullish / neutral / bearish).
    """
    try:
        snapshot = service_b_client.fetch_market_data(symbol)
    except UpstreamHTTPException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gateway routing error to Service B: {str(e)}"
        )
    
    price = snapshot.price
    open_price = snapshot.open
    previous_close = snapshot.previous_close
    
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid market data: price field is missing"
        )
    
    # Calculate percentage change
    change_pct = 0.0
    if previous_close is not None and previous_close != 0:
        change_pct = ((price - previous_close) / previous_close) * 100
    elif open_price is not None and open_price != 0:
        change_pct = ((price - open_price) / open_price) * 100
    
    # Simple rule-based logic:
    # 24h change > +2% -> bullish, below -2% -> bearish, in-between -> neutral
    if change_pct > 2.0:
        signal = "bullish"
    elif change_pct < -2.0:
        signal = "bearish"
    else:
        signal = "neutral"
        
    return MarketSignalResponse(
        symbol=symbol,
        signal=signal,
        change_percent=round(change_pct, 4),
        timestamp=time.time()
    )

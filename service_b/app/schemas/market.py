from typing import Optional
from pydantic import BaseModel, Field

class MarketSnapshot(BaseModel):
    """
    Normalized internal model for stock or crypto asset market data snapshot.
    """
    symbol: str = Field(..., description="Ticker symbol of the asset (e.g., AAPL, BTC-USD)")
    name: str = Field(..., description="Name of the asset or company")
    price: float = Field(..., description="Current price of the asset")
    currency: str = Field("USD", description="Currency of the asset pricing")
    high: Optional[float] = Field(None, description="24h or day high price")
    low: Optional[float] = Field(None, description="24h or day low price")
    open: Optional[float] = Field(None, description="Market open price")
    volume: Optional[float] = Field(None, description="Trading volume")
    market_cap: Optional[float] = Field(None, description="Market capitalization")
    previous_close: Optional[float] = Field(None, description="Previous close price")
    timestamp: float = Field(..., description="Unix timestamp of when the data was retrieved")

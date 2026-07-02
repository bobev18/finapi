import time
from typing import Any, Dict
from service_b.app.schemas.market import MarketSnapshot

def normalize_ticker_info(symbol: str, raw_info: Dict[str, Any]) -> MarketSnapshot:
    """
    Normalizes a raw ticker info dictionary from yfinance into a stable MarketSnapshot model.
    """
    # 1. Determine Price (essential)
    price = (
        raw_info.get("currentPrice") or
        raw_info.get("regularMarketPrice") or
        raw_info.get("lastPrice") or
        raw_info.get("price")
    )
    if price is None:
        raise ValueError("Could not find price in raw ticker info")
    
    # 2. Determine Name (fallback to symbol if not available)
    name = (
        raw_info.get("longName") or
        raw_info.get("shortName") or
        raw_info.get("name") or
        symbol
    )
    
    # 3. Determine Currency (fallback to USD)
    currency = raw_info.get("currency") or "USD"
    
    # 4. Extract other values with optional fallbacks
    high = raw_info.get("dayHigh") or raw_info.get("regularMarketDayHigh")
    low = raw_info.get("dayLow") or raw_info.get("regularMarketDayLow")
    open_val = raw_info.get("open") or raw_info.get("regularMarketOpen")
    volume = raw_info.get("volume") or raw_info.get("regularMarketVolume")
    market_cap = raw_info.get("marketCap")
    
    return MarketSnapshot(
        symbol=symbol,
        name=name,
        price=float(price),
        currency=currency,
        high=float(high) if high is not None else None,
        low=float(low) if low is not None else None,
        open=float(open_val) if open_val is not None else None,
        volume=float(volume) if volume is not None else None,
        market_cap=float(market_cap) if market_cap is not None else None,
        timestamp=time.time()
    )

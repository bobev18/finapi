import time
from typing import Any, Dict
from service_b.app.schemas.market import MarketSnapshot

def normalize_ticker_info(symbol: str, raw_info: Dict[str, Any]) -> MarketSnapshot:
    """
    Normalizes a raw ticker info dictionary from yfinance into a stable MarketSnapshot model.
    """
    # 1. Determine Price (essential)
    price = raw_info.get("currentPrice")
    if price is None:
        price = raw_info.get("regularMarketPrice")
    if price is None:
        price = raw_info.get("lastPrice")
    if price is None:
        price = raw_info.get("price")
        
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
    
    # 4. Extract other values with optional fallbacks using explicit is not None checks
    high = raw_info.get("dayHigh") if raw_info.get("dayHigh") is not None else raw_info.get("regularMarketDayHigh")
    low = raw_info.get("dayLow") if raw_info.get("dayLow") is not None else raw_info.get("regularMarketDayLow")
    open_val = raw_info.get("open") if raw_info.get("open") is not None else raw_info.get("regularMarketOpen")
    volume = raw_info.get("volume") if raw_info.get("volume") is not None else raw_info.get("regularMarketVolume")
    market_cap = raw_info.get("marketCap")
    previous_close = raw_info.get("previousClose") if raw_info.get("previousClose") is not None else raw_info.get("regularMarketPreviousClose")
    
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
        previous_close=float(previous_close) if previous_close is not None else None,
        timestamp=time.time()
    )

def normalize_eodhd_data(symbol: str, data: Dict[str, Any]) -> MarketSnapshot:
    """
    Normalizes a raw data dictionary from EODHD into a stable MarketSnapshot model.
    """
    close_price = data.get("close")
    if close_price is None:
        raise ValueError("Could not find close price in EODHD response")
    
    return MarketSnapshot(
        symbol=symbol,  # Keep the original queried symbol
        name=symbol,    # Default name to symbol as EODHD live prices has no corporate name
        price=float(close_price),
        currency="USD",
        high=float(data["high"]) if data.get("high") is not None else None,
        low=float(data["low"]) if data.get("low") is not None else None,
        open=float(data["open"]) if data.get("open") is not None else None,
        volume=float(data["volume"]) if data.get("volume") is not None else None,
        market_cap=None,
        previous_close=float(data["previousClose"]) if data.get("previousClose") is not None else None,
        timestamp=float(data["timestamp"]) if data.get("timestamp") is not None else time.time(),
        provider="eodhd"
    )

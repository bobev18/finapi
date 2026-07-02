import pytest
from pydantic import ValidationError
from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.normalizer import normalize_ticker_info

def test_normalize_stock_info_success():
    # Mock ticker.info dictionary for a stock
    mock_info = {
        "symbol": "AAPL",
        "longName": "Apple Inc.",
        "currentPrice": 175.50,
        "currency": "USD",
        "dayHigh": 176.00,
        "dayLow": 174.00,
        "open": 174.50,
        "volume": 52000000,
        "marketCap": 2700000000000,
        "previousClose": 174.00
    }
    
    snapshot = normalize_ticker_info(symbol="AAPL", raw_info=mock_info)
    
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.symbol == "AAPL"
    assert snapshot.name == "Apple Inc."
    assert snapshot.price == 175.50
    assert snapshot.currency == "USD"
    assert snapshot.high == 176.00
    assert snapshot.low == 174.00
    assert snapshot.open == 174.50
    assert snapshot.volume == 52000000
    assert snapshot.market_cap == 2700000000000
    assert snapshot.previous_close == 174.00
    assert snapshot.timestamp > 0

def test_normalize_crypto_info_success():
    # Mock ticker.info dictionary for a crypto asset
    mock_info = {
        "symbol": "BTC-USD",
        "name": "Bitcoin USD",
        "regularMarketPrice": 65000.00,
        "currency": "USD",
        "regularMarketDayHigh": 66000.00,
        "regularMarketDayLow": 64000.00,
        "regularMarketOpen": 64500.00,
        "volume": 25000000000,
        "marketCap": 1280000000000,
        "regularMarketPreviousClose": 64000.00
    }
    
    snapshot = normalize_ticker_info(symbol="BTC-USD", raw_info=mock_info)
    
    assert snapshot.symbol == "BTC-USD"
    assert snapshot.name == "Bitcoin USD"
    assert snapshot.price == 65000.00
    assert snapshot.high == 66000.00
    assert snapshot.low == 64000.00
    assert snapshot.open == 64500.00
    assert snapshot.volume == 25000000000
    assert snapshot.market_cap == 1280000000000
    assert snapshot.previous_close == 64000.00

def test_normalize_missing_essential_fields():
    # If price and common price keys are missing, it should raise a ValueError
    mock_info = {
        "symbol": "AAPL",
        "longName": "Apple Inc."
    }
    
    with pytest.raises(ValueError, match="Could not find price in raw ticker info"):
        normalize_ticker_info(symbol="AAPL", raw_info=mock_info)

def test_normalize_with_default_fallbacks():
    # Test fallback fields (e.g., name defaults to symbol, fields default to None or 0)
    mock_info = {
        "symbol": "XYZ",
        "currentPrice": 10.0
    }
    
    snapshot = normalize_ticker_info(symbol="XYZ", raw_info=mock_info)
    assert snapshot.symbol == "XYZ"
    assert snapshot.name == "XYZ"  # Fallback to symbol
    assert snapshot.price == 10.0
    assert snapshot.currency == "USD"  # Default fallback
    assert snapshot.high is None
    assert snapshot.low is None
    assert snapshot.open is None
    assert snapshot.volume is None
    assert snapshot.market_cap is None
    assert snapshot.previous_close is None

import time
import pytest
from unittest.mock import MagicMock, PropertyMock, patch
from service_b.app.services.market_data import (
    YFinanceProvider,
    EodhdProvider,
    FallbackProvider,
    UpstreamAPIError
)
from service_b.app.schemas.market import MarketSnapshot

# ==========================================
# YFinanceProvider Tests
# ==========================================

@patch("service_b.app.services.market_data.yf.Ticker")
def test_yfinance_provider_success(mock_ticker_class):
    mock_ticker = MagicMock()
    mock_ticker.info = {
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
    mock_ticker_class.return_value = mock_ticker
    
    provider = YFinanceProvider(retries=3, delay_seconds=0.01)
    snapshot = provider.fetch_snapshot("AAPL")
    
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.symbol == "AAPL"
    assert snapshot.price == 175.50
    mock_ticker_class.assert_called_once_with("AAPL")

@patch("service_b.app.services.market_data.yf.Ticker")
def test_yfinance_provider_retry_success(mock_ticker_class):
    mock_ticker = MagicMock()
    p = PropertyMock(side_effect=[
        Exception("Network connection failed"),
        {
            "symbol": "AAPL",
            "currentPrice": 175.50,
            "longName": "Apple Inc."
        }
    ])
    type(mock_ticker).info = p
    mock_ticker_class.return_value = mock_ticker
    
    provider = YFinanceProvider(retries=3, delay_seconds=0.01)
    snapshot = provider.fetch_snapshot("AAPL")
    
    assert snapshot.symbol == "AAPL"
    assert snapshot.price == 175.50
    assert p.call_count == 2

@patch("service_b.app.services.market_data.yf.Ticker")
def test_yfinance_provider_exhausted_retries(mock_ticker_class):
    mock_ticker = MagicMock()
    p = PropertyMock(side_effect=Exception("API offline"))
    type(mock_ticker).info = p
    mock_ticker_class.return_value = mock_ticker
    
    provider = YFinanceProvider(retries=3, delay_seconds=0.01)
    
    with pytest.raises(UpstreamAPIError, match="Failed to fetch market data for symbol MSFT after 3 attempts"):
        provider.fetch_snapshot("MSFT")


# ==========================================
# EodhdProvider Tests
# ==========================================

@patch("service_b.app.services.market_data.APIClient")
def test_eodhd_provider_success(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_live_stock_prices.return_value = {
        "code": "AAPL.US",
        "timestamp": 1693941000,
        "open": 174.50,
        "high": 176.00,
        "low": 174.00,
        "close": 175.50,
        "volume": 52000000,
        "previousClose": 174.00
    }
    mock_client_class.return_value = mock_client
    
    provider = EodhdProvider(api_key="fake_key", retries=3, delay_seconds=0.01)
    snapshot = provider.fetch_snapshot("AAPL")
    
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.symbol == "AAPL"
    assert snapshot.name == "AAPL"
    assert snapshot.price == 175.50
    assert snapshot.previous_close == 174.00
    mock_client.get_live_stock_prices.assert_called_once_with(ticker="AAPL.US")

@patch("service_b.app.services.market_data.APIClient")
def test_eodhd_provider_symbol_normalization(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_live_stock_prices.return_value = {
        "code": "TEST",
        "close": 10.0
    }
    mock_client_class.return_value = mock_client
    
    provider = EodhdProvider(api_key="fake_key", retries=1, delay_seconds=0.01)
    
    # 1. Standard stock ticker
    provider.fetch_snapshot("AAPL")
    mock_client.get_live_stock_prices.assert_called_with(ticker="AAPL.US")
    
    # 2. Crypto ticker
    provider.fetch_snapshot("BTC-USD")
    mock_client.get_live_stock_prices.assert_called_with(ticker="BTC-USD.CC")
    
    # 3. Pre-formatted ticker
    provider.fetch_snapshot("MSFT.US")
    mock_client.get_live_stock_prices.assert_called_with(ticker="MSFT.US")


# ==========================================
# FallbackProvider Tests
# ==========================================

def test_fallback_provider_primary_success():
    mock_primary = MagicMock()
    mock_fallback = MagicMock()
    
    mock_snapshot = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc.",
        price=175.50,
        currency="USD",
        timestamp=time.time()
    )
    mock_primary.fetch_snapshot.return_value = mock_snapshot
    
    provider = FallbackProvider(primary=mock_primary, fallback=mock_fallback)
    snapshot = provider.fetch_snapshot("AAPL")
    
    assert snapshot == mock_snapshot
    mock_primary.fetch_snapshot.assert_called_once_with("AAPL")
    mock_fallback.fetch_snapshot.assert_not_called()

def test_fallback_provider_primary_fails_fallback_success():
    mock_primary = MagicMock()
    mock_fallback = MagicMock()
    
    mock_primary.fetch_snapshot.side_effect = Exception("Primary API offline")
    mock_snapshot = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc.",
        price=175.50,
        currency="USD",
        timestamp=time.time()
    )
    mock_fallback.fetch_snapshot.return_value = mock_snapshot
    
    provider = FallbackProvider(primary=mock_primary, fallback=mock_fallback)
    snapshot = provider.fetch_snapshot("AAPL")
    
    assert snapshot == mock_snapshot
    mock_primary.fetch_snapshot.assert_called_once_with("AAPL")
    mock_fallback.fetch_snapshot.assert_called_once_with("AAPL")

def test_fallback_provider_both_fail():
    mock_primary = MagicMock()
    mock_fallback = MagicMock()
    
    mock_primary.fetch_snapshot.side_effect = Exception("Primary offline")
    mock_fallback.fetch_snapshot.side_effect = Exception("Fallback offline")
    
    provider = FallbackProvider(primary=mock_primary, fallback=mock_fallback)
    
    with pytest.raises(Exception, match="Fallback offline"):
        provider.fetch_snapshot("AAPL")

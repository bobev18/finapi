import pytest
from unittest.mock import MagicMock, PropertyMock, patch
from service_b.app.services.market_data import MarketDataClient, UpstreamAPIError
from service_b.app.schemas.market import MarketSnapshot

@patch("service_b.app.services.market_data.yf.Ticker")
def test_fetch_snapshot_success(mock_ticker_class):
    # Set up mock ticker info
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
        "marketCap": 2700000000000
    }
    mock_ticker_class.return_value = mock_ticker
    
    client = MarketDataClient(retries=3, delay_seconds=0.1)
    snapshot = client.fetch_snapshot("AAPL")
    
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.symbol == "AAPL"
    assert snapshot.price == 175.50
    mock_ticker_class.assert_called_once_with("AAPL")

@patch("service_b.app.services.market_data.yf.Ticker")
def test_fetch_snapshot_retry_success(mock_ticker_class):
    # We will use side_effect on a property mock
    mock_ticker = MagicMock()
    p = PropertyMock(side_effect=[
        Exception("Network connection failed"),
        Exception("Timeout"),
        {
            "symbol": "AAPL",
            "currentPrice": 175.50,
            "longName": "Apple Inc."
        }
    ])
    type(mock_ticker).info = p
    mock_ticker_class.return_value = mock_ticker
    
    client = MarketDataClient(retries=3, delay_seconds=0.01)
    snapshot = client.fetch_snapshot("AAPL")
    
    assert snapshot.symbol == "AAPL"
    assert snapshot.price == 175.50
    # Property was accessed 3 times
    assert p.call_count == 3

@patch("service_b.app.services.market_data.yf.Ticker")
def test_fetch_snapshot_exhausted_retries(mock_ticker_class):
    # Set up mock ticker that always fails
    mock_ticker = MagicMock()
    p = PropertyMock(side_effect=Exception("API offline"))
    type(mock_ticker).info = p
    mock_ticker_class.return_value = mock_ticker
    
    client = MarketDataClient(retries=3, delay_seconds=0.01)
    
    with pytest.raises(UpstreamAPIError, match="Failed to fetch market data for symbol MSFT after 3 attempts"):
        client.fetch_snapshot("MSFT")


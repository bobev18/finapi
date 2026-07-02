import time
import logging
from abc import ABC, abstractmethod
from typing import Optional
import yfinance as yf
from eodhd import APIClient

from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.normalizer import normalize_ticker_info

logger = logging.getLogger(__name__)

class UpstreamAPIError(Exception):
    """
    Custom exception raised when calls to the upstream public API fail.
    """
    pass

class BaseMarketDataProvider(ABC):
    """
    Abstract base class representing a market data provider.
    """
    @abstractmethod
    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        """
        Queries the provider for a symbol and returns a normalized MarketSnapshot.
        """
        pass

class YFinanceProvider(BaseMarketDataProvider):
    """
    Market data provider that queries Yahoo Finance using yfinance library.
    """
    def __init__(self, retries: int = 3, delay_seconds: float = 1.0):
        self._retries = retries
        self._delay_seconds = delay_seconds

    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        last_error = None
        for attempt in range(1, self._retries + 1):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                if not info or not isinstance(info, dict):
                    raise ValueError(f"Upstream returned empty or invalid info dict: {info}")
                
                snapshot = normalize_ticker_info(symbol, info)
                snapshot.provider = "yfinance"
                return snapshot
            except Exception as e:
                last_error = e
                logger.warning(
                    f"yfinance attempt {attempt}/{self._retries} failed for symbol {symbol}: {str(e)}"
                )
                if attempt < self._retries:
                    time.sleep(self._delay_seconds)
        
        raise UpstreamAPIError(
            f"Failed to fetch market data for symbol {symbol} after {self._retries} attempts. Last error: {str(last_error)}"
        )

class EodhdProvider(BaseMarketDataProvider):
    """
    Market data provider that queries EODHD Financial APIs.
    """
    def __init__(self, api_key: str, retries: int = 3, delay_seconds: float = 1.0):
        self._api_key = api_key
        self._client = APIClient(api_key)
        self._retries = retries
        self._delay_seconds = delay_seconds

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalizes standard symbols into EODHD exchange format:
        - If symbol contains a dot (.), assume it is already formatted (e.g. AAPL.US, BTC-USD.CC).
        - If symbol ends with -USD (e.g. BTC-USD), append .CC for crypto.
        - Otherwise, assume US stock and append .US.
        """
        if "." in symbol:
            return symbol
        if symbol.endswith("-USD"):
            return f"{symbol}.CC"
        return f"{symbol}.US"

    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        normalized = self._normalize_symbol(symbol)
        last_error = None
        for attempt in range(1, self._retries + 1):
            try:
                # EODHD python client: get_live_stock_prices returns a dict for a single symbol
                data = self._client.get_live_stock_prices(ticker=normalized)
                
                if not data or not isinstance(data, dict):
                    raise ValueError(f"EODHD returned empty or invalid data: {data}")
                
                close_price = data.get("close")
                if close_price is None:
                    raise ValueError(f"Could not find close price in EODHD response: {data}")
                
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
            except Exception as e:
                last_error = e
                logger.warning(
                    f"EODHD attempt {attempt}/{self._retries} failed for symbol {normalized}: {str(e)}"
                )
                if attempt < self._retries:
                    time.sleep(self._delay_seconds)
                    
        raise UpstreamAPIError(
            f"Failed to fetch market data from EODHD for symbol {normalized} after {self._retries} attempts. Last error: {str(last_error)}"
        )

class FallbackProvider(BaseMarketDataProvider):
    """
    Composite provider that queries a primary provider, and falls back to a secondary provider if it fails.
    """
    def __init__(self, primary: BaseMarketDataProvider, fallback: BaseMarketDataProvider):
        self._primary = primary
        self._fallback = fallback

    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        try:
            return self._primary.fetch_snapshot(symbol)
        except Exception as e:
            logger.warning(
                f"Primary provider failed to fetch symbol {symbol}: {str(e)}. "
                "Attempting fallback provider..."
            )
            return self._fallback.fetch_snapshot(symbol)

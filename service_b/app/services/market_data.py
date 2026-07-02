import time
import logging
import yfinance as yf
from typing import Any, Dict
from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.normalizer import normalize_ticker_info

logger = logging.getLogger(__name__)

class UpstreamAPIError(Exception):
    """
    Custom exception raised when calls to the upstream public API fail.
    """
    pass

class MarketDataClient:
    """
    Client for interacting with the external yfinance API with built-in retries and error handling.
    """
    def __init__(self, retries: int = 3, delay_seconds: float = 1.0):
        self._retries = retries
        self._delay_seconds = delay_seconds

    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        """
        Queries yfinance for a symbol, normalizes it, and returns a MarketSnapshot.
        Applies simple retry logic with a delay between attempts.
        """
        last_error = None
        for attempt in range(1, self._retries + 1):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                # Verify that ticker info exists and is valid
                if not info or not isinstance(info, dict):
                    raise ValueError(f"Upstream returned empty or invalid info dict: {info}")
                
                return normalize_ticker_info(symbol, info)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt}/{self._retries} failed for symbol {symbol}: {str(e)}"
                )
                if attempt < self._retries:
                    time.sleep(self._delay_seconds)
        
        raise UpstreamAPIError(
            f"Failed to fetch market data for symbol {symbol} after {self._retries} attempts. Last error: {str(last_error)}"
        )

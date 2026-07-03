import time
import logging
from abc import ABC, abstractmethod
from typing import Optional
from enum import Enum
import requests
import yfinance as yf
from eodhd import APIClient

from service_b.app.schemas.market import MarketSnapshot
from service_b.app.services.normalizer import normalize_ticker_info, normalize_eodhd_data

logger = logging.getLogger(__name__)

class UpstreamAPIError(Exception):
    """
    Custom exception raised when calls to the upstream public API fail.
    """
    def __init__(self, message: str, is_client_error: bool = False):
        super().__init__(message)
        self.is_client_error = is_client_error

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """
    A simple, thread-safe Circuit Breaker implementation for managing upstream provider states.
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_state_change = time.time()

    @property
    def state(self) -> CircuitState:
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_state_change > self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._last_state_change = time.time()
        return self._state

    def record_success(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_state_change = time.time()

    def record_failure(self):
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._last_state_change = time.time()

    def allow_request(self) -> bool:
        state = self.state
        return state == CircuitState.CLOSED or state == CircuitState.HALF_OPEN

def is_client_error(e: Exception) -> bool:
    """
    Determines if an exception is a client-side error (e.g. invalid ticker,
    bad request, or validation error) that should **not** be retried.

    Classification is based solely on exception *type* and HTTP status code —
    never on message string content, which is unreliable (e.g. a stock price
    of 404.50 must not trigger a client-error classification).

    Rules:
    - ``ValueError``: always a client error (bad input / empty upstream data).
    - ``requests.exceptions.HTTPError`` with a 4xx status code: client error,
      **except** 429 (Too Many Requests) which is a server-side throttle and
      should be retried.
    - All other exceptions: not a client error (default safe: retry).
    """
    if isinstance(e, ValueError):
        return True

    if isinstance(e, requests.exceptions.HTTPError):
        response = getattr(e, "response", None)
        if response is not None and hasattr(response, "status_code"):
            status = response.status_code
            # 4xx range = client errors, but 429 (rate-limit) should be retried
            return 400 <= status < 500 and status != 429

    return False

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
                if is_client_error(e):
                    raise UpstreamAPIError(str(e), is_client_error=True) from e
                last_error = e
                logger.warning(
                    f"yfinance attempt {attempt}/{self._retries} failed for symbol {symbol}: {str(e)}"
                )
                if attempt < self._retries:
                    time.sleep(self._delay_seconds)
        
        raise UpstreamAPIError(
            f"Failed to fetch market data for symbol {symbol} after {self._retries} attempts. Last error: {str(last_error)}",
            is_client_error=False
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
                
                snapshot = normalize_eodhd_data(symbol, data)
                return snapshot
            except Exception as e:
                if is_client_error(e):
                    raise UpstreamAPIError(str(e), is_client_error=True) from e
                last_error = e
                logger.warning(
                    f"EODHD attempt {attempt}/{self._retries} failed for symbol {normalized}: {str(e)}"
                )
                if attempt < self._retries:
                    time.sleep(self._delay_seconds)
                    
        raise UpstreamAPIError(
            f"Failed to fetch market data from EODHD for symbol {normalized} after {self._retries} attempts. Last error: {str(last_error)}",
            is_client_error=False
        )

class FallbackProvider(BaseMarketDataProvider):
    """
    Composite provider that queries a primary provider, and falls back to a secondary provider if it fails.
    """
    def __init__(
        self,
        primary: BaseMarketDataProvider,
        fallback: BaseMarketDataProvider,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0
    ):
        self._primary = primary
        self._fallback = fallback
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        if not self._circuit_breaker.allow_request():
            logger.warning(
                f"Primary provider circuit is OPEN. Bypassing primary to call fallback provider directly for {symbol}."
            )
            return self._fallback.fetch_snapshot(symbol)
            
        try:
            snapshot = self._primary.fetch_snapshot(symbol)
            self._circuit_breaker.record_success()
            return snapshot
        except UpstreamAPIError as e:
            if e.is_client_error:
                # Do not record failure on circuit breaker for client-side errors, but query fallback
                logger.info(
                    f"Primary provider returned client error for {symbol}: {str(e)}. "
                    "Querying fallback..."
                )
                try:
                    return self._fallback.fetch_snapshot(symbol)
                except Exception:
                    raise
            else:
                self._circuit_breaker.record_failure()
                logger.warning(
                    f"Primary provider failed with service error: {str(e)}. "
                    "Attempting fallback provider..."
                )
                return self._fallback.fetch_snapshot(symbol)
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.warning(
                f"Primary provider failed with unexpected error: {str(e)}. "
                "Attempting fallback provider..."
            )
            return self._fallback.fetch_snapshot(symbol)

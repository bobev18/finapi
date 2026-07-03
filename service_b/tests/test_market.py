import time
import threading
import pytest
import requests
from unittest.mock import MagicMock, PropertyMock, patch
from service_b.app.services.market_data import (
    YFinanceProvider,
    EodhdProvider,
    FallbackProvider,
    UpstreamAPIError,
    is_client_error,
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


# ==========================================
# Provider Error Cases & Retry Tests
# ==========================================

@patch("service_b.app.services.market_data.yf.Ticker")
def test_yfinance_provider_invalid_data(mock_ticker_class):
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    mock_ticker_class.return_value = mock_ticker
    
    provider = YFinanceProvider(retries=1, delay_seconds=0.01)
    with pytest.raises(UpstreamAPIError, match="Upstream returned empty or invalid info dict"):
        provider.fetch_snapshot("AAPL")


@patch("service_b.app.services.market_data.APIClient")
def test_eodhd_provider_empty_data(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_live_stock_prices.return_value = None
    mock_client_class.return_value = mock_client
    
    provider = EodhdProvider(api_key="fake_key", retries=1, delay_seconds=0.01)
    with pytest.raises(UpstreamAPIError, match="EODHD returned empty or invalid data"):
        provider.fetch_snapshot("AAPL")


@patch("service_b.app.services.market_data.APIClient")
def test_eodhd_provider_missing_close_price(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_live_stock_prices.return_value = {
        "code": "AAPL.US",
        "open": 174.50
    }
    mock_client_class.return_value = mock_client
    
    provider = EodhdProvider(api_key="fake_key", retries=1, delay_seconds=0.01)
    with pytest.raises(UpstreamAPIError, match="Could not find close price in EODHD response"):
        provider.fetch_snapshot("AAPL")


@patch("service_b.app.services.market_data.APIClient")
def test_eodhd_provider_retry_behavior(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_live_stock_prices.side_effect = [
        Exception("Timeout"),
        Exception("Timeout"),
        {
            "code": "AAPL.US",
            "close": 175.50
        }
    ]
    mock_client_class.return_value = mock_client
    
    provider = EodhdProvider(api_key="fake_key", retries=3, delay_seconds=0.01)
    snapshot = provider.fetch_snapshot("AAPL")
    
    assert snapshot.price == 175.50
    assert mock_client.get_live_stock_prices.call_count == 3


@patch("service_b.app.services.market_data.APIClient")
def test_eodhd_provider_exhausted_retries(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_live_stock_prices.side_effect = Exception("EODHD offline")
    mock_client_class.return_value = mock_client
    
    provider = EodhdProvider(api_key="fake_key", retries=3, delay_seconds=0.01)
    with pytest.raises(UpstreamAPIError, match="Failed to fetch market data from EODHD"):
        provider.fetch_snapshot("AAPL")


# ==========================================
# CircuitBreaker Thread-Safety Tests
# ==========================================

def test_circuit_breaker_concurrent_failures_do_not_exceed_threshold():
    """
    RED: Two threads that both call record_failure() concurrently must each
    increment _failure_count exactly once.  Without a lock the read-modify-write
    is not atomic, so the final count may be under-counted and the breaker may
    never open.
    """
    from service_b.app.services.market_data import CircuitBreaker, CircuitState

    cb = CircuitBreaker(failure_threshold=100, recovery_timeout=60.0)
    barrier = threading.Barrier(50)

    def _fail():
        barrier.wait()          # all threads start at exactly the same instant
        cb.record_failure()

    threads = [threading.Thread(target=_fail) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Without a lock the count is often < 50 due to lost updates.
    assert cb._failure_count == 50


def test_circuit_breaker_concurrent_state_transition_is_idempotent():
    """
    RED: When _failure_count just reaches the threshold, two threads racing
    inside record_failure() must not set _state to OPEN more than once and
    must not corrupt _last_state_change.
    """
    from service_b.app.services.market_data import CircuitBreaker, CircuitState

    THRESHOLD = 10
    cb = CircuitBreaker(failure_threshold=THRESHOLD, recovery_timeout=60.0)
    barrier = threading.Barrier(THRESHOLD)
    state_changes: list[CircuitState] = []
    lock = threading.Lock()

    def _fail_and_record():
        barrier.wait()
        cb.record_failure()
        with lock:
            state_changes.append(cb._state)

    threads = [threading.Thread(target=_fail_and_record) for _ in range(THRESHOLD)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # The breaker must end up OPEN and the count must not exceed the threshold.
    assert cb._state == CircuitState.OPEN
    assert cb._failure_count == THRESHOLD


def test_circuit_breaker_half_open_transition_is_atomic():
    """
    RED: Multiple threads calling .state concurrently while the circuit is OPEN
    and the timeout has elapsed must only ever see CLOSED or HALF_OPEN — never
    an inconsistent intermediate value.
    """
    from service_b.app.services.market_data import CircuitBreaker, CircuitState

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
    cb.record_failure()  # trip the breaker
    time.sleep(0.05)     # let the recovery window expire

    results: list[CircuitState] = []
    lock = threading.Lock()
    barrier = threading.Barrier(20)

    def _read_state():
        barrier.wait()
        s = cb.state
        with lock:
            results.append(s)

    threads = [threading.Thread(target=_read_state) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    valid_states = {CircuitState.OPEN, CircuitState.HALF_OPEN, CircuitState.CLOSED}
    assert all(s in valid_states for s in results), f"Unexpected states seen: {results}"
    # After the timeout only HALF_OPEN or CLOSED are legal (not OPEN).
    assert all(s != CircuitState.OPEN for s in results), (
        "Circuit must have transitioned away from OPEN after recovery timeout"
    )


# ==========================================
# Resilience, Fail-Fast & Circuit Breaker Tests
# ==========================================

@patch("service_b.app.services.market_data.yf.Ticker")
def test_yfinance_provider_fail_fast_on_client_error(mock_ticker_class):
    mock_ticker = MagicMock()
    mock_ticker.info = {}  # Trigger ValueError -> client error
    mock_ticker_class.return_value = mock_ticker
    
    provider = YFinanceProvider(retries=3, delay_seconds=0.01)
    
    with pytest.raises(UpstreamAPIError) as exc_info:
        provider.fetch_snapshot("INVALID")
        
    assert exc_info.value.is_client_error is True
    # Verify it failed on the very first attempt and did not retry
    assert mock_ticker_class.call_count == 1


@patch("service_b.app.services.market_data.APIClient")
def test_eodhd_provider_fail_fast_on_client_error(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_live_stock_prices.return_value = None  # Trigger ValueError -> client error
    mock_client_class.return_value = mock_client
    
    provider = EodhdProvider(api_key="fake_key", retries=3, delay_seconds=0.01)
    
    with pytest.raises(UpstreamAPIError) as exc_info:
        provider.fetch_snapshot("INVALID")
        
    assert exc_info.value.is_client_error is True
    # Verify it failed on the very first attempt and did not retry
    assert mock_client.get_live_stock_prices.call_count == 1


def test_circuit_breaker_transitions():
    from service_b.app.services.market_data import CircuitBreaker, CircuitState
    
    # 1. Closed state initially
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True
    
    # 2. Transition to OPEN on failures
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False
    
    # 3. Transition to HALF_OPEN after recovery timeout
    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True
    
    # 4. Reset to CLOSED on success
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True


def test_fallback_provider_circuit_breaker_behavior():
    mock_primary = MagicMock()
    mock_fallback = MagicMock()
    
    # Setup primary to fail with a network error
    mock_primary.fetch_snapshot.side_effect = Exception("Primary offline")
    
    # Setup fallback to succeed
    mock_snapshot = MarketSnapshot(
        symbol="AAPL",
        name="Apple Inc.",
        price=175.50,
        currency="USD",
        timestamp=time.time()
    )
    mock_fallback.fetch_snapshot.return_value = mock_snapshot
    
    # Instantiate with a low threshold
    provider = FallbackProvider(
        primary=mock_primary,
        fallback=mock_fallback,
        failure_threshold=2,
        recovery_timeout=30.0
    )
    
    # 1. First request: primary is tried, fails, fallback succeeds
    res1 = provider.fetch_snapshot("AAPL")
    assert res1 == mock_snapshot
    assert mock_primary.fetch_snapshot.call_count == 1
    
    # 2. Second request: primary is tried, fails, fallback succeeds, trips CB
    res2 = provider.fetch_snapshot("AAPL")
    assert res2 == mock_snapshot
    assert mock_primary.fetch_snapshot.call_count == 2
    
    # 3. Third request: CB is OPEN, primary is bypassed, fallback called directly
    res3 = provider.fetch_snapshot("AAPL")
    assert res3 == mock_snapshot


    # Primary call count remains at 2!
    assert mock_primary.fetch_snapshot.call_count == 2


# ==========================================
# is_client_error Unit Tests
# ==========================================

def _make_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Helper that constructs a requests.HTTPError with a real response stub."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    err = requests.exceptions.HTTPError(response=response)
    return err


class TestIsClientError:
    """
    Unit tests for the is_client_error helper function.

    Correctness is determined by the *type* and HTTP status code of the
    exception, never by substring-matching the exception message.
    """

    # --- HTTP 4xx errors (client errors) ---

    def test_http_400_is_client_error(self):
        """HTTP 400 Bad Request should be classified as a client error."""
        assert is_client_error(_make_http_error(400)) is True

    def test_http_404_is_client_error(self):
        """HTTP 404 Not Found should be classified as a client error."""
        assert is_client_error(_make_http_error(404)) is True

    def test_http_422_is_client_error(self):
        """HTTP 422 Unprocessable Entity should be classified as a client error."""
        assert is_client_error(_make_http_error(422)) is True

    # --- HTTP errors that must NOT be treated as client errors ---

    def test_http_429_is_not_client_error(self):
        """
        HTTP 429 Too Many Requests is a *server-side* throttle, not a
        bad-client-request.  It must be retried, not suppressed.
        """
        assert is_client_error(_make_http_error(429)) is False

    def test_http_500_is_not_client_error(self):
        """HTTP 500 Internal Server Error is a server fault, not a client error."""
        assert is_client_error(_make_http_error(500)) is False

    def test_http_503_is_not_client_error(self):
        """HTTP 503 Service Unavailable is a transient server error, must retry."""
        assert is_client_error(_make_http_error(503)) is False

    # --- ValueError: always a client error (bad input / empty data) ---

    def test_value_error_is_client_error(self):
        """ValueError raised for invalid/empty data should always be a client error."""
        assert is_client_error(ValueError("empty ticker info")) is True

    # --- False-positive guard: numeric digits in the message must NOT match ---

    def test_numeric_in_message_is_not_client_error(self):
        """
        Regression guard: a message such as 'price was 404.50' must NOT be
        misidentified as a client error.  Classification must rely on
        exception *type*, not message content.
        """
        assert is_client_error(RuntimeError("The stock price was 404.50")) is False

    def test_not_found_in_message_is_not_client_error(self):
        """
        Regression guard: a plain exception whose message contains 'not found'
        must NOT be misidentified as a client error.
        """
        assert is_client_error(Exception("Data not found in cache")) is False

    # --- HTTPError without a response object ---

    def test_http_error_without_response_is_not_client_error(self):
        """
        An HTTPError that has no attached response (e.g. a connection-level
        failure) should fall through to the safe default: not a client error.
        """
        err = requests.exceptions.HTTPError()  # response=None
        assert is_client_error(err) is False

    # --- Generic / unknown exceptions ---

    def test_generic_exception_is_not_client_error(self):
        """Unrecognised exception types should default to 'not a client error'."""
        assert is_client_error(RuntimeError("unknown network issue")) is False

    def test_connection_error_is_not_client_error(self):
        """Connection errors are transient and must be retried."""
        assert is_client_error(requests.exceptions.ConnectionError("timeout")) is False

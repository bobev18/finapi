"""
Re-exports MarketSnapshot from the shared canonical definition.

Do not add fields here — edit shared/schemas/market.py instead.
"""
from shared.schemas.market import MarketSnapshot  # noqa: F401

__all__ = ["MarketSnapshot"]

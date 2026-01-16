"""Market, Event, and Contract data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class MarketStatus(Enum):
    """Market status enumeration."""
    OPEN = "open"
    CLOSED = "closed"
    SETTLED = "settled"


class ContractSide(Enum):
    """Contract side (YES/NO)."""
    YES = "yes"
    NO = "no"


@dataclass
class Contract:
    """Represents a single contract within a market."""

    ticker: str
    side: ContractSide
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    last_price: Optional[float] = None
    volume: int = 0

    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price from bid/ask."""
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None


@dataclass
class Market:
    """Represents a Kalshi market."""

    ticker: str
    event_ticker: str
    title: str
    status: MarketStatus
    close_time: datetime
    result: Optional[str] = None

    # Pricing
    yes_bid: Optional[float] = None
    yes_ask: Optional[float] = None
    no_bid: Optional[float] = None
    no_ask: Optional[float] = None

    # Volume
    volume: int = 0
    open_interest: int = 0

    # Metadata
    rules: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict) -> "Market":
        """Create Market from API response."""
        return cls(
            ticker=data["ticker"],
            event_ticker=data["event_ticker"],
            title=data["title"],
            status=MarketStatus(data["status"]),
            close_time=datetime.fromisoformat(data["close_time"].replace("Z", "+00:00")),
            result=data.get("result"),
            yes_bid=data.get("yes_bid"),
            yes_ask=data.get("yes_ask"),
            no_bid=data.get("no_bid"),
            no_ask=data.get("no_ask"),
            volume=data.get("volume", 0),
            open_interest=data.get("open_interest", 0),
            rules=data.get("rules_primary", ""),
            category=data.get("category", ""),
            tags=data.get("tags", []),
        )


@dataclass
class Event:
    """Represents a Kalshi event containing multiple markets."""

    ticker: str
    series_ticker: str
    title: str
    category: str
    markets: list[Market] = field(default_factory=list)

    # Sports-specific
    league: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    game_time: Optional[datetime] = None

    @classmethod
    def from_api_response(cls, data: dict) -> "Event":
        """Create Event from API response."""
        return cls(
            ticker=data["event_ticker"],
            series_ticker=data["series_ticker"],
            title=data["title"],
            category=data.get("category", ""),
        )


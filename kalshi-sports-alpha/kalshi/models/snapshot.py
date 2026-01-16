"""Market snapshot data model - point-in-time view of a contract."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MarketSnapshot:
    """
    Represents a single point-in-time view of a contract.
    
    This is the core data contract for the feature engineering pipeline.
    """

    # Identifiers
    market_id: str
    event_id: str
    snapshot_time: datetime

    # Sports context
    league: str
    team_home: Optional[str] = None
    team_away: Optional[str] = None
    market_type: str = "moneyline"  # moneyline, total, prop

    # Contract side
    contract_side: str = "YES"  # YES or NO

    # Pricing
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    mid_price: Optional[float] = None
    last_trade_price: Optional[float] = None
    last_trade_size: Optional[int] = None

    # Volume (rolling windows)
    volume_1m: int = 0
    volume_5m: int = 0
    volume_1h: int = 0
    volume_total: int = 0

    # Depth
    total_bid_depth: int = 0
    total_ask_depth: int = 0
    bid_depth_notional: float = 0.0
    ask_depth_notional: float = 0.0

    # Timing
    time_to_kickoff_seconds: Optional[int] = None
    time_to_resolution_seconds: Optional[int] = None

    @property
    def spread(self) -> Optional[float]:
        """Bid-ask spread."""
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_pct(self) -> Optional[float]:
        """Spread as percentage of mid price."""
        if self.spread is not None and self.mid_price and self.mid_price > 0:
            return self.spread / self.mid_price
        return None

    @property
    def depth_imbalance(self) -> float:
        """Depth imbalance ratio (-1 to 1)."""
        total = self.total_bid_depth + self.total_ask_depth
        if total == 0:
            return 0
        return (self.total_bid_depth - self.total_ask_depth) / total

    @property
    def kickoff_window(self) -> str:
        """
        Categorize time to kickoff into regimes.
        
        Returns:
            One of: 'far', 'approaching', 'imminent', 'live', 'unknown'
        """
        if self.time_to_kickoff_seconds is None:
            return "unknown"

        seconds = self.time_to_kickoff_seconds

        if seconds < 0:
            return "live"  # Game in progress
        elif seconds <= 600:  # 10 minutes
            return "imminent"
        elif seconds <= 7200:  # 2 hours
            return "approaching"
        else:
            return "far"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "market_id": self.market_id,
            "event_id": self.event_id,
            "snapshot_time": self.snapshot_time.isoformat(),
            "league": self.league,
            "team_home": self.team_home,
            "team_away": self.team_away,
            "market_type": self.market_type,
            "contract_side": self.contract_side,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "last_trade_price": self.last_trade_price,
            "last_trade_size": self.last_trade_size,
            "volume_1m": self.volume_1m,
            "volume_5m": self.volume_5m,
            "volume_1h": self.volume_1h,
            "volume_total": self.volume_total,
            "total_bid_depth": self.total_bid_depth,
            "total_ask_depth": self.total_ask_depth,
            "bid_depth_notional": self.bid_depth_notional,
            "ask_depth_notional": self.ask_depth_notional,
            "time_to_kickoff_seconds": self.time_to_kickoff_seconds,
            "time_to_resolution_seconds": self.time_to_resolution_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MarketSnapshot":
        """Create from dictionary."""
        data = data.copy()
        data["snapshot_time"] = datetime.fromisoformat(data["snapshot_time"])
        return cls(**data)


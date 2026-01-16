"""Trade data model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class TradeSide(Enum):
    """Trade side - whether the taker bought or sold."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Trade:
    """Represents a single trade execution."""

    trade_id: str
    ticker: str
    timestamp: datetime
    price: float
    count: int  # Number of contracts
    taker_side: TradeSide

    # Optional enrichments
    notional: Optional[float] = None  # price * count in cents

    def __post_init__(self):
        """Calculate derived fields."""
        if self.notional is None:
            self.notional = self.price * self.count

    @classmethod
    def from_api_response(cls, data: dict) -> "Trade":
        """Create Trade from API response."""
        return cls(
            trade_id=data["trade_id"],
            ticker=data["ticker"],
            timestamp=datetime.fromisoformat(
                data["created_time"].replace("Z", "+00:00")
            ),
            price=data["yes_price"] / 100,  # Convert cents to dollars
            count=data["count"],
            taker_side=TradeSide(data.get("taker_side", "buy")),
        )

    @property
    def is_buyer_initiated(self) -> bool:
        """Check if trade was buyer-initiated."""
        return self.taker_side == TradeSide.BUY

    @property
    def is_seller_initiated(self) -> bool:
        """Check if trade was seller-initiated."""
        return self.taker_side == TradeSide.SELL


@dataclass
class TradeCluster:
    """Represents a cluster of related trades."""

    trades: list[Trade]
    start_time: datetime
    end_time: datetime

    @property
    def total_volume(self) -> int:
        """Total contracts traded in cluster."""
        return sum(t.count for t in self.trades)

    @property
    def total_notional(self) -> float:
        """Total notional value of cluster."""
        return sum(t.notional or 0 for t in self.trades)

    @property
    def vwap(self) -> float:
        """Volume-weighted average price."""
        if self.total_volume == 0:
            return 0
        return sum(t.price * t.count for t in self.trades) / self.total_volume

    @property
    def net_flow(self) -> int:
        """Net buy-sell flow (positive = net buying)."""
        return sum(
            t.count if t.is_buyer_initiated else -t.count for t in self.trades
        )


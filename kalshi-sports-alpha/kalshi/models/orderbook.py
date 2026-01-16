"""Order book data model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class OrderBookLevel:
    """Single price level in the order book."""

    price: float  # In dollars (0.01 - 0.99)
    quantity: int  # Number of contracts

    @property
    def notional(self) -> float:
        """Total notional at this level."""
        return self.price * self.quantity


@dataclass
class OrderBook:
    """Order book snapshot for a market."""

    ticker: str
    timestamp: datetime
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)

    @property
    def best_bid(self) -> Optional[float]:
        """Best (highest) bid price."""
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Best (lowest) ask price."""
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        """Mid price between best bid and ask."""
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Bid-ask spread."""
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        """Spread in basis points relative to mid price."""
        if self.spread is not None and self.mid_price and self.mid_price > 0:
            return (self.spread / self.mid_price) * 10000
        return None

    @property
    def total_bid_depth(self) -> int:
        """Total contracts on bid side."""
        return sum(level.quantity for level in self.bids)

    @property
    def total_ask_depth(self) -> int:
        """Total contracts on ask side."""
        return sum(level.quantity for level in self.asks)

    @property
    def total_bid_notional(self) -> float:
        """Total notional on bid side."""
        return sum(level.notional for level in self.bids)

    @property
    def total_ask_notional(self) -> float:
        """Total notional on ask side."""
        return sum(level.notional for level in self.asks)

    @property
    def depth_imbalance(self) -> float:
        """
        Depth imbalance ratio.
        Positive = more bids, Negative = more asks.
        Range: -1 to 1
        """
        total_bid = self.total_bid_depth
        total_ask = self.total_ask_depth
        total = total_bid + total_ask
        if total == 0:
            return 0
        return (total_bid - total_ask) / total

    def price_impact(self, size: int, side: str) -> Optional[float]:
        """
        Estimate price impact for a given order size.

        Args:
            size: Number of contracts
            side: 'buy' or 'sell'

        Returns:
            Estimated average execution price
        """
        levels = self.asks if side == "buy" else self.bids
        if not levels:
            return None

        remaining = size
        total_cost = 0.0

        for level in levels:
            fill = min(remaining, level.quantity)
            total_cost += fill * level.price
            remaining -= fill
            if remaining <= 0:
                break

        if remaining > 0:
            # Not enough liquidity
            return None

        return total_cost / size

    @classmethod
    def from_api_response(cls, ticker: str, data: dict) -> "OrderBook":
        """Create OrderBook from API response."""
        bids = [
            OrderBookLevel(price=level[0] / 100, quantity=level[1])
            for level in data.get("yes", {}).get("bids", [])
        ]
        asks = [
            OrderBookLevel(price=level[0] / 100, quantity=level[1])
            for level in data.get("yes", {}).get("asks", [])
        ]

        return cls(
            ticker=ticker,
            timestamp=datetime.now(),
            bids=sorted(bids, key=lambda x: -x.price),  # Highest first
            asks=sorted(asks, key=lambda x: x.price),  # Lowest first
        )


"""Slippage and partial fill models."""

from dataclasses import dataclass
from typing import Optional
import random


@dataclass
class Fill:
    """Represents a trade fill."""

    requested_size: int
    filled_size: int
    avg_price: float
    slippage: float

    @property
    def fill_rate(self) -> float:
        """Percentage of order filled."""
        if self.requested_size == 0:
            return 0
        return self.filled_size / self.requested_size


@dataclass
class SlippageModel:
    """Model for price slippage."""

    base_slippage_bps: float = 10  # 10 bps base
    size_impact_factor: float = 0.1  # Additional slippage per % of depth
    volatility_factor: float = 1.0  # Multiplier for volatility

    def estimate_slippage(
        self,
        size: int,
        depth: int,
        volatility: float = 0.01,
        spread: float = 0.02
    ) -> float:
        """
        Estimate slippage for an order.

        Args:
            size: Order size in contracts
            depth: Available depth
            volatility: Current volatility
            spread: Current bid-ask spread

        Returns:
            Estimated slippage in price terms
        """
        # Base slippage
        slippage = self.base_slippage_bps / 10000

        # Size impact
        if depth > 0:
            size_pct = size / depth
            slippage += self.size_impact_factor * size_pct

        # Volatility impact
        slippage *= (1 + volatility * self.volatility_factor)

        # At minimum, half the spread
        slippage = max(slippage, spread / 2)

        return slippage


class FillModel:
    """Model for trade fills including partial fills."""

    def __init__(
        self,
        slippage_model: Optional[SlippageModel] = None,
        partial_fill_prob: float = 0.1,
        min_fill_pct: float = 0.5,
    ):
        """
        Initialize fill model.

        Args:
            slippage_model: Model for slippage estimation
            partial_fill_prob: Probability of partial fill
            min_fill_pct: Minimum fill percentage when partial
        """
        self.slippage = slippage_model or SlippageModel()
        self.partial_fill_prob = partial_fill_prob
        self.min_fill_pct = min_fill_pct

    def simulate_fill(
        self,
        side: str,
        size: int,
        price: float,
        depth: int,
        volatility: float = 0.01,
        spread: float = 0.02,
    ) -> Optional[Fill]:
        """
        Simulate a trade fill.

        Args:
            side: 'YES' or 'NO'
            size: Requested size
            price: Current market price
            depth: Available depth
            volatility: Current volatility
            spread: Current spread

        Returns:
            Fill object or None if no fill
        """
        if size <= 0 or depth <= 0:
            return None

        # Determine filled size
        if size > depth:
            # Can only fill available depth
            filled_size = depth
        elif random.random() < self.partial_fill_prob:
            # Random partial fill
            fill_pct = random.uniform(self.min_fill_pct, 1.0)
            filled_size = int(size * fill_pct)
        else:
            filled_size = size

        if filled_size <= 0:
            return None

        # Calculate slippage
        slippage = self.slippage.estimate_slippage(
            size=filled_size,
            depth=depth,
            volatility=volatility,
            spread=spread,
        )

        # Adjust price for slippage
        # Buying YES: price increases
        # Buying NO: price of YES decreases (NO increases)
        if side == "YES":
            avg_price = price + slippage
        else:
            avg_price = price - slippage

        # Clamp to valid range
        avg_price = max(0.01, min(0.99, avg_price))

        return Fill(
            requested_size=size,
            filled_size=filled_size,
            avg_price=avg_price,
            slippage=slippage,
        )


def estimate_market_impact(
    size: int,
    depth: int,
    current_price: float,
    price_impact_coefficient: float = 0.001
) -> float:
    """
    Estimate permanent market impact of a trade.

    Uses Kyle's lambda-style model:
    Impact = lambda * signed_order_flow

    Args:
        size: Order size
        depth: Market depth
        current_price: Current price
        price_impact_coefficient: Impact per contract/depth ratio

    Returns:
        Estimated price impact
    """
    if depth == 0:
        return 0

    impact = price_impact_coefficient * (size / depth) * current_price
    return impact


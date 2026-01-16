"""Fragile Market Snipe signal - identify markets where small capital moves price."""

from typing import Optional
from kalshi.models import MarketSnapshot
from .signal_base import Signal, SignalDirection, SignalGenerator


class FragileMarketSignal(SignalGenerator):
    """
    Identify markets where small capital moves price.

    Intent: Find inefficiently priced markets with low liquidity.

    Criteria:
    - Low depth
    - High price impact
    - Approaching resolution

    Direction: Based on pricing inefficiency analysis.
    """

    name = "fragile_market"
    description = "Snipe fragile, illiquid markets"

    def __init__(
        self,
        max_depth: int = 200,  # contracts
        min_impact: float = 0.03,  # 3 cents per $100
        max_time_to_resolution: int = 7200,  # 2 hours
        min_edge: float = 0.02,  # 2% minimum edge
    ):
        self.max_depth = max_depth
        self.min_impact = min_impact
        self.max_time_to_resolution = max_time_to_resolution
        self.min_edge = min_edge

    def generate(
        self,
        snapshot: MarketSnapshot,
        features: dict[str, float],
        **kwargs
    ) -> Optional[Signal]:
        """Generate fragile market signal."""
        # Check time to resolution
        if snapshot.time_to_resolution_seconds is None:
            return None

        if snapshot.time_to_resolution_seconds > self.max_time_to_resolution:
            return None

        total_depth = snapshot.total_bid_depth + snapshot.total_ask_depth
        price_impact = features.get("price_impact_100", 0)

        # Must be fragile
        if total_depth > self.max_depth:
            return None

        if price_impact < self.min_impact:
            return None

        # Look for pricing inefficiency
        implied_edge = features.get("implied_edge", 0)
        favorite_longshot = features.get("favorite_longshot_bias", 0)

        # Need some edge to act on
        if abs(implied_edge) < self.min_edge * 100:  # Convert to cents
            return None

        # Direction based on detected edge
        direction = SignalDirection.YES if implied_edge > 0 else SignalDirection.NO

        # Strength based on fragility
        depth_score = max(0, 1 - total_depth / self.max_depth)
        impact_score = min(1, price_impact / 0.10)
        strength = (depth_score + impact_score) / 2

        # Confidence based on edge magnitude
        confidence = min(1, abs(implied_edge) / 10)  # 10 cent edge = max confidence

        # Risk: these markets can be illiquid to exit
        hours_left = snapshot.time_to_resolution_seconds / 3600

        rationale = (
            f"Fragile market detected: "
            f"depth={total_depth}, "
            f"impact={price_impact:.3f}, "
            f"edge={implied_edge:+.1f}c, "
            f"{hours_left:.1f}h to resolution"
        )

        signal = self.create_signal(
            direction=direction,
            strength=strength,
            confidence=confidence,
            rationale=rationale,
            snapshot=snapshot,
            features_used=["price_impact_100", "implied_edge", "favorite_longshot_bias"],
        )
        signal.metadata["total_depth"] = total_depth
        signal.metadata["hours_to_resolution"] = hours_left
        signal.metadata["risk_flags"] = ["illiquid", "hard_to_exit"]

        return signal


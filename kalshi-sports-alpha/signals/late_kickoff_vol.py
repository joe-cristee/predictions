"""Late Kickoff Volatility signal - exploit fragile pricing near kickoff."""

from typing import Optional
from kalshi.models import MarketSnapshot
from .signal_base import Signal, SignalDirection, SignalGenerator


class LateKickoffVolSignal(SignalGenerator):
    """
    Exploit fragile pricing near kickoff.

    Intent: Capitalize on volatility spikes as kickoff approaches.

    Criteria:
    - Volatility spike
    - Liquidity thinning
    - Short time to kickoff

    Direction: Based on order book imbalance.
    """

    name = "late_kickoff_vol"
    description = "Exploit late kickoff volatility"

    def __init__(
        self,
        volatility_ratio_threshold: float = 1.5,
        max_time_to_kickoff: int = 600,  # 10 minutes
        min_imbalance: float = 0.3,
        liquidity_warning: float = 0.3,
    ):
        self.volatility_ratio_threshold = volatility_ratio_threshold
        self.max_time_to_kickoff = max_time_to_kickoff
        self.min_imbalance = min_imbalance
        self.liquidity_warning = liquidity_warning

    def generate(
        self,
        snapshot: MarketSnapshot,
        features: dict[str, float],
        **kwargs
    ) -> Optional[Signal]:
        """Generate late kickoff volatility signal."""
        # Must be close to kickoff
        if snapshot.time_to_kickoff_seconds is None:
            return None

        if snapshot.time_to_kickoff_seconds > self.max_time_to_kickoff:
            return None

        if snapshot.time_to_kickoff_seconds < 0:
            return None  # Already live

        volatility_ratio = features.get("volatility_ratio", 1)
        depth_imbalance = features.get("depth_imbalance", 0)
        liquidity = features.get("liquidity_score", 0.5)

        # Check for volatility spike
        if volatility_ratio < self.volatility_ratio_threshold:
            return None

        # Need clear directional imbalance
        if abs(depth_imbalance) < self.min_imbalance:
            return None

        # Direction follows depth imbalance
        # More bid depth = bullish, more ask depth = bearish
        direction = SignalDirection.YES if depth_imbalance > 0 else SignalDirection.NO

        # Strength based on volatility magnitude
        strength = min(1, (volatility_ratio - 1) / 2)

        # Confidence based on imbalance clarity
        confidence = abs(depth_imbalance)

        # Warning if liquidity is too low
        risk_flags = []
        if liquidity < self.liquidity_warning:
            confidence *= 0.7
            risk_flags.append("low_liquidity")

        minutes = snapshot.time_to_kickoff_seconds / 60

        rationale = (
            f"Late kickoff vol opportunity: "
            f"{minutes:.0f}min to kickoff, "
            f"vol_ratio={volatility_ratio:.2f}, "
            f"imbalance={depth_imbalance:+.2f}"
        )

        signal = self.create_signal(
            direction=direction,
            strength=strength,
            confidence=confidence,
            rationale=rationale,
            snapshot=snapshot,
            features_used=["volatility_ratio", "depth_imbalance", "liquidity_score"],
        )
        signal.metadata["risk_flags"] = risk_flags
        signal.metadata["minutes_to_kickoff"] = minutes

        return signal


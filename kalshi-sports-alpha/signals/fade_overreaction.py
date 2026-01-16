"""Fade Overreaction signal - fade narrative-driven moves."""

from typing import Optional
from kalshi.models import MarketSnapshot
from .signal_base import Signal, SignalDirection, SignalGenerator


class FadeOverreactionSignal(SignalGenerator):
    """
    Fade narrative-driven moves.

    Intent: Profit from mean reversion after emotional price moves.

    Criteria:
    - High price velocity
    - Low volume confirmation
    - No external news
    - Short time horizon

    Direction: Opposite of recent price move.
    """

    name = "fade_overreaction"
    description = "Fade narrative-driven price moves"

    def __init__(
        self,
        velocity_threshold: float = 0.5,  # cents per minute
        volume_ratio_max: float = 1.5,  # recent vs average
        overreaction_threshold: float = 0.5,
        min_time_to_kickoff: int = 1800,  # 30 minutes
    ):
        self.velocity_threshold = velocity_threshold
        self.volume_ratio_max = volume_ratio_max
        self.overreaction_threshold = overreaction_threshold
        self.min_time_to_kickoff = min_time_to_kickoff

    def generate(
        self,
        snapshot: MarketSnapshot,
        features: dict[str, float],
        **kwargs
    ) -> Optional[Signal]:
        """Generate fade overreaction signal."""
        required = ["price_velocity", "overreaction_score"]
        if not self.validate_inputs(snapshot, features, required):
            return None

        velocity = features.get("price_velocity", 0)
        overreaction = features.get("overreaction_score", 0)
        mean_reversion = features.get("mean_reversion_signal", 0)

        # Need enough time for mean reversion
        if snapshot.time_to_kickoff_seconds is not None:
            if snapshot.time_to_kickoff_seconds < self.min_time_to_kickoff:
                return None

        # Check for overreaction
        if abs(velocity) < self.velocity_threshold:
            return None

        if overreaction < self.overreaction_threshold:
            return None

        # Direction is opposite of price move (fade)
        direction = SignalDirection.NO if velocity > 0 else SignalDirection.YES

        # Strength based on overreaction magnitude
        strength = min(1, overreaction)

        # Confidence based on mean reversion alignment
        if mean_reversion != 0:
            # Higher confidence if mean reversion agrees
            mr_agrees = (mean_reversion > 0 and direction == SignalDirection.YES) or \
                       (mean_reversion < 0 and direction == SignalDirection.NO)
            confidence = 0.7 if mr_agrees else 0.4
        else:
            confidence = 0.5

        # Adjust for liquidity
        liquidity = features.get("liquidity_score", 0.5)
        confidence *= liquidity

        rationale = (
            f"Overreaction detected: "
            f"velocity={velocity:+.2f}c/min, "
            f"overreaction={overreaction:.2f}, "
            f"fading to {direction.value}"
        )

        return self.create_signal(
            direction=direction,
            strength=strength,
            confidence=confidence,
            rationale=rationale,
            snapshot=snapshot,
            features_used=required + ["mean_reversion_signal", "liquidity_score"],
        )


"""Tail Informed Flow signal - follow informed accumulation."""

from typing import Optional
from kalshi.models import MarketSnapshot
from .signal_base import Signal, SignalDirection, SignalGenerator


class TailInformedFlowSignal(SignalGenerator):
    """
    Follow informed accumulation.

    Intent: Identify and follow large, informed traders.

    Criteria:
    - High trade clustering
    - Large notional
    - Low price impact
    - Narrow spread

    Direction: Same as dominant flow.
    """

    name = "tail_informed_flow"
    description = "Follow informed accumulation patterns"

    def __init__(
        self,
        clustering_threshold: float = 0.6,
        notional_threshold: float = 500,  # dollars
        impact_threshold: float = 0.02,  # 2 cents
        spread_threshold: float = 0.05,  # 5 cents
    ):
        self.clustering_threshold = clustering_threshold
        self.notional_threshold = notional_threshold
        self.impact_threshold = impact_threshold
        self.spread_threshold = spread_threshold

    def generate(
        self,
        snapshot: MarketSnapshot,
        features: dict[str, float],
        **kwargs
    ) -> Optional[Signal]:
        """Generate tail informed flow signal."""
        required = ["trade_clustering", "spread", "trade_flow_imbalance"]
        if not self.validate_inputs(snapshot, features, required):
            return None

        clustering = features.get("trade_clustering", 0)
        spread = features.get("spread", 1)
        flow_imbalance = features.get("trade_flow_imbalance", 0)
        price_impact = features.get("price_impact_100", 0.1)

        # Check criteria
        if clustering < self.clustering_threshold:
            return None

        if spread > self.spread_threshold:
            return None

        if price_impact > self.impact_threshold:
            return None

        # Determine direction from flow imbalance
        if abs(flow_imbalance) < 0.2:
            return None  # No clear direction

        direction = SignalDirection.YES if flow_imbalance > 0 else SignalDirection.NO

        # Calculate strength based on how well criteria are met
        clustering_score = min(1, clustering / 0.8)
        spread_score = max(0, 1 - spread / self.spread_threshold)
        impact_score = max(0, 1 - price_impact / self.impact_threshold)

        strength = (clustering_score + spread_score + impact_score) / 3
        confidence = abs(flow_imbalance)

        rationale = (
            f"Detected informed accumulation: "
            f"clustering={clustering:.2f}, "
            f"flow={flow_imbalance:+.2f}, "
            f"spread={spread:.3f}"
        )

        return self.create_signal(
            direction=direction,
            strength=strength,
            confidence=confidence,
            rationale=rationale,
            snapshot=snapshot,
            features_used=required,
        )


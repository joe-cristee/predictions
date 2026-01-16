"""Signal aggregation - combine multiple signals into unified view."""

from typing import Optional
from dataclasses import dataclass, field

from signals import Signal, SignalDirection


@dataclass
class AggregatedSignal:
    """Combined signal from multiple sources."""

    market_id: str
    direction: SignalDirection
    aggregate_score: float
    confidence: float
    contributing_signals: list[Signal]
    weights_used: dict[str, float] = field(default_factory=dict)

    @property
    def signal_count(self) -> int:
        """Number of contributing signals."""
        return len(self.contributing_signals)

    @property
    def agreement_ratio(self) -> float:
        """Ratio of signals agreeing on direction."""
        if not self.contributing_signals:
            return 0.0

        agreeing = sum(
            1 for s in self.contributing_signals
            if s.direction == self.direction
        )
        return agreeing / len(self.contributing_signals)


class SignalAggregator:
    """
    Combine multiple signals into single recommendation.

    Supports weighted linear and logistic combination.
    Configurable via signals.yaml.
    """

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        method: str = "weighted_linear",
        min_signals: int = 1,
    ):
        """
        Initialize aggregator.

        Args:
            weights: Signal name -> weight mapping
            method: Aggregation method ('weighted_linear', 'logistic', 'max')
            min_signals: Minimum signals required
        """
        self.weights = weights or {}
        self.method = method
        self.min_signals = min_signals

        # Default weights if not specified
        self.default_weight = 1.0

    def aggregate(self, signals: list[Signal]) -> Optional[AggregatedSignal]:
        """
        Aggregate multiple signals for a market.

        Args:
            signals: List of signals for the same market

        Returns:
            AggregatedSignal or None if insufficient signals
        """
        if len(signals) < self.min_signals:
            return None

        # Filter out neutral signals
        directional = [s for s in signals if s.direction != SignalDirection.NEUTRAL]
        if not directional:
            return None

        market_id = directional[0].market_id

        # Calculate weighted scores by direction
        yes_score = 0.0
        no_score = 0.0
        yes_weight = 0.0
        no_weight = 0.0
        weights_used = {}

        for signal in directional:
            weight = self.weights.get(signal.name, self.default_weight)
            weighted_score = signal.composite_score * weight
            weights_used[signal.name] = weight

            if signal.direction == SignalDirection.YES:
                yes_score += weighted_score
                yes_weight += weight
            else:
                no_score += weighted_score
                no_weight += weight

        # Determine direction
        if yes_score > no_score:
            direction = SignalDirection.YES
            aggregate_score = yes_score / yes_weight if yes_weight > 0 else 0
        elif no_score > yes_score:
            direction = SignalDirection.NO
            aggregate_score = no_score / no_weight if no_weight > 0 else 0
        else:
            return None  # No clear direction

        # Confidence from agreement and individual confidences
        agreement = sum(
            1 for s in directional if s.direction == direction
        ) / len(directional)

        avg_confidence = sum(s.confidence for s in directional) / len(directional)
        confidence = agreement * avg_confidence

        return AggregatedSignal(
            market_id=market_id,
            direction=direction,
            aggregate_score=aggregate_score,
            confidence=confidence,
            contributing_signals=directional,
            weights_used=weights_used,
        )

    def aggregate_batch(
        self,
        signals_by_market: dict[str, list[Signal]]
    ) -> list[AggregatedSignal]:
        """Aggregate signals for multiple markets."""
        results = []
        for market_id, signals in signals_by_market.items():
            agg = self.aggregate(signals)
            if agg is not None:
                results.append(agg)
        return results


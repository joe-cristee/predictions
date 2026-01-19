"""Signal aggregation - combine multiple signals into unified view."""

from typing import Optional
from dataclasses import dataclass, field

from signals import Signal, SignalDirection


def compute_feature_overlap(signal_a: Signal, signal_b: Signal) -> float:
    """
    Compute feature overlap between two signals.

    Returns a value between 0 (no overlap) and 1 (complete overlap).
    Signals that share features are likely correlated.
    """
    features_a = set(signal_a.features_used)
    features_b = set(signal_b.features_used)

    if not features_a or not features_b:
        return 0.0

    intersection = features_a & features_b
    union = features_a | features_b

    # Jaccard similarity
    return len(intersection) / len(union) if union else 0.0


def compute_pairwise_correlations(signals: list[Signal]) -> dict[tuple[str, str], float]:
    """
    Compute pairwise correlations between signals based on feature overlap.

    Returns dict mapping (signal_a_name, signal_b_name) -> correlation score
    """
    correlations = {}
    for i, sig_a in enumerate(signals):
        for sig_b in signals[i + 1:]:
            overlap = compute_feature_overlap(sig_a, sig_b)
            key = tuple(sorted([sig_a.name, sig_b.name]))
            correlations[key] = overlap
    return correlations


@dataclass
class AggregatedSignal:
    """Combined signal from multiple sources."""

    market_id: str
    direction: SignalDirection
    aggregate_score: float
    confidence: float
    contributing_signals: list[Signal]
    weights_used: dict[str, float] = field(default_factory=dict)

    # Correlation tracking
    feature_correlations: dict[tuple[str, str], float] = field(default_factory=dict)
    avg_correlation: float = 0.0
    independent_signal_count: float = 0.0  # Effective count after correlation adjustment

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
        min_signals: int = 2,
        require_agreement: bool = True,
        min_agreement_ratio: float = 0.6,
    ):
        """
        Initialize aggregator.

        Args:
            weights: Signal name -> weight mapping
            method: Aggregation method ('weighted_linear', 'logistic', 'max')
            min_signals: Minimum signals required (default 2 to reduce false positives)
            require_agreement: Whether to require signals to agree on direction
            min_agreement_ratio: Minimum ratio of signals that must agree (0-1)
        """
        self.weights = weights or {}
        self.method = method
        self.min_signals = min_signals
        self.require_agreement = require_agreement
        self.min_agreement_ratio = min_agreement_ratio

        # Default weights if not specified
        self.default_weight = 1.0

    def aggregate(self, signals: list[Signal]) -> Optional[AggregatedSignal]:
        """
        Aggregate multiple signals for a market.

        Args:
            signals: List of signals for the same market

        Returns:
            AggregatedSignal or None if insufficient signals or agreement requirements not met
        """
        if len(signals) < self.min_signals:
            return None

        # Filter out neutral signals
        directional = [s for s in signals if s.direction != SignalDirection.NEUTRAL]
        if not directional:
            return None

        # Check minimum directional signals requirement
        if len(directional) < self.min_signals:
            return None

        market_id = directional[0].market_id

        # Calculate weighted scores by direction
        yes_score = 0.0
        no_score = 0.0
        yes_weight = 0.0
        no_weight = 0.0
        yes_count = 0
        no_count = 0
        weights_used = {}

        for signal in directional:
            weight = self.weights.get(signal.name, self.default_weight)
            weighted_score = signal.composite_score * weight
            weights_used[signal.name] = weight

            if signal.direction == SignalDirection.YES:
                yes_score += weighted_score
                yes_weight += weight
                yes_count += 1
            else:
                no_score += weighted_score
                no_weight += weight
                no_count += 1

        # Determine direction
        if yes_score > no_score:
            direction = SignalDirection.YES
            aggregate_score = yes_score / yes_weight if yes_weight > 0 else 0
            agreeing_count = yes_count
        elif no_score > yes_score:
            direction = SignalDirection.NO
            aggregate_score = no_score / no_weight if no_weight > 0 else 0
            agreeing_count = no_count
        else:
            return None  # No clear direction

        # Calculate agreement ratio
        agreement_ratio = agreeing_count / len(directional)

        # Enforce agreement requirement
        if self.require_agreement and agreement_ratio < self.min_agreement_ratio:
            return None  # Signals don't agree enough

        avg_confidence = sum(s.confidence for s in directional) / len(directional)

        # Compute signal correlations based on feature overlap
        correlations = compute_pairwise_correlations(directional)
        avg_correlation = (
            sum(correlations.values()) / len(correlations) if correlations else 0.0
        )

        # Calculate effective independent signal count
        # Highly correlated signals contribute less to independence
        # Formula: effective_count = n / (1 + (n-1) * avg_correlation)
        # At avg_correlation=0: effective = n (all independent)
        # At avg_correlation=1: effective = 1 (all identical)
        n = len(directional)
        independent_count = n / (1 + (n - 1) * avg_correlation) if n > 0 else 0

        # Adjust confidence based on correlation
        # Penalize confidence when signals are highly correlated
        correlation_penalty = 1 - (avg_correlation * 0.3)  # Max 30% penalty
        confidence = agreement_ratio * avg_confidence * correlation_penalty

        return AggregatedSignal(
            market_id=market_id,
            direction=direction,
            aggregate_score=aggregate_score,
            confidence=confidence,
            contributing_signals=directional,
            weights_used=weights_used,
            feature_correlations=correlations,
            avg_correlation=avg_correlation,
            independent_signal_count=independent_count,
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


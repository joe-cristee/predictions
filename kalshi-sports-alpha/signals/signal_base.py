"""Base signal class and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from kalshi.models import MarketSnapshot


class SignalDirection(Enum):
    """Signal direction - which side to bet."""
    YES = "YES"
    NO = "NO"
    NEUTRAL = "NEUTRAL"


@dataclass
class Signal:
    """
    Directional insight produced from one or more features.
    
    This is the output of signal generators, consumed by the strategy layer.
    """

    name: str
    direction: SignalDirection
    strength: float  # 0-1, how strong the signal is
    confidence: float  # 0-1, how confident we are in the signal
    rationale: str

    # Context
    market_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    features_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate signal values."""
        self.strength = max(0, min(1, self.strength))
        self.confidence = max(0, min(1, self.confidence))

    @property
    def composite_score(self) -> float:
        """Combined score (strength * confidence)."""
        return self.strength * self.confidence

    @property
    def is_actionable(self) -> bool:
        """Check if signal is strong enough to act on."""
        return (
            self.direction != SignalDirection.NEUTRAL
            and self.composite_score >= 0.3
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "direction": self.direction.value,
            "strength": self.strength,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "market_id": self.market_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "composite_score": self.composite_score,
        }


class SignalGenerator(ABC):
    """Abstract base class for signal generators."""

    name: str = "base_signal"
    description: str = ""

    @abstractmethod
    def generate(
        self,
        snapshot: MarketSnapshot,
        features: dict[str, float],
        **kwargs
    ) -> Optional[Signal]:
        """
        Generate a signal from market snapshot and features.

        Args:
            snapshot: Current market snapshot
            features: Computed feature values
            **kwargs: Additional context (trades, orderbook, etc.)

        Returns:
            Signal if conditions are met, None otherwise
        """
        pass

    def validate_inputs(
        self,
        snapshot: MarketSnapshot,
        features: dict[str, float],
        required_features: list[str]
    ) -> bool:
        """Check that required features are present."""
        for feat in required_features:
            if feat not in features or features[feat] is None:
                return False
        return True

    def create_signal(
        self,
        direction: SignalDirection,
        strength: float,
        confidence: float,
        rationale: str,
        snapshot: MarketSnapshot,
        features_used: list[str]
    ) -> Signal:
        """Helper to create a signal with common fields."""
        return Signal(
            name=self.name,
            direction=direction,
            strength=strength,
            confidence=confidence,
            rationale=rationale,
            market_id=snapshot.market_id,
            timestamp=snapshot.snapshot_time,
            features_used=features_used,
        )


class CompositeSignalGenerator(SignalGenerator):
    """Combines multiple signal generators."""

    name = "composite"

    def __init__(self, generators: list[SignalGenerator]):
        self.generators = generators

    def generate(
        self,
        snapshot: MarketSnapshot,
        features: dict[str, float],
        **kwargs
    ) -> list[Signal]:
        """Generate signals from all sub-generators."""
        signals = []
        for gen in self.generators:
            signal = gen.generate(snapshot, features, **kwargs)
            if signal is not None:
                signals.append(signal)
        return signals


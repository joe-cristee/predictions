"""Feature discovery and execution registry."""

from typing import Callable, Any, Optional
from dataclasses import dataclass, field
import logging

from kalshi.models import MarketSnapshot


logger = logging.getLogger(__name__)


@dataclass
class FeatureDefinition:
    """Definition of a registered feature."""

    name: str
    compute_fn: Callable[[MarketSnapshot], float]
    category: str
    description: str = ""
    dependencies: list[str] = field(default_factory=list)


class FeatureRegistry:
    """Registry for feature discovery and computation."""

    _instance: Optional["FeatureRegistry"] = None
    _features: dict[str, FeatureDefinition] = {}

    def __new__(cls):
        """Singleton pattern for global registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._features = {}
        return cls._instance

    def register(
        self,
        name: str,
        compute_fn: Callable[[MarketSnapshot], float],
        category: str,
        description: str = "",
        dependencies: list[str] = None,
    ) -> None:
        """Register a new feature."""
        self._features[name] = FeatureDefinition(
            name=name,
            compute_fn=compute_fn,
            category=category,
            description=description,
            dependencies=dependencies or [],
        )
        logger.debug(f"Registered feature: {name}")

    def get(self, name: str) -> Optional[FeatureDefinition]:
        """Get a feature definition by name."""
        return self._features.get(name)

    def list_features(self, category: Optional[str] = None) -> list[str]:
        """List all registered features, optionally filtered by category."""
        if category:
            return [
                name for name, feat in self._features.items()
                if feat.category == category
            ]
        return list(self._features.keys())

    def compute(self, name: str, snapshot: MarketSnapshot) -> float:
        """Compute a single feature."""
        feat = self._features.get(name)
        if not feat:
            raise ValueError(f"Unknown feature: {name}")
        return feat.compute_fn(snapshot)

    def compute_all(
        self,
        snapshot: MarketSnapshot,
        features: Optional[list[str]] = None
    ) -> dict[str, float]:
        """
        Compute multiple features for a snapshot.

        Args:
            snapshot: Market snapshot
            features: List of feature names (None = all)

        Returns:
            Dict of feature name -> value
        """
        feature_names = features or list(self._features.keys())
        results = {}

        for name in feature_names:
            try:
                results[name] = self.compute(name, snapshot)
            except Exception as e:
                logger.warning(f"Failed to compute {name}: {e}")
                results[name] = None

        return results

    def compute_batch(
        self,
        snapshots: list[MarketSnapshot],
        features: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """Compute features for multiple snapshots."""
        return [self.compute_all(s, features) for s in snapshots]


# Global registry instance
_registry = FeatureRegistry()


def register_feature(
    name: str,
    category: str,
    description: str = "",
    dependencies: list[str] = None,
):
    """Decorator to register a feature function."""
    def decorator(fn: Callable[[MarketSnapshot], float]):
        _registry.register(
            name=name,
            compute_fn=fn,
            category=category,
            description=description,
            dependencies=dependencies,
        )
        return fn
    return decorator


def get_registry() -> FeatureRegistry:
    """Get the global feature registry."""
    return _registry


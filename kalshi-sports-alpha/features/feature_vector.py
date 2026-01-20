"""FeatureVector data contract - formal structure for computed features."""

from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime

from kalshi.models import MarketSnapshot
from .registry import get_registry


@dataclass
class FeatureVector:
    """
    Derived feature vector from MarketSnapshot.

    This is the formal data contract for features as specified in Section 5.2.
    All features are numeric, deterministic, and side-agnostic.
    """

    # Core features from spec
    spread: Optional[float] = None
    liquidity_imbalance: Optional[float] = None
    price_impact_per_dollar: Optional[float] = None
    trade_size_zscore: Optional[float] = None
    trade_cluster_score: Optional[float] = None
    price_velocity: Optional[float] = None
    volatility_ratio: Optional[float] = None
    absorption_ratio: Optional[float] = None
    overreaction_score: Optional[float] = None
    rule_complexity_score: Optional[float] = None

    # Additional computed features
    trade_flow_imbalance: Optional[float] = None
    large_trade_ratio: Optional[float] = None
    volume_rate: Optional[float] = None
    kyle_lambda: Optional[float] = None
    hidden_liquidity_score: Optional[float] = None
    settlement_ambiguity: Optional[float] = None
    kickoff_urgency: Optional[float] = None
    time_decay_factor: Optional[float] = None

    # Metadata
    market_id: Optional[str] = None
    snapshot_time: Optional[datetime] = None
    computation_time_ms: Optional[float] = None

    # Raw feature dict for any additional features
    extra_features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}

        # Add core features
        core_fields = [
            "spread", "liquidity_imbalance", "price_impact_per_dollar",
            "trade_size_zscore", "trade_cluster_score", "price_velocity",
            "volatility_ratio", "absorption_ratio", "overreaction_score",
            "rule_complexity_score", "trade_flow_imbalance", "large_trade_ratio",
            "volume_rate", "kyle_lambda", "hidden_liquidity_score",
            "settlement_ambiguity", "kickoff_urgency", "time_decay_factor",
        ]

        for field_name in core_fields:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value

        # Add extra features
        result.update(self.extra_features)

        return result

    def get(self, name: str, default: Any = None) -> Any:
        """Get a feature value by name."""
        if hasattr(self, name):
            value = getattr(self, name)
            return value if value is not None else default
        return self.extra_features.get(name, default)

    def __getitem__(self, name: str) -> Any:
        """Allow dict-like access to features."""
        return self.get(name)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureVector":
        """Create FeatureVector from dictionary."""
        # Known fields
        known_fields = {
            "spread", "liquidity_imbalance", "price_impact_per_dollar",
            "trade_size_zscore", "trade_cluster_score", "price_velocity",
            "volatility_ratio", "absorption_ratio", "overreaction_score",
            "rule_complexity_score", "trade_flow_imbalance", "large_trade_ratio",
            "volume_rate", "kyle_lambda", "hidden_liquidity_score",
            "settlement_ambiguity", "kickoff_urgency", "time_decay_factor",
            "market_id", "snapshot_time", "computation_time_ms",
        }

        kwargs = {}
        extra = {}

        for key, value in data.items():
            if key in known_fields:
                kwargs[key] = value
            elif key != "extra_features":
                extra[key] = value

        kwargs["extra_features"] = extra
        return cls(**kwargs)


def compute_feature_vector(snapshot: MarketSnapshot) -> FeatureVector:
    """
    Compute a complete FeatureVector from a MarketSnapshot.

    Uses the feature registry to compute all registered features,
    then maps them to the formal FeatureVector structure.

    Args:
        snapshot: Market snapshot to compute features from

    Returns:
        FeatureVector with all computed features
    """
    import time
    start_time = time.time()

    registry = get_registry()
    raw_features = registry.compute_all(snapshot)

    # Map registry features to FeatureVector fields
    # Registry names -> FeatureVector field names
    field_mapping = {
        "spread": "spread",
        "depth_imbalance": "liquidity_imbalance",
        "price_impact_100": "price_impact_per_dollar",
        "trade_size_zscore": "trade_size_zscore",
        "trade_clustering": "trade_cluster_score",
        "price_velocity": "price_velocity",
        "volatility_ratio": "volatility_ratio",
        "absorption_ratio": "absorption_ratio",
        "overreaction_score": "overreaction_score",
        "rule_complexity": "rule_complexity_score",
        "trade_flow_imbalance": "trade_flow_imbalance",
        "large_trade_ratio": "large_trade_ratio",
        "volume_rate": "volume_rate",
        "kyle_lambda": "kyle_lambda",
        "hidden_liquidity_score": "hidden_liquidity_score",
        "settlement_ambiguity": "settlement_ambiguity",
        "kickoff_urgency": "kickoff_urgency",
        "time_decay_factor": "time_decay_factor",
    }

    # Build kwargs for FeatureVector
    kwargs = {
        "market_id": snapshot.market_id,
        "snapshot_time": snapshot.snapshot_time,
    }

    extra_features = {}

    for registry_name, value in raw_features.items():
        if registry_name in field_mapping:
            kwargs[field_mapping[registry_name]] = value
        else:
            extra_features[registry_name] = value

    # Add spread from snapshot if not in registry
    if kwargs.get("spread") is None and snapshot.spread is not None:
        kwargs["spread"] = snapshot.spread

    # Add liquidity_imbalance from snapshot if not computed
    if kwargs.get("liquidity_imbalance") is None:
        kwargs["liquidity_imbalance"] = snapshot.depth_imbalance

    kwargs["extra_features"] = extra_features
    kwargs["computation_time_ms"] = (time.time() - start_time) * 1000

    return FeatureVector(**kwargs)


def compute_feature_vectors_batch(
    snapshots: list[MarketSnapshot]
) -> list[FeatureVector]:
    """
    Compute FeatureVectors for multiple snapshots.

    Args:
        snapshots: List of market snapshots

    Returns:
        List of FeatureVectors
    """
    return [compute_feature_vector(s) for s in snapshots]


"""Feature engineering components."""

from .registry import FeatureRegistry, register_feature, get_registry
from .feature_vector import (
    FeatureVector,
    compute_feature_vector,
    compute_feature_vectors_batch,
)

# Import submodules to trigger @register_feature decorators
from . import microstructure
from . import behavioral
from . import temporal
from . import structural

__all__ = [
    "FeatureRegistry",
    "register_feature",
    "get_registry",
    "FeatureVector",
    "compute_feature_vector",
    "compute_feature_vectors_batch",
    "microstructure",
    "behavioral",
    "temporal",
    "structural",
]


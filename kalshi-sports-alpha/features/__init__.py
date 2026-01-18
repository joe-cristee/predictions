"""Feature engineering components."""

from .registry import FeatureRegistry, register_feature

# Import submodules to trigger @register_feature decorators
from . import microstructure
from . import behavioral
from . import temporal
from . import structural

__all__ = [
    "FeatureRegistry",
    "register_feature",
    "microstructure",
    "behavioral",
    "temporal",
    "structural",
]


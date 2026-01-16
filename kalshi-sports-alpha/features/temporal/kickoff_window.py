"""Kickoff window features."""

from typing import Optional
from enum import Enum
from kalshi.models import MarketSnapshot
from features.registry import register_feature


class KickoffRegime(Enum):
    """Defined time regimes relative to kickoff."""
    FAR = 0        # T-24h to T-2h
    APPROACHING = 1  # T-2h to T-10m
    IMMINENT = 2   # T-10m to kickoff
    LIVE = 3       # In-play


@register_feature(
    name="kickoff_regime",
    category="temporal",
    description="Categorical kickoff regime (0-3)"
)
def compute_kickoff_regime(snapshot: MarketSnapshot) -> int:
    """
    Compute kickoff regime as numeric value.

    Returns:
        0 = FAR, 1 = APPROACHING, 2 = IMMINENT, 3 = LIVE
    """
    if snapshot.time_to_kickoff_seconds is None:
        return 0  # Default to FAR if unknown

    seconds = snapshot.time_to_kickoff_seconds

    if seconds < 0:
        return KickoffRegime.LIVE.value
    elif seconds <= 600:  # 10 minutes
        return KickoffRegime.IMMINENT.value
    elif seconds <= 7200:  # 2 hours
        return KickoffRegime.APPROACHING.value
    else:
        return KickoffRegime.FAR.value


@register_feature(
    name="time_urgency",
    category="temporal",
    description="Time urgency score (0-1, higher = closer to kickoff)"
)
def compute_time_urgency(snapshot: MarketSnapshot) -> float:
    """
    Compute time urgency score.

    Captures how close we are to kickoff on a continuous scale.

    Returns:
        Urgency score in range [0, 1]
    """
    if snapshot.time_to_kickoff_seconds is None:
        return 0.0

    seconds = snapshot.time_to_kickoff_seconds

    if seconds < 0:
        return 1.0  # Maximum urgency during live

    # Exponential decay from 24h out
    # At 24h: ~0.0, At 1h: ~0.5, At 10m: ~0.9
    max_seconds = 24 * 3600  # 24 hours
    normalized = max(0, min(1, 1 - seconds / max_seconds))

    # Apply exponential to emphasize close-to-kickoff
    return normalized ** 0.5


@register_feature(
    name="minutes_to_kickoff",
    category="temporal",
    description="Minutes until kickoff (negative if live)"
)
def compute_minutes_to_kickoff(snapshot: MarketSnapshot) -> Optional[float]:
    """
    Compute minutes to kickoff.

    Returns:
        Minutes to kickoff, negative if in-play
    """
    if snapshot.time_to_kickoff_seconds is None:
        return None
    return snapshot.time_to_kickoff_seconds / 60


@register_feature(
    name="is_approaching_kickoff",
    category="temporal",
    description="Binary: within 2 hours of kickoff"
)
def is_approaching_kickoff(snapshot: MarketSnapshot) -> int:
    """Check if within 2 hours of kickoff."""
    if snapshot.time_to_kickoff_seconds is None:
        return 0
    return 1 if 0 < snapshot.time_to_kickoff_seconds <= 7200 else 0


@register_feature(
    name="is_imminent_kickoff",
    category="temporal",
    description="Binary: within 10 minutes of kickoff"
)
def is_imminent_kickoff(snapshot: MarketSnapshot) -> int:
    """Check if within 10 minutes of kickoff."""
    if snapshot.time_to_kickoff_seconds is None:
        return 0
    return 1 if 0 < snapshot.time_to_kickoff_seconds <= 600 else 0


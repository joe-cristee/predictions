"""Time decay features - theta and resolution timing."""

import math
from typing import Optional
from kalshi.models import MarketSnapshot
from features.registry import register_feature


@register_feature(
    name="time_decay",
    category="temporal",
    description="Time decay factor (0-1, accelerates near resolution)"
)
def compute_time_decay(snapshot: MarketSnapshot) -> float:
    """
    Compute time decay factor.

    Models how contract value erodes as resolution approaches.
    Accelerates in final hours.

    Returns:
        Decay factor in range [0, 1]
    """
    if snapshot.time_to_resolution_seconds is None:
        return 0.0

    seconds = snapshot.time_to_resolution_seconds

    if seconds <= 0:
        return 1.0

    # Exponential decay model
    # Half-life of ~6 hours
    half_life = 6 * 3600
    decay = 1 - math.exp(-math.log(2) * (1 - seconds / (24 * 3600)))

    return max(0, min(1, decay))


@register_feature(
    name="theta",
    category="temporal",
    description="Estimated theta (time value decay rate)"
)
def compute_theta(
    snapshot: MarketSnapshot,
    implied_prob: Optional[float] = None
) -> Optional[float]:
    """
    Compute theta - rate of time value decay.

    For binary options, theta depends on:
    - Distance from 50%
    - Time to expiration

    Args:
        snapshot: Market snapshot
        implied_prob: Current implied probability (mid price)

    Returns:
        Theta in cents per hour
    """
    if snapshot.time_to_resolution_seconds is None:
        return None

    prob = implied_prob or snapshot.mid_price
    if prob is None:
        return None

    seconds = snapshot.time_to_resolution_seconds
    if seconds <= 0:
        return None

    hours = seconds / 3600

    # Time value is maximized at 50%, zero at 0% or 100%
    time_value = prob * (1 - prob)

    # Theta = time value / time remaining (simplified)
    # More sophisticated would use Black-Scholes for binaries
    theta = time_value / hours if hours > 0 else 0

    return theta


@register_feature(
    name="resolution_urgency",
    category="temporal",
    description="Urgency score based on resolution time"
)
def compute_resolution_urgency(snapshot: MarketSnapshot) -> float:
    """
    Compute resolution urgency score.

    Similar to kickoff urgency but for resolution timing.

    Returns:
        Urgency score in range [0, 1]
    """
    if snapshot.time_to_resolution_seconds is None:
        return 0.0

    seconds = snapshot.time_to_resolution_seconds

    if seconds <= 0:
        return 1.0

    # Normalize: 24h = 0, 0h = 1
    max_seconds = 24 * 3600
    normalized = max(0, 1 - seconds / max_seconds)

    return normalized


def estimate_final_settlement(
    current_price: float,
    time_to_resolution: float,
    volatility: float
) -> dict[str, float]:
    """
    Estimate probability distribution of final settlement.

    Uses simplified normal distribution model.

    Args:
        current_price: Current mid price
        time_to_resolution: Seconds to resolution
        volatility: Estimated volatility

    Returns:
        Dict with mean, std, prob_yes, prob_no
    """
    # Scale volatility by time
    hours = time_to_resolution / 3600
    scaled_vol = volatility * math.sqrt(hours) if hours > 0 else 0

    return {
        "mean": current_price,
        "std": scaled_vol,
        "prob_yes": current_price,  # Under risk-neutral measure
        "prob_no": 1 - current_price,
    }


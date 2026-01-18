"""Overreaction detection features."""

from typing import Optional
from kalshi.models import MarketSnapshot
from features.registry import register_feature


@register_feature(
    name="overreaction_score",
    category="behavioral",
    description="Score indicating potential overreaction (0-1)"
)
def compute_overreaction_score(snapshot: MarketSnapshot) -> float:
    """
    Compute overreaction score proxy from snapshot data.

    Without historical price data, we use spread and depth as proxies.
    Wide spread + thin depth can indicate overreaction/stress.

    Returns:
        Overreaction score in range [0, 1]
    """
    score = 0.0
    
    # Spread component - wider spreads can indicate uncertainty/overreaction
    spread = snapshot.spread
    if spread is not None:
        # Wide spread (>5 cents) suggests market stress
        spread_score = min(1.0, spread / 0.10)  # 10 cent spread = max score
        score += spread_score * 0.5
    
    # Depth imbalance - extreme imbalance can indicate overreaction
    imbalance = abs(snapshot.depth_imbalance)
    imbalance_score = min(1.0, imbalance * 1.5)  # 0.67 imbalance = max
    score += imbalance_score * 0.5
    
    return min(1.0, score)


@register_feature(
    name="mean_reversion_signal",
    category="behavioral",
    description="Mean reversion signal strength (-1 to 1)"
)
def compute_mean_reversion_signal(snapshot: MarketSnapshot) -> float:
    """
    Compute mean reversion signal proxy.

    Without historical price data, use mid_price distance from 0.5.
    Prices far from 0.5 have less room to move further.

    Returns:
        Signal strength in range [-1, 1]
    """
    if snapshot.mid_price is None:
        return 0.0
    
    # Distance from neutral (0.5)
    # Prices near extremes tend to mean-revert
    deviation = snapshot.mid_price - 0.5
    
    # Signal is opposite to deviation (mean reversion)
    # Large deviation = strong signal
    signal = -deviation * 2  # Scale so 0.25 deviation = 0.5 signal
    
    return max(-1.0, min(1.0, signal))


# Helper functions that require historical data (not registered as features)
def compute_overreaction_score_from_history(
    price_change: float,
    volume_change: float,
    time_window_minutes: float = 30
) -> float:
    """
    Compute overreaction score based on price vs volume.

    High score = large price move without volume confirmation.

    Args:
        price_change: Absolute price change in cents
        volume_change: Volume as multiple of average
        time_window_minutes: Window for measurement

    Returns:
        Overreaction score in range [0, 1]
    """
    if volume_change <= 0:
        return 0.0

    # Ratio of price move to volume
    # Large price move + low volume = potential overreaction
    price_vol_ratio = abs(price_change) / (volume_change + 0.01)

    # Normalize: 5 cent move with 1x volume = 0.5 score
    normalized = min(1.0, price_vol_ratio / 10)

    # Time adjustment: faster moves are more likely overreactions
    time_factor = min(1.0, 30 / (time_window_minutes + 1))

    return normalized * time_factor


def compute_mean_reversion_signal_from_history(
    current_price: float,
    moving_average: float,
    std_dev: float
) -> float:
    """
    Compute mean reversion signal from historical data.

    Positive = price below MA (expect rise)
    Negative = price above MA (expect fall)

    Args:
        current_price: Current mid price
        moving_average: Historical moving average
        std_dev: Standard deviation of prices

    Returns:
        Signal strength in range [-1, 1]
    """
    if std_dev == 0:
        return 0.0

    # Z-score from moving average
    z_score = (current_price - moving_average) / std_dev

    # Convert to signal: large deviation = strong signal
    # Negative because we're looking for reversion (opposite direction)
    signal = -z_score / 2  # Scale so 2 std devs = full signal

    return max(-1.0, min(1.0, signal))


def detect_narrative_move(
    price_velocity: float,
    volume_ratio: float,
    has_news: bool = False
) -> dict[str, any]:
    """
    Detect if price move is narrative-driven vs informed.

    Narrative moves:
    - High velocity
    - Low volume confirmation
    - No external news

    Args:
        price_velocity: Rate of price change
        volume_ratio: Current vs average volume
        has_news: Whether there's relevant external news

    Returns:
        Dict with is_narrative, confidence, direction
    """
    is_narrative = False
    confidence = 0.0

    # High velocity + low volume = narrative
    if abs(price_velocity) > 0.5 and volume_ratio < 1.5:
        is_narrative = True
        confidence = min(1.0, abs(price_velocity) / volume_ratio)

    # News reduces confidence in narrative detection
    if has_news:
        is_narrative = False
        confidence = 0.0

    return {
        "is_narrative": is_narrative,
        "confidence": confidence,
        "direction": "up" if price_velocity > 0 else "down",
        "fade_signal": -price_velocity if is_narrative else 0,
    }


def compute_contrarian_opportunity(
    overreaction_score: float,
    liquidity_score: float,
    time_to_kickoff: float
) -> float:
    """
    Compute composite contrarian opportunity score.

    Best opportunities: high overreaction + good liquidity + time to recover

    Args:
        overreaction_score: From compute_overreaction_score
        liquidity_score: Market liquidity
        time_to_kickoff: Seconds to kickoff

    Returns:
        Opportunity score in range [0, 1]
    """
    # Need enough time for mean reversion
    time_factor = min(1.0, time_to_kickoff / 3600)  # 1 hour minimum

    # Need liquidity to execute
    if liquidity_score < 0.3:
        return 0.0

    return overreaction_score * liquidity_score * time_factor


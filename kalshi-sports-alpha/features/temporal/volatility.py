"""Volatility features."""

import math
from typing import Optional
from kalshi.models import MarketSnapshot, Trade
from features.registry import register_feature


@register_feature(
    name="realized_volatility",
    category="temporal",
    description="Realized volatility from recent price changes"
)
def compute_realized_volatility(snapshot: MarketSnapshot) -> float:
    """
    Compute realized volatility proxy from snapshot.

    Without price history, use spread as volatility proxy.
    Wider spreads often correlate with higher volatility.

    Returns:
        Volatility proxy (0-1 scale)
    """
    spread = snapshot.spread
    if spread is None:
        return 0.0
    
    # Use spread as volatility proxy
    # Normalize: 1 cent spread = 0.1 vol, 10 cent spread = 1.0 vol
    volatility = min(1.0, spread * 10)
    return volatility


@register_feature(
    name="volatility_ratio",
    category="temporal",
    description="Recent vs historical volatility ratio"
)
def compute_volatility_ratio(snapshot: MarketSnapshot) -> float:
    """
    Compute volatility ratio proxy.

    Without historical data, use volume burst as proxy.
    High recent volume vs total suggests volatility spike.

    Returns:
        Volatility ratio proxy (1.0 = normal)
    """
    if snapshot.volume_1h == 0:
        return 1.0
    
    # Compare 5-minute volume to 1-hour volume
    # Expected: 5m is ~8% of 1h volume if uniform
    expected_ratio = 5 / 60  # ~0.083
    
    if snapshot.volume_5m == 0:
        return 1.0
    
    actual_ratio = snapshot.volume_5m / snapshot.volume_1h
    
    # Ratio of actual to expected gives volatility multiplier
    vol_ratio = actual_ratio / expected_ratio
    
    return min(3.0, vol_ratio)  # Cap at 3x


@register_feature(
    name="price_velocity",
    category="temporal",
    description="Rate of price change (cents per minute)"
)
def compute_price_velocity(snapshot: MarketSnapshot) -> float:
    """
    Compute price velocity proxy.

    Without price history, use depth imbalance as directional proxy.
    Strong imbalance suggests price movement in that direction.

    Returns:
        Price velocity proxy (positive = upward pressure)
    """
    # Use depth imbalance as velocity proxy
    # More bid depth suggests upward price pressure
    imbalance = snapshot.depth_imbalance
    
    # Scale to reasonable velocity range (-1 to 1 cents/minute)
    velocity = imbalance * 1.0
    
    return velocity


# Helper functions that require price history (not registered as features)
def compute_realized_volatility_from_history(
    price_history: list[float],
    annualize: bool = False
) -> Optional[float]:
    """
    Compute realized volatility from price history.

    Args:
        price_history: List of prices (oldest to newest)
        annualize: Whether to annualize the volatility

    Returns:
        Realized volatility or None if insufficient data
    """
    if len(price_history) < 2:
        return None

    # Compute log returns
    returns = []
    for i in range(1, len(price_history)):
        if price_history[i-1] > 0 and price_history[i] > 0:
            log_return = math.log(price_history[i] / price_history[i-1])
            returns.append(log_return)

    if not returns:
        return None

    # Standard deviation of returns
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    volatility = math.sqrt(variance)

    if annualize:
        # Assume 5-minute intervals, ~100k intervals per year
        volatility *= math.sqrt(100000)

    return volatility


def compute_price_velocity_from_history(
    prices: list[float],
    timestamps: list[float],  # Unix timestamps
) -> Optional[float]:
    """
    Compute price velocity (rate of change) from history.

    Args:
        prices: Price history
        timestamps: Corresponding timestamps

    Returns:
        Price change per minute
    """
    if len(prices) < 2 or len(timestamps) < 2:
        return None

    price_change = prices[-1] - prices[0]
    time_change = (timestamps[-1] - timestamps[0]) / 60  # Convert to minutes

    if time_change == 0:
        return None

    return price_change / time_change


def compute_volatility_regime(volatility: float) -> str:
    """
    Categorize volatility into regime.

    Args:
        volatility: Realized volatility

    Returns:
        Regime string: 'low', 'normal', 'high', 'extreme'
    """
    if volatility < 0.005:
        return "low"
    elif volatility < 0.015:
        return "normal"
    elif volatility < 0.03:
        return "high"
    else:
        return "extreme"


def compute_intraday_range(
    high: float,
    low: float,
    current: float
) -> dict[str, float]:
    """
    Compute intraday range statistics.

    Returns:
        Dict with range, position in range, etc.
    """
    range_size = high - low

    if range_size == 0:
        position = 0.5
    else:
        position = (current - low) / range_size

    return {
        "range": range_size,
        "position": position,  # 0 = at low, 1 = at high
        "distance_from_high": high - current,
        "distance_from_low": current - low,
    }


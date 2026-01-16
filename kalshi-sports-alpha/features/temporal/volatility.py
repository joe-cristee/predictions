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
def compute_realized_volatility(
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


@register_feature(
    name="volatility_ratio",
    category="temporal",
    description="Recent vs historical volatility ratio"
)
def compute_volatility_ratio(
    recent_prices: list[float],
    historical_prices: list[float]
) -> Optional[float]:
    """
    Compute ratio of recent to historical volatility.

    High ratio suggests volatility spike.

    Args:
        recent_prices: Recent price history (e.g., last hour)
        historical_prices: Longer history (e.g., last day)

    Returns:
        Volatility ratio or None
    """
    recent_vol = compute_realized_volatility(recent_prices)
    historical_vol = compute_realized_volatility(historical_prices)

    if recent_vol is None or historical_vol is None:
        return None

    if historical_vol == 0:
        return None

    return recent_vol / historical_vol


@register_feature(
    name="price_velocity",
    category="temporal",
    description="Rate of price change (cents per minute)"
)
def compute_price_velocity(
    prices: list[float],
    timestamps: list[float],  # Unix timestamps
) -> Optional[float]:
    """
    Compute price velocity (rate of change).

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


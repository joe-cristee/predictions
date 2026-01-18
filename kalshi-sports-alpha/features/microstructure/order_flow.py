"""Order flow features."""

from typing import Optional
from kalshi.models import MarketSnapshot, Trade
from features.registry import register_feature


@register_feature(
    name="trade_flow_imbalance",
    category="microstructure",
    description="Net buy-sell flow imbalance"
)
def compute_trade_flow_imbalance(snapshot: MarketSnapshot) -> float:
    """
    Compute trade flow imbalance proxy from order book depth.

    Without trade history, we use depth imbalance as a proxy.
    Positive = more bid depth (buying pressure)
    Negative = more ask depth (selling pressure)

    Returns:
        Imbalance ratio in range [-1, 1]
    """
    # Use depth imbalance as proxy for flow imbalance
    return snapshot.depth_imbalance


@register_feature(
    name="trade_clustering",
    category="microstructure",
    description="Measure of trade time clustering"
)
def compute_trade_clustering(snapshot: MarketSnapshot) -> float:
    """
    Compute trade clustering score proxy.

    Without trade history, we estimate from volume patterns.
    Higher volume in short windows suggests clustering.

    Returns:
        Clustering score (0-1, higher = more clustered)
    """
    # Without trade history, use volume concentration as proxy
    # If 1-minute volume is high relative to 5-minute, trades are clustered
    if snapshot.volume_5m == 0:
        return 0.0
    
    # Ratio of 1m to 5m volume (expected ~0.2 if uniform)
    volume_ratio = snapshot.volume_1m / snapshot.volume_5m
    
    # If ratio > 0.4, trades are more clustered in recent minute
    clustering = min(1.0, volume_ratio * 2.5)
    return clustering


@register_feature(
    name="large_trade_ratio",
    category="microstructure",
    description="Ratio of volume from large trades"
)
def compute_large_trade_ratio(snapshot: MarketSnapshot) -> float:
    """
    Compute large trade ratio proxy.

    Without trade history, use last_trade_size if available.

    Returns:
        Ratio in range [0, 1]
    """
    if snapshot.last_trade_size is None:
        return 0.0
    
    # If last trade was large (>50 contracts), signal high ratio
    large_threshold = 50
    if snapshot.last_trade_size >= large_threshold:
        return min(1.0, snapshot.last_trade_size / 100)
    return 0.0


# Helper functions that require trade history (not registered as features)
def compute_trade_flow_imbalance_from_trades(
    trades: Optional[list[Trade]] = None
) -> float:
    """
    Compute trade flow imbalance from actual trade history.

    Positive = net buying pressure
    Negative = net selling pressure

    Returns:
        Imbalance ratio in range [-1, 1]
    """
    if not trades:
        return 0.0

    buy_volume = sum(t.count for t in trades if t.is_buyer_initiated)
    sell_volume = sum(t.count for t in trades if t.is_seller_initiated)
    total = buy_volume + sell_volume

    if total == 0:
        return 0.0

    return (buy_volume - sell_volume) / total


def compute_trade_clustering_from_trades(
    trades: list[Trade],
    window_seconds: float = 60.0
) -> float:
    """
    Compute trade clustering score from actual trade history.

    High clustering suggests informed trading.

    Args:
        trades: List of recent trades
        window_seconds: Window to consider

    Returns:
        Clustering score (0-1, higher = more clustered)
    """
    if len(trades) < 2:
        return 0.0

    # Sort by timestamp
    sorted_trades = sorted(trades, key=lambda t: t.timestamp)

    # Compute inter-arrival times
    intervals = []
    for i in range(1, len(sorted_trades)):
        delta = (sorted_trades[i].timestamp - sorted_trades[i-1].timestamp)
        intervals.append(delta.total_seconds())

    if not intervals:
        return 0.0

    # Coefficient of variation (lower = more clustered)
    mean_interval = sum(intervals) / len(intervals)
    if mean_interval == 0:
        return 1.0

    variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
    std_interval = variance ** 0.5
    cv = std_interval / mean_interval

    # Invert and normalize (high clustering = low CV = high score)
    clustering_score = max(0, 1 - cv)
    return min(1.0, clustering_score)


def compute_vwap(trades: list[Trade]) -> Optional[float]:
    """
    Compute volume-weighted average price.

    Args:
        trades: List of trades

    Returns:
        VWAP or None if no trades
    """
    if not trades:
        return None

    total_volume = sum(t.count for t in trades)
    if total_volume == 0:
        return None

    return sum(t.price * t.count for t in trades) / total_volume


def compute_trade_size_zscore(
    trade: Trade,
    recent_trades: list[Trade]
) -> Optional[float]:
    """
    Compute z-score of trade size relative to recent trades.

    Args:
        trade: Trade to evaluate
        recent_trades: Recent trades for baseline

    Returns:
        Z-score or None if insufficient data
    """
    if len(recent_trades) < 10:
        return None

    sizes = [t.count for t in recent_trades]
    mean_size = sum(sizes) / len(sizes)
    variance = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)

    if variance == 0:
        return 0.0

    std_size = variance ** 0.5
    return (trade.count - mean_size) / std_size


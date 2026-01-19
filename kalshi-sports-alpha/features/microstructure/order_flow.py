"""Order flow features."""

from typing import Optional
from kalshi.models import MarketSnapshot, Trade
from features.registry import register_feature


def _get_trade_metrics(ticker: str) -> Optional[dict[str, float]]:
    """
    Get trade metrics from the trade history pipeline if available.

    Returns None if pipeline is not initialized or no data exists.
    """
    try:
        from ingestion.trade_history import get_trade_pipeline
        pipeline = get_trade_pipeline()
        if pipeline is None:
            return None
        return pipeline.compute_trade_metrics(ticker, window_minutes=60)
    except ImportError:
        return None


@register_feature(
    name="trade_flow_imbalance",
    category="microstructure",
    description="Net buy-sell flow imbalance"
)
def compute_trade_flow_imbalance(snapshot: MarketSnapshot) -> float:
    """
    Compute trade flow imbalance from actual trade history.

    Uses real trade data when available, falls back to depth imbalance proxy.
    Positive = net buying pressure
    Negative = net selling pressure

    Returns:
        Imbalance ratio in range [-1, 1]
    """
    # Try to get actual trade data first
    metrics = _get_trade_metrics(snapshot.market_id)
    if metrics and "trade_flow_imbalance" in metrics:
        return metrics["trade_flow_imbalance"]

    # Fall back to depth imbalance as proxy
    return snapshot.depth_imbalance


@register_feature(
    name="trade_clustering",
    category="microstructure",
    description="Measure of trade time clustering"
)
def compute_trade_clustering(snapshot: MarketSnapshot) -> float:
    """
    Compute trade clustering score from actual trade history.

    Uses real trade data when available, falls back to volume-based proxy.
    High clustering suggests informed trading.

    Returns:
        Clustering score (0-1, higher = more clustered)
    """
    # Try to get actual trade data first
    metrics = _get_trade_metrics(snapshot.market_id)
    if metrics and "trade_clustering" in metrics:
        return metrics["trade_clustering"]

    # Fall back to volume concentration as proxy
    if snapshot.volume_5m == 0:
        return 0.0

    volume_ratio = snapshot.volume_1m / snapshot.volume_5m
    clustering = min(1.0, volume_ratio * 2.5)
    return clustering


@register_feature(
    name="large_trade_ratio",
    category="microstructure",
    description="Ratio of volume from large trades"
)
def compute_large_trade_ratio(snapshot: MarketSnapshot) -> float:
    """
    Compute large trade ratio from actual trade history.

    Uses real trade data when available, falls back to last_trade_size proxy.

    Returns:
        Ratio in range [0, 1]
    """
    # Try to get actual trade data first
    metrics = _get_trade_metrics(snapshot.market_id)
    if metrics and "large_trade_ratio" in metrics:
        return metrics["large_trade_ratio"]

    # Fall back to last_trade_size proxy
    if snapshot.last_trade_size is None:
        return 0.0

    large_threshold = 50
    if snapshot.last_trade_size >= large_threshold:
        return min(1.0, snapshot.last_trade_size / 100)
    return 0.0


@register_feature(
    name="price_velocity",
    category="microstructure",
    description="Rate of price change (cents per minute)"
)
def compute_price_velocity(snapshot: MarketSnapshot) -> float:
    """
    Compute price velocity from actual trade history.

    Uses real trade data when available.

    Returns:
        Price velocity in cents per minute
    """
    # Try to get actual trade data first
    metrics = _get_trade_metrics(snapshot.market_id)
    if metrics and "price_velocity" in metrics:
        return metrics["price_velocity"]

    # No proxy available without trade history
    return 0.0


@register_feature(
    name="volume_rate",
    category="microstructure",
    description="Trade rate (trades per minute)"
)
def compute_volume_rate(snapshot: MarketSnapshot) -> float:
    """
    Compute volume/trade rate from actual trade history.

    Returns:
        Trades per minute
    """
    # Try to get actual trade data first
    metrics = _get_trade_metrics(snapshot.market_id)
    if metrics and "volume_rate" in metrics:
        return metrics["volume_rate"]

    # Estimate from snapshot volume data
    # volume_1m gives us a rough trades-per-minute estimate
    return float(snapshot.volume_1m) if snapshot.volume_1m else 0.0


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


"""Liquidity-related features."""

from typing import Optional
from kalshi.models import MarketSnapshot, OrderBook
from features.registry import register_feature


@register_feature(
    name="spread",
    category="microstructure",
    description="Bid-ask spread in cents"
)
def compute_spread(snapshot: MarketSnapshot) -> Optional[float]:
    """
    Compute bid-ask spread.

    Returns:
        Spread in cents, or None if no quotes
    """
    if snapshot.best_bid is None or snapshot.best_ask is None:
        return None
    return snapshot.best_ask - snapshot.best_bid


@register_feature(
    name="spread_pct",
    category="microstructure",
    description="Spread as percentage of mid price"
)
def compute_spread_pct(snapshot: MarketSnapshot) -> Optional[float]:
    """
    Compute spread as percentage of mid price.

    Returns:
        Spread percentage, or None if no mid price
    """
    spread = compute_spread(snapshot)
    if spread is None or snapshot.mid_price is None or snapshot.mid_price == 0:
        return None
    return spread / snapshot.mid_price


@register_feature(
    name="depth_imbalance",
    category="microstructure",
    description="Bid-ask depth imbalance ratio (-1 to 1)"
)
def compute_depth_imbalance(snapshot: MarketSnapshot) -> float:
    """
    Compute order book depth imbalance.

    Positive = more bid depth (bullish)
    Negative = more ask depth (bearish)

    Returns:
        Imbalance ratio in range [-1, 1]
    """
    total_bid = snapshot.total_bid_depth
    total_ask = snapshot.total_ask_depth
    total = total_bid + total_ask

    if total == 0:
        return 0.0

    return (total_bid - total_ask) / total


@register_feature(
    name="liquidity_score",
    category="microstructure",
    description="Composite liquidity score (0-1)"
)
def compute_liquidity_score(snapshot: MarketSnapshot) -> float:
    """
    Compute composite liquidity score.

    Combines spread, depth, and volume into single score.
    Higher = more liquid.

    Returns:
        Score in range [0, 1]
    """
    score = 0.0
    weights_sum = 0.0

    # Spread component (tighter = better)
    spread = compute_spread(snapshot)
    if spread is not None:
        # Normalize: 1 cent spread = 1.0, 10 cent spread = 0.1
        spread_score = max(0, 1 - (spread * 10))
        score += spread_score * 0.4
        weights_sum += 0.4

    # Depth component
    total_depth = snapshot.total_bid_depth + snapshot.total_ask_depth
    if total_depth > 0:
        # Normalize: 1000 contracts = 1.0
        depth_score = min(1.0, total_depth / 1000)
        score += depth_score * 0.3
        weights_sum += 0.3

    # Volume component
    if snapshot.volume_1h > 0:
        # Normalize: 500 contracts/hour = 1.0
        volume_score = min(1.0, snapshot.volume_1h / 500)
        score += volume_score * 0.3
        weights_sum += 0.3

    if weights_sum == 0:
        return 0.0

    return score / weights_sum


def compute_effective_spread(
    orderbook: OrderBook,
    trade_price: float
) -> Optional[float]:
    """
    Compute effective spread from actual trade execution.

    Args:
        orderbook: Order book at time of trade
        trade_price: Actual execution price

    Returns:
        Effective spread (2 * |trade - mid|)
    """
    if orderbook.mid_price is None:
        return None

    return 2 * abs(trade_price - orderbook.mid_price)


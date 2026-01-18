"""Price impact features."""

from typing import Optional
from kalshi.models import MarketSnapshot, OrderBook, Trade
from features.registry import register_feature


@register_feature(
    name="price_impact_100",
    category="microstructure",
    description="Price impact for $100 order"
)
def compute_price_impact(
    snapshot: MarketSnapshot,
    order_size_dollars: float = 100.0
) -> Optional[float]:
    """
    Estimate price impact for a given order size.

    Args:
        snapshot: Market snapshot with depth info
        order_size_dollars: Notional order size

    Returns:
        Estimated price move in cents, or None
    """
    if snapshot.best_ask is None or snapshot.total_ask_depth == 0:
        return None

    # Simplified: assume linear impact based on depth
    # More sophisticated would walk the book
    avg_price = (snapshot.best_bid + snapshot.best_ask) / 2 if snapshot.best_bid else snapshot.best_ask
    contracts = order_size_dollars / avg_price if avg_price > 0 else 0

    if contracts == 0:
        return None

    # Impact = contracts / depth * spread
    spread = snapshot.spread or 0.01
    depth = snapshot.total_ask_depth

    impact = (contracts / depth) * spread if depth > 0 else spread
    return min(impact, 0.50)  # Cap at 50 cents


@register_feature(
    name="kyle_lambda",
    category="microstructure",
    description="Kyle's lambda (price impact coefficient)"
)
def compute_kyle_lambda(snapshot: MarketSnapshot) -> float:
    """
    Estimate Kyle's lambda proxy from snapshot.

    Without trade history, use spread/depth ratio as lambda proxy.
    Higher lambda = higher price impact per unit volume.

    Returns:
        Lambda estimate (higher = more impact)
    """
    spread = snapshot.spread
    depth = snapshot.total_bid_depth + snapshot.total_ask_depth
    
    if spread is None or depth == 0:
        return 0.0
    
    # Lambda proxy: spread per unit depth
    # Tight spread with deep book = low lambda
    # Wide spread with thin book = high lambda
    lambda_proxy = spread / (depth / 100 + 0.01)
    
    return min(1.0, lambda_proxy)


# Helper function that requires trade history
def compute_kyle_lambda_from_trades(
    trades: list[Trade],
    price_changes: list[float]
) -> Optional[float]:
    """
    Estimate Kyle's lambda - price impact per unit of order flow.

    λ = Cov(ΔP, Q) / Var(Q)

    Args:
        trades: Recent trades with signed volume
        price_changes: Corresponding price changes

    Returns:
        Lambda estimate or None if insufficient data
    """
    if len(trades) < 10 or len(price_changes) != len(trades):
        return None

    # Signed order flow (positive = buy, negative = sell)
    order_flow = [
        t.count if t.is_buyer_initiated else -t.count
        for t in trades
    ]

    # Compute covariance and variance
    mean_flow = sum(order_flow) / len(order_flow)
    mean_price = sum(price_changes) / len(price_changes)

    cov = sum(
        (q - mean_flow) * (p - mean_price)
        for q, p in zip(order_flow, price_changes)
    ) / len(order_flow)

    var_flow = sum((q - mean_flow) ** 2 for q in order_flow) / len(order_flow)

    if var_flow == 0:
        return None

    return cov / var_flow


def compute_price_impact_from_book(
    orderbook: OrderBook,
    size: int,
    side: str
) -> Optional[float]:
    """
    Compute exact price impact by walking the order book.

    Args:
        orderbook: Current order book
        size: Number of contracts
        side: 'buy' or 'sell'

    Returns:
        Average execution price minus mid price
    """
    if orderbook.mid_price is None:
        return None

    avg_fill = orderbook.price_impact(size, side)
    if avg_fill is None:
        return None

    return avg_fill - orderbook.mid_price


@register_feature(
    name="price_impact_asymmetry",
    category="microstructure",
    description="Buy vs sell impact asymmetry"
)
def compute_impact_asymmetry(snapshot: MarketSnapshot) -> float:
    """
    Compute asymmetry between buy and sell price impact.

    Positive = easier to buy (more ask depth)
    Negative = easier to sell (more bid depth)

    Returns:
        Asymmetry score in range [-1, 1]
    """
    bid_depth = snapshot.total_bid_depth
    ask_depth = snapshot.total_ask_depth
    total = bid_depth + ask_depth

    if total == 0:
        return 0.0

    # More ask depth = lower buy impact = positive asymmetry
    return (ask_depth - bid_depth) / total


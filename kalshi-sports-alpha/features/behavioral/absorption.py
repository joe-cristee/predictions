"""Order absorption features."""

from typing import Optional
from dataclasses import dataclass
from kalshi.models import MarketSnapshot, Trade, OrderBook
from features.registry import register_feature


@dataclass
class AbsorptionEvent:
    """Represents a detected absorption event."""

    timestamp: float
    side: str  # 'bid' or 'ask'
    volume_absorbed: int
    price_impact: float
    confidence: float


@register_feature(
    name="absorption_ratio",
    category="behavioral",
    description="Volume absorbed vs price impact ratio"
)
def compute_absorption_ratio(
    volume: int,
    price_change: float,
    baseline_impact: Optional[float] = None
) -> float:
    """
    Compute absorption ratio - how much volume moved price.

    High ratio = strong absorption (price held despite volume)
    Low ratio = weak absorption (price moved easily)

    Args:
        volume: Volume traded
        price_change: Absolute price change
        baseline_impact: Expected impact per contract

    Returns:
        Absorption ratio (higher = stronger absorption)
    """
    if volume == 0:
        return 0.0

    if price_change == 0:
        return float("inf")  # Perfect absorption

    # Volume per cent of price move
    ratio = volume / (abs(price_change) * 100 + 0.01)

    # Normalize: 100 contracts per cent = ratio of 1
    return min(10.0, ratio / 100)


def detect_absorption_event(
    trades: list[Trade],
    orderbook_before: OrderBook,
    orderbook_after: OrderBook,
    threshold: float = 2.0
) -> Optional[AbsorptionEvent]:
    """
    Detect significant absorption events.

    Absorption = large volume traded with minimal price impact,
    suggesting a large resting order or informed participant.

    Args:
        trades: Recent trades
        orderbook_before: Order book before trades
        orderbook_after: Order book after trades
        threshold: Minimum absorption ratio to flag

    Returns:
        AbsorptionEvent if detected, None otherwise
    """
    if not trades or orderbook_before.mid_price is None:
        return None

    total_volume = sum(t.count for t in trades)
    price_change = abs(
        (orderbook_after.mid_price or 0) - orderbook_before.mid_price
    )

    ratio = compute_absorption_ratio(total_volume, price_change)

    if ratio < threshold:
        return None

    # Determine which side absorbed
    buy_volume = sum(t.count for t in trades if t.is_buyer_initiated)
    sell_volume = total_volume - buy_volume
    side = "ask" if buy_volume > sell_volume else "bid"

    return AbsorptionEvent(
        timestamp=trades[-1].timestamp.timestamp(),
        side=side,
        volume_absorbed=total_volume,
        price_impact=price_change,
        confidence=min(1.0, ratio / 5),
    )


@register_feature(
    name="hidden_liquidity_score",
    category="behavioral",
    description="Estimated hidden liquidity (0-1)"
)
def compute_hidden_liquidity(
    visible_depth: int,
    recent_absorption: float,
    trade_size_distribution: list[int]
) -> float:
    """
    Estimate hidden (iceberg) liquidity presence.

    High score suggests significant hidden orders.

    Args:
        visible_depth: Visible order book depth
        recent_absorption: Recent absorption ratio
        trade_size_distribution: Recent trade sizes

    Returns:
        Hidden liquidity score in range [0, 1]
    """
    score = 0.0

    # High absorption suggests hidden orders
    if recent_absorption > 2.0:
        score += 0.4 * min(1.0, recent_absorption / 5)

    # Consistent trade sizes suggest algorithmic iceberg
    if trade_size_distribution:
        mean_size = sum(trade_size_distribution) / len(trade_size_distribution)
        variance = sum((s - mean_size) ** 2 for s in trade_size_distribution)
        variance /= len(trade_size_distribution)

        if variance < mean_size * 0.1:  # Low variance = consistent = iceberg
            score += 0.3

    # Large trades relative to visible depth
    if trade_size_distribution and visible_depth > 0:
        max_trade = max(trade_size_distribution)
        if max_trade > visible_depth * 0.5:
            score += 0.3

    return min(1.0, score)


def compute_absorption_asymmetry(
    bid_absorption: float,
    ask_absorption: float
) -> float:
    """
    Compute asymmetry between bid and ask absorption.

    Positive = stronger bid absorption (bullish)
    Negative = stronger ask absorption (bearish)

    Args:
        bid_absorption: Absorption ratio on bid side
        ask_absorption: Absorption ratio on ask side

    Returns:
        Asymmetry score in range [-1, 1]
    """
    total = bid_absorption + ask_absorption
    if total == 0:
        return 0.0

    return (bid_absorption - ask_absorption) / total


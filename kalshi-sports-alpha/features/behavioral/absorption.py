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
def compute_absorption_ratio(snapshot: MarketSnapshot) -> float:
    """
    Compute absorption ratio proxy from snapshot.

    High ratio = strong absorption (price held despite volume)
    Low ratio = weak absorption (price moved easily)

    Uses depth and recent volume as proxy.

    Returns:
        Absorption ratio (higher = stronger absorption)
    """
    # Use depth-to-volume ratio as absorption proxy
    total_depth = snapshot.total_bid_depth + snapshot.total_ask_depth
    recent_volume = snapshot.volume_5m
    
    if recent_volume == 0:
        return 1.0  # No recent volume = stable
    
    if total_depth == 0:
        return 0.0  # No depth = weak absorption
    
    # Higher depth relative to volume = better absorption
    ratio = total_depth / recent_volume
    
    # Normalize: depth = volume means ratio of 1
    return min(10.0, ratio)


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
def compute_hidden_liquidity(snapshot: MarketSnapshot) -> float:
    """
    Estimate hidden (iceberg) liquidity presence.

    Without detailed trade data, use volume vs depth ratio.
    High volume relative to visible depth suggests hidden orders.

    Returns:
        Hidden liquidity score in range [0, 1]
    """
    score = 0.0
    
    visible_depth = snapshot.total_bid_depth + snapshot.total_ask_depth
    recent_volume = snapshot.volume_1h
    
    if visible_depth == 0:
        return 0.0
    
    if recent_volume == 0:
        return 0.0
    
    # High volume relative to depth suggests hidden liquidity
    volume_depth_ratio = recent_volume / visible_depth
    
    if volume_depth_ratio > 2.0:
        score += 0.5 * min(1.0, volume_depth_ratio / 5)
    
    # Large last trade relative to visible depth suggests iceberg
    if snapshot.last_trade_size is not None:
        if snapshot.last_trade_size > visible_depth * 0.3:
            score += 0.3
    
    # Tight spread with volume suggests hidden depth
    spread = snapshot.spread
    if spread is not None and spread < 0.03 and recent_volume > 100:
        score += 0.2

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


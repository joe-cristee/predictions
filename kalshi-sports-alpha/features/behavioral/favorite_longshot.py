"""Favorite-longshot bias features."""

from typing import Optional
from kalshi.models import MarketSnapshot
from features.registry import register_feature


@register_feature(
    name="favorite_longshot_bias",
    category="behavioral",
    description="FLB indicator (-1 to 1, positive = longshot overpriced)"
)
def compute_favorite_longshot_bias(
    kalshi_price: float,
    fair_prob: Optional[float] = None,
    sportsbook_odds: Optional[float] = None
) -> float:
    """
    Compute favorite-longshot bias indicator.

    The FLB suggests:
    - Longshots (low probability) are systematically overpriced
    - Favorites (high probability) are underpriced

    Args:
        kalshi_price: Kalshi implied probability
        fair_prob: Estimated fair probability (if available)
        sportsbook_odds: Sportsbook implied probability

    Returns:
        FLB score: positive = potential fade longshot opportunity
    """
    # If we have external reference, compare directly
    if fair_prob is not None:
        return kalshi_price - fair_prob

    if sportsbook_odds is not None:
        return kalshi_price - sportsbook_odds

    # Without external reference, use empirical FLB curve
    # Research shows ~2-5% bias at extremes
    if kalshi_price < 0.20:
        # Longshot: likely overpriced
        expected_bias = 0.03 * (0.20 - kalshi_price) / 0.20
    elif kalshi_price > 0.80:
        # Favorite: likely underpriced
        expected_bias = -0.03 * (kalshi_price - 0.80) / 0.20
    else:
        expected_bias = 0.0

    return expected_bias


@register_feature(
    name="implied_edge",
    category="behavioral",
    description="Estimated edge from FLB (in cents)"
)
def compute_implied_edge(
    kalshi_price: float,
    external_price: Optional[float] = None
) -> float:
    """
    Compute implied edge from pricing discrepancy.

    Args:
        kalshi_price: Kalshi implied probability
        external_price: External reference probability

    Returns:
        Edge in cents (positive = buy YES, negative = buy NO)
    """
    bias = compute_favorite_longshot_bias(kalshi_price, external_price)

    # Edge = bias adjusted for typical vig
    # Kalshi vig is ~1-2% per side
    vig_adjustment = 0.02

    edge = bias - vig_adjustment if bias > 0 else bias + vig_adjustment
    return edge * 100  # Convert to cents


def identify_mispricing(
    prices: dict[str, float],
    threshold: float = 0.03
) -> list[dict]:
    """
    Identify potential mispricings across related markets.

    Args:
        prices: Dict of market_id -> price
        threshold: Minimum edge to flag

    Returns:
        List of mispricing opportunities
    """
    opportunities = []

    for market_id, price in prices.items():
        edge = compute_implied_edge(price)

        if abs(edge) > threshold * 100:  # Convert threshold to cents
            opportunities.append({
                "market_id": market_id,
                "price": price,
                "edge": edge,
                "direction": "YES" if edge > 0 else "NO",
                "confidence": min(1.0, abs(edge) / 10),  # 10 cent edge = max confidence
            })

    return sorted(opportunities, key=lambda x: -abs(x["edge"]))


def compute_public_bias(
    yes_volume: int,
    no_volume: int,
    yes_price: float
) -> float:
    """
    Estimate public betting bias from volume imbalance.

    Args:
        yes_volume: Volume on YES side
        no_volume: Volume on NO side
        yes_price: Current YES price

    Returns:
        Public bias score (-1 to 1, positive = public on YES)
    """
    total = yes_volume + no_volume
    if total == 0:
        return 0.0

    # Volume share vs fair share based on price
    yes_share = yes_volume / total
    fair_share = yes_price  # In efficient market, volume should match probability

    # Bias = excess volume on one side
    return yes_share - fair_share


"""Cross-market analysis features."""

from typing import Optional
from kalshi.models import MarketSnapshot
from features.registry import register_feature


@register_feature(
    name="cross_market_divergence",
    category="structural",
    description="Divergence from related markets"
)
def compute_cross_market_divergence(
    primary_price: float,
    related_prices: list[float],
    expected_relationship: str = "sum_to_one"
) -> float:
    """
    Compute divergence from related market expectations.

    For mutually exclusive outcomes, prices should sum to ~1.
    Divergence suggests arbitrage or mispricing.

    Args:
        primary_price: Price of market being evaluated
        related_prices: Prices of related markets
        expected_relationship: Type of relationship

    Returns:
        Divergence score (0 = perfectly aligned)
    """
    if expected_relationship == "sum_to_one":
        # Mutually exclusive outcomes should sum to 1
        total = primary_price + sum(related_prices)
        divergence = abs(total - 1.0)
    elif expected_relationship == "complement":
        # YES + NO should equal 1
        if len(related_prices) == 1:
            divergence = abs(primary_price + related_prices[0] - 1.0)
        else:
            divergence = 0.0
    else:
        divergence = 0.0

    return divergence


@register_feature(
    name="correlation_score",
    category="structural",
    description="Price correlation with related markets"
)
def compute_correlation_score(
    price_history: list[float],
    related_history: list[float]
) -> Optional[float]:
    """
    Compute price correlation between markets.

    Args:
        price_history: Historical prices of primary market
        related_history: Historical prices of related market

    Returns:
        Correlation coefficient (-1 to 1)
    """
    if len(price_history) != len(related_history) or len(price_history) < 10:
        return None

    n = len(price_history)
    mean_x = sum(price_history) / n
    mean_y = sum(related_history) / n

    # Covariance
    cov = sum(
        (price_history[i] - mean_x) * (related_history[i] - mean_y)
        for i in range(n)
    ) / n

    # Standard deviations
    std_x = (sum((x - mean_x) ** 2 for x in price_history) / n) ** 0.5
    std_y = (sum((y - mean_y) ** 2 for y in related_history) / n) ** 0.5

    if std_x == 0 or std_y == 0:
        return None

    return cov / (std_x * std_y)


def find_arbitrage_opportunities(
    markets: list[dict],
    threshold: float = 0.02
) -> list[dict]:
    """
    Find potential arbitrage across related markets.

    Args:
        markets: List of market dicts with prices and relationships
        threshold: Minimum divergence to flag

    Returns:
        List of arbitrage opportunities
    """
    opportunities = []

    # Group by event
    by_event = {}
    for m in markets:
        event = m.get("event_id")
        if event:
            by_event.setdefault(event, []).append(m)

    for event_id, event_markets in by_event.items():
        # Check if prices sum to approximately 1
        total_price = sum(m.get("price", 0) for m in event_markets)

        if abs(total_price - 1.0) > threshold:
            opportunities.append({
                "event_id": event_id,
                "markets": event_markets,
                "total_price": total_price,
                "divergence": total_price - 1.0,
                "type": "sum_divergence",
            })

    return opportunities


def compute_implied_correlation(
    moneyline_price: float,
    spread_price: float,
    total_price: float
) -> float:
    """
    Compute implied correlation between game outcomes.

    Different market types on same game should be consistent.

    Args:
        moneyline_price: Team win probability
        spread_price: Spread cover probability
        total_price: Total over probability

    Returns:
        Implied correlation (-1 to 1)
    """
    # Simplified: teams expected to win often cover spreads
    # Correlation = consistency between moneyline and spread
    if moneyline_price > 0.5:
        # Favorite - spread should also be >= 0.5
        consistency = spread_price - (1 - moneyline_price)
    else:
        # Underdog - spread might diverge
        consistency = (1 - spread_price) - moneyline_price

    return max(-1.0, min(1.0, consistency * 2))


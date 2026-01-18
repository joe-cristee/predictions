"""Market rule complexity features."""

import re
from typing import Optional
from kalshi.models import MarketSnapshot
from features.registry import register_feature


@register_feature(
    name="rule_complexity",
    category="structural",
    description="Market rule complexity score (0-1)"
)
def compute_rule_complexity(snapshot: MarketSnapshot) -> float:
    """
    Compute complexity score proxy based on market type.

    Without rule text, use market type as complexity proxy.
    Props and totals tend to have more complex rules.

    Returns:
        Complexity score in range [0, 1]
    """
    # Use market type as complexity proxy
    market_type = snapshot.market_type.lower()
    
    if market_type == "prop":
        return 0.7  # Props often have complex settlement rules
    elif market_type == "total":
        return 0.4  # Totals have overtime considerations
    elif market_type == "moneyline":
        return 0.2  # Moneylines are straightforward
    else:
        return 0.3  # Default medium complexity


# Helper function that requires actual rules text
def compute_rule_complexity_from_text(rules: str) -> float:
    """
    Compute complexity score for market rules.

    Complex rules = harder to price = more mispricing opportunity.

    Args:
        rules: Market rules text

    Returns:
        Complexity score in range [0, 1]
    """
    if not rules:
        return 0.0

    score = 0.0

    # Length factor
    word_count = len(rules.split())
    score += min(0.3, word_count / 200)

    # Conditional language
    conditional_words = ["if", "unless", "except", "provided", "contingent"]
    conditional_count = sum(
        1 for word in rules.lower().split()
        if word in conditional_words
    )
    score += min(0.2, conditional_count * 0.05)

    # Numeric thresholds
    numbers = re.findall(r"\d+\.?\d*", rules)
    score += min(0.2, len(numbers) * 0.03)

    # Time conditions
    time_patterns = ["before", "after", "during", "within", "by"]
    time_count = sum(
        1 for pattern in time_patterns
        if pattern in rules.lower()
    )
    score += min(0.15, time_count * 0.03)

    # Edge cases / exceptions
    edge_words = ["overtime", "extra", "postpone", "cancel", "void"]
    edge_count = sum(
        1 for word in edge_words
        if word in rules.lower()
    )
    score += min(0.15, edge_count * 0.05)

    return min(1.0, score)


def parse_market_rules(rules: str) -> dict:
    """
    Parse market rules into structured components.

    Args:
        rules: Market rules text

    Returns:
        Dict with parsed rule components
    """
    parsed = {
        "raw": rules,
        "thresholds": [],
        "conditions": [],
        "time_constraints": [],
        "edge_cases": [],
    }

    if not rules:
        return parsed

    # Extract numeric thresholds
    threshold_pattern = r"(\d+\.?\d*)\s*(points?|yards?|goals?|runs?|%)"
    for match in re.finditer(threshold_pattern, rules.lower()):
        parsed["thresholds"].append({
            "value": float(match.group(1)),
            "unit": match.group(2),
        })

    # Extract time constraints
    time_pattern = r"(before|after|by|within)\s+(\d+:\d+|\d+\s*(?:am|pm|minutes?|hours?))"
    for match in re.finditer(time_pattern, rules.lower()):
        parsed["time_constraints"].append({
            "type": match.group(1),
            "value": match.group(2),
        })

    # Extract conditions
    condition_pattern = r"if\s+([^,.]+)"
    for match in re.finditer(condition_pattern, rules.lower()):
        parsed["conditions"].append(match.group(1).strip())

    return parsed


def identify_rule_edge_cases(rules: str) -> list[str]:
    """
    Identify potential edge cases in market rules.

    Args:
        rules: Market rules text

    Returns:
        List of identified edge cases
    """
    edge_cases = []

    patterns = {
        "overtime": "May include overtime/extra periods",
        "postpone": "Postponement clause present",
        "cancel": "Cancellation clause present",
        "void": "Void condition exists",
        "official": "Requires official result",
        "protest": "May be affected by protests",
        "weather": "Weather dependency",
        "injury": "Injury-related conditions",
    }

    rules_lower = rules.lower()
    for keyword, description in patterns.items():
        if keyword in rules_lower:
            edge_cases.append(description)

    return edge_cases


@register_feature(
    name="settlement_ambiguity",
    category="structural",
    description="Risk of ambiguous settlement (0-1)"
)
def compute_settlement_ambiguity(snapshot: MarketSnapshot) -> float:
    """
    Compute settlement ambiguity proxy.

    Without rule text, use market type and time as proxies.
    In-play markets and props have higher ambiguity risk.

    Returns:
        Ambiguity score in range [0, 1]
    """
    ambiguity = 0.0
    
    # Props have higher settlement ambiguity
    if snapshot.market_type.lower() == "prop":
        ambiguity += 0.3
    
    # Markets close to kickoff have more settlement edge cases
    if snapshot.time_to_kickoff_seconds is not None:
        if snapshot.time_to_kickoff_seconds < 600:  # 10 minutes
            ambiguity += 0.2
        elif snapshot.time_to_kickoff_seconds < 0:  # Live
            ambiguity += 0.3
    
    return min(1.0, ambiguity)


# Helper function that requires actual rules text
def compute_settlement_ambiguity_from_text(rules: str) -> float:
    """
    Compute risk of ambiguous or disputed settlement.

    Args:
        rules: Market rules text

    Returns:
        Ambiguity score in range [0, 1]
    """
    ambiguity = 0.0

    # Check for ambiguous language
    ambiguous_terms = [
        "discretion", "judgment", "may", "reasonable",
        "approximately", "substantially", "generally",
    ]

    rules_lower = rules.lower()
    for term in ambiguous_terms:
        if term in rules_lower:
            ambiguity += 0.1

    # Check for multiple data sources
    if "official" in rules_lower and "if" in rules_lower:
        ambiguity += 0.15

    # Check for time-sensitive conditions
    if any(word in rules_lower for word in ["deadline", "cutoff", "before"]):
        ambiguity += 0.1

    return min(1.0, ambiguity)


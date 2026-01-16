"""Position sizing logic."""

from dataclasses import dataclass
from typing import Optional
import math

from signals import Signal


@dataclass
class SizingParams:
    """Parameters for position sizing."""

    base_size: float = 100.0  # Base position in dollars
    max_size: float = 500.0  # Maximum position
    min_size: float = 10.0  # Minimum position
    kelly_fraction: float = 0.25  # Fraction of Kelly to use
    confidence_scale: float = 1.0  # Scaling factor for confidence


class PositionSizer:
    """
    Calculate appropriate position sizes.

    Inputs:
    - Signal confidence
    - Liquidity
    - Time to resolution

    Outputs:
    - Suggested max order size
    """

    def __init__(self, params: Optional[SizingParams] = None):
        self.params = params or SizingParams()

    def calculate(
        self,
        signal_confidence: float,
        expected_value: float,
        liquidity_score: float,
        time_to_resolution: Optional[int] = None,
        available_depth: Optional[int] = None,
    ) -> int:
        """
        Calculate position size.

        Args:
            signal_confidence: Confidence in signal (0-1)
            expected_value: Expected value as decimal (e.g., 0.05 = 5%)
            liquidity_score: Market liquidity (0-1)
            time_to_resolution: Seconds until resolution
            available_depth: Available order book depth

        Returns:
            Suggested position size in dollars
        """
        # Start with base size
        size = self.params.base_size

        # Scale by confidence
        confidence_factor = signal_confidence * self.params.confidence_scale
        size *= confidence_factor

        # Kelly criterion adjustment
        if expected_value > 0:
            kelly_size = self._kelly_size(expected_value, signal_confidence)
            size = min(size, kelly_size * self.params.kelly_fraction)

        # Liquidity adjustment
        size *= liquidity_score

        # Time adjustment - reduce size close to resolution
        if time_to_resolution is not None:
            time_factor = self._time_adjustment(time_to_resolution)
            size *= time_factor

        # Depth constraint
        if available_depth is not None:
            max_from_depth = available_depth * 0.1  # Max 10% of depth
            size = min(size, max_from_depth)

        # Apply bounds
        size = max(self.params.min_size, min(self.params.max_size, size))

        return int(size)

    def _kelly_size(self, ev: float, win_prob: float) -> float:
        """
        Calculate Kelly criterion size.

        Kelly = (bp - q) / b
        where b = odds, p = win prob, q = 1-p

        For binary options, simplified to:
        Kelly = 2p - 1 (when odds are even)
        """
        # Adjust win probability for EV
        # This is simplified - full Kelly would use actual odds
        implied_edge = ev / (1 - win_prob) if win_prob < 1 else 0

        kelly = implied_edge * self.params.base_size * 10
        return max(0, kelly)

    def _time_adjustment(self, seconds: int) -> float:
        """
        Adjust size based on time to resolution.

        Reduce size when very close to resolution
        (less time for price to move favorably).
        """
        hours = seconds / 3600

        if hours < 0.5:  # Less than 30 minutes
            return 0.5
        elif hours < 1:
            return 0.7
        elif hours < 2:
            return 0.85
        else:
            return 1.0

    def size_for_target_risk(
        self,
        target_risk: float,
        entry_price: float,
        stop_price: Optional[float] = None
    ) -> int:
        """
        Calculate size for target dollar risk.

        Args:
            target_risk: Maximum dollars to risk
            entry_price: Entry price
            stop_price: Stop loss price (defaults to 0 for binaries)

        Returns:
            Position size in contracts
        """
        if stop_price is None:
            # For binaries, max loss is entry price
            stop_price = 0

        risk_per_contract = entry_price - stop_price
        if risk_per_contract <= 0:
            return 0

        return int(target_risk / risk_per_contract)


def optimal_bet_fraction(
    win_probability: float,
    win_payout: float,
    loss_amount: float = 1.0
) -> float:
    """
    Calculate optimal bet fraction using Kelly criterion.

    Args:
        win_probability: Probability of winning
        win_payout: Payout on win (e.g., 2.0 for even money)
        loss_amount: Amount lost on loss (usually 1.0)

    Returns:
        Optimal fraction of bankroll to bet
    """
    if win_probability <= 0 or win_probability >= 1:
        return 0

    b = win_payout / loss_amount
    p = win_probability
    q = 1 - p

    kelly = (b * p - q) / b

    # Never bet more than the edge suggests
    return max(0, kelly)


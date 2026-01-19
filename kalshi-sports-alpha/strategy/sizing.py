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
        entry_price: float,
        liquidity_score: float,
        time_to_resolution: Optional[int] = None,
        available_depth: Optional[int] = None,
        bankroll: Optional[float] = None,
    ) -> int:
        """
        Calculate position size using Kelly criterion.

        Args:
            signal_confidence: Confidence in signal (0-1), used as win probability estimate
            entry_price: Entry price for the contract (0-1)
            liquidity_score: Market liquidity (0-1)
            time_to_resolution: Seconds until resolution
            available_depth: Available order book depth
            bankroll: Total bankroll for Kelly calculation

        Returns:
            Suggested position size in dollars
        """
        # Estimate win probability from signal confidence and entry price
        # If signal confidence is high and price is low, we have edge
        # Use confidence to adjust our probability estimate above market price
        # win_prob = entry_price + (confidence * edge_scaling)
        # where edge_scaling represents max additional edge we believe we have
        max_edge = 0.10  # Maximum 10% edge over market
        estimated_win_prob = entry_price + (signal_confidence * max_edge)
        estimated_win_prob = min(0.95, max(0.05, estimated_win_prob))  # Clamp to reasonable range

        # Calculate Kelly-optimal size
        size = self._kelly_size(
            win_prob=estimated_win_prob,
            entry_price=entry_price,
            bankroll=bankroll
        )

        # If Kelly returns 0 (no edge), use minimum size scaled by confidence
        if size <= 0:
            size = self.params.min_size * signal_confidence

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

    def _kelly_size(
        self,
        win_prob: float,
        entry_price: float,
        bankroll: Optional[float] = None
    ) -> float:
        """
        Calculate Kelly criterion size for binary options.

        For a binary option bought at price `entry_price`:
        - Win payout: 1 - entry_price (profit per contract)
        - Loss amount: entry_price (cost per contract)
        - Odds b = (1 - entry_price) / entry_price

        Kelly formula: f* = (b * p - q) / b
        where b = odds, p = win probability, q = 1 - p

        Args:
            win_prob: Estimated probability of winning (0-1)
            entry_price: Price paid per contract (0-1)
            bankroll: Total bankroll (defaults to base_size * 10)

        Returns:
            Suggested position size in dollars
        """
        if bankroll is None:
            bankroll = self.params.base_size * 10

        # Validate inputs
        if win_prob <= 0 or win_prob >= 1:
            return 0
        if entry_price <= 0 or entry_price >= 1:
            return 0

        # Calculate odds: profit / risk
        # Buying at entry_price: win gives (1 - entry_price), lose costs entry_price
        b = (1 - entry_price) / entry_price
        p = win_prob
        q = 1 - p

        # Kelly fraction: f* = (bp - q) / b
        kelly_fraction = (b * p - q) / b

        # Only bet if we have positive edge
        if kelly_fraction <= 0:
            return 0

        # Apply fractional Kelly for risk management
        adjusted_fraction = kelly_fraction * self.params.kelly_fraction

        # Convert fraction to dollar size
        kelly_dollars = bankroll * adjusted_fraction

        return max(0, kelly_dollars)

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


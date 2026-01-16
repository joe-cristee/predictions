"""Risk management - Phase 2 stub."""

from dataclasses import dataclass, field
from typing import Optional
import logging


logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Risk limits configuration."""

    # Position limits
    max_position_per_market: float = 500  # Dollars
    max_position_per_event: float = 1000
    max_position_per_league: float = 2000
    max_total_exposure: float = 5000

    # Loss limits
    max_daily_loss: float = 500
    max_weekly_loss: float = 1000
    max_drawdown: float = 0.10  # 10%

    # Order limits
    max_order_size: int = 200  # Contracts
    min_order_size: int = 10

    # Time limits
    min_time_to_kickoff: int = 300  # 5 minutes
    min_time_to_resolution: int = 600  # 10 minutes


@dataclass
class RiskState:
    """Current risk state."""

    daily_pnl: float = 0
    weekly_pnl: float = 0
    total_exposure: float = 0
    exposure_by_league: dict[str, float] = field(default_factory=dict)
    exposure_by_event: dict[str, float] = field(default_factory=dict)
    current_drawdown: float = 0


class RiskManager:
    """
    Real-time risk management.
    
    Phase 2 implementation - currently stubbed.
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.state = RiskState()
        self._halted = False

    def check_order(
        self,
        market_id: str,
        event_id: str,
        league: str,
        size: int,
        price: float,
    ) -> tuple[bool, list[str]]:
        """
        Check if an order passes risk checks.

        Args:
            market_id: Market identifier
            event_id: Event identifier
            league: League code
            size: Order size in contracts
            price: Order price

        Returns:
            (is_allowed, list of violations)
        """
        violations = []
        exposure = size * price

        if self._halted:
            violations.append("trading_halted")

        # Order size limits
        if size > self.limits.max_order_size:
            violations.append(f"order_size: {size} > {self.limits.max_order_size}")
        if size < self.limits.min_order_size:
            violations.append(f"order_size: {size} < {self.limits.min_order_size}")

        # Position limits
        current_market = self.state.exposure_by_event.get(market_id, 0)
        if current_market + exposure > self.limits.max_position_per_market:
            violations.append("max_position_per_market exceeded")

        current_event = self.state.exposure_by_event.get(event_id, 0)
        if current_event + exposure > self.limits.max_position_per_event:
            violations.append("max_position_per_event exceeded")

        current_league = self.state.exposure_by_league.get(league, 0)
        if current_league + exposure > self.limits.max_position_per_league:
            violations.append("max_position_per_league exceeded")

        if self.state.total_exposure + exposure > self.limits.max_total_exposure:
            violations.append("max_total_exposure exceeded")

        # Loss limits
        if self.state.daily_pnl < -self.limits.max_daily_loss:
            violations.append("daily_loss_limit_breached")

        if self.state.weekly_pnl < -self.limits.max_weekly_loss:
            violations.append("weekly_loss_limit_breached")

        if self.state.current_drawdown > self.limits.max_drawdown:
            violations.append("max_drawdown_breached")

        return len(violations) == 0, violations

    def update_exposure(
        self,
        event_id: str,
        league: str,
        delta: float
    ) -> None:
        """Update exposure after a fill."""
        self.state.exposure_by_event[event_id] = (
            self.state.exposure_by_event.get(event_id, 0) + delta
        )
        self.state.exposure_by_league[league] = (
            self.state.exposure_by_league.get(league, 0) + delta
        )
        self.state.total_exposure += delta

    def update_pnl(self, pnl: float) -> None:
        """Update P&L tracking."""
        self.state.daily_pnl += pnl
        self.state.weekly_pnl += pnl

        # Check for auto-halt conditions
        if self.state.daily_pnl < -self.limits.max_daily_loss:
            self.halt_trading("Daily loss limit breached")

    def halt_trading(self, reason: str) -> None:
        """Halt all trading."""
        self._halted = True
        logger.critical(f"TRADING HALTED: {reason}")

    def resume_trading(self) -> None:
        """Resume trading after halt."""
        self._halted = False
        logger.info("Trading resumed")

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of day)."""
        self.state.daily_pnl = 0
        if self._halted and self.state.daily_pnl >= -self.limits.max_daily_loss:
            self._halted = False

    def reset_weekly(self) -> None:
        """Reset weekly counters (call at start of week)."""
        self.state.weekly_pnl = 0


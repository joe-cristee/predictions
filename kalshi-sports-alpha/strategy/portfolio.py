"""Portfolio management - correlation and exposure control."""

from dataclasses import dataclass, field
from typing import Optional

from .ranker import Recommendation


@dataclass
class PortfolioPosition:
    """Represents a position in the portfolio."""

    market_id: str
    event_id: str
    league: str
    direction: str
    size: int
    entry_price: float
    current_price: Optional[float] = None

    @property
    def pnl(self) -> Optional[float]:
        """Unrealized P&L."""
        if self.current_price is None:
            return None
        return (self.current_price - self.entry_price) * self.size

    @property
    def exposure(self) -> float:
        """Dollar exposure."""
        return self.size * self.entry_price


@dataclass
class PortfolioLimits:
    """Portfolio risk limits."""

    max_total_exposure: float = 5000  # Total dollars at risk
    max_per_market: float = 500  # Per market
    max_per_event: float = 1000  # Per event (game)
    max_per_league: float = 2000  # Per league
    max_correlated: float = 1500  # Highly correlated positions


class PortfolioManager:
    """
    Manage portfolio correlation and exposure.

    Avoids multiple bets on same game outcome.
    Penalizes highly correlated contracts.
    """

    def __init__(self, limits: Optional[PortfolioLimits] = None):
        self.limits = limits or PortfolioLimits()
        self.positions: list[PortfolioPosition] = []

    def add_position(self, position: PortfolioPosition) -> None:
        """Add a position to the portfolio."""
        self.positions.append(position)

    def clear(self) -> None:
        """Clear all positions."""
        self.positions.clear()

    @property
    def total_exposure(self) -> float:
        """Total portfolio exposure."""
        return sum(p.exposure for p in self.positions)

    def exposure_by_league(self) -> dict[str, float]:
        """Exposure grouped by league."""
        by_league = {}
        for p in self.positions:
            by_league[p.league] = by_league.get(p.league, 0) + p.exposure
        return by_league

    def exposure_by_event(self) -> dict[str, float]:
        """Exposure grouped by event."""
        by_event = {}
        for p in self.positions:
            by_event[p.event_id] = by_event.get(p.event_id, 0) + p.exposure
        return by_event

    def check_limits(self, rec: Recommendation) -> tuple[bool, list[str]]:
        """
        Check if recommendation fits within limits.

        Args:
            rec: Recommendation to check

        Returns:
            (is_allowed, list of limit violations)
        """
        violations = []
        proposed_exposure = rec.entry_price * rec.max_size

        # Total exposure
        if self.total_exposure + proposed_exposure > self.limits.max_total_exposure:
            violations.append(
                f"total_exposure: {self.total_exposure + proposed_exposure:.0f} > {self.limits.max_total_exposure}"
            )

        # Per-market
        market_exposure = sum(
            p.exposure for p in self.positions if p.market_id == rec.market_id
        )
        if market_exposure + proposed_exposure > self.limits.max_per_market:
            violations.append(f"market_exposure: exceeds {self.limits.max_per_market}")

        # Per-event
        event_exposure = sum(
            p.exposure for p in self.positions if p.event_id == rec.event_id
        )
        if event_exposure + proposed_exposure > self.limits.max_per_event:
            violations.append(f"event_exposure: exceeds {self.limits.max_per_event}")

        # Per-league
        league_exposure = sum(
            p.exposure for p in self.positions if p.league == rec.league
        )
        if league_exposure + proposed_exposure > self.limits.max_per_league:
            violations.append(f"league_exposure: exceeds {self.limits.max_per_league}")

        return len(violations) == 0, violations

    def adjust_for_correlation(
        self,
        recommendations: list[Recommendation]
    ) -> list[Recommendation]:
        """
        Adjust recommendations for correlation.

        Penalizes/removes recommendations correlated with existing positions.

        Args:
            recommendations: List of recommendations

        Returns:
            Filtered and adjusted recommendations
        """
        adjusted = []

        for rec in recommendations:
            # Check if we already have position in this event
            event_positions = [
                p for p in self.positions if p.event_id == rec.event_id
            ]

            if event_positions:
                # Check for conflicting directions
                same_direction = any(
                    p.direction == rec.contract for p in event_positions
                )
                if same_direction:
                    # Already exposed this direction, reduce size
                    rec.max_size = int(rec.max_size * 0.5)
                    rec.risk_flags.append("correlated_position")
                else:
                    # Opposite direction - could be hedge or conflict
                    rec.risk_flags.append("opposite_position_exists")

            # Check limits
            allowed, violations = self.check_limits(rec)
            if not allowed:
                rec.risk_flags.extend(violations)
                # Reduce size to fit
                rec.max_size = self._size_to_fit(rec)

            if rec.max_size >= 10:  # Minimum viable size
                adjusted.append(rec)

        return adjusted

    def _size_to_fit(self, rec: Recommendation) -> int:
        """Calculate maximum size that fits within limits."""
        available_total = self.limits.max_total_exposure - self.total_exposure
        available_event = self.limits.max_per_event - sum(
            p.exposure for p in self.positions if p.event_id == rec.event_id
        )
        available_league = self.limits.max_per_league - sum(
            p.exposure for p in self.positions if p.league == rec.league
        )

        available = min(
            available_total,
            available_event,
            available_league,
            self.limits.max_per_market,
        )

        if available <= 0 or rec.entry_price <= 0:
            return 0

        return int(available / rec.entry_price)


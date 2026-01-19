"""Recommendation ranking - EV and confidence based ranking."""

from dataclasses import dataclass, field
from typing import Optional, Any

from signals import SignalDirection
from .aggregator import AggregatedSignal


@dataclass
class CandidateOpportunity:
    """
    All evaluated opportunities, whether recommended or not.
    
    Used for the watchlist to show near-miss opportunities.
    """
    
    market_id: str
    event_id: str
    direction: str  # "YES" or "NO"
    entry_price: float
    expected_value: float
    confidence: float
    signals: list[str]
    rejection_reasons: list[str]  # Empty if recommended
    rank_score: float  # For sorting watchlist
    
    # Display info
    league: str = ""
    matchup: str = ""
    market_title: str = ""
    
    # Thresholds that were applied (for display)
    ev_threshold: float = 0.0
    confidence_threshold: float = 0.0
    
    @property
    def is_recommended(self) -> bool:
        """Returns True if this candidate passed all filters."""
        return len(self.rejection_reasons) == 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "market_id": self.market_id,
            "event_id": self.event_id,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "expected_value": self.expected_value,
            "confidence": self.confidence,
            "signals": self.signals,
            "rejection_reasons": self.rejection_reasons,
            "rank_score": self.rank_score,
            "league": self.league,
            "matchup": self.matchup,
            "is_recommended": self.is_recommended,
        }


@dataclass
class Recommendation:
    """
    Final output delivered to the user.

    Contains all information needed to make a trading decision.
    """

    market_id: str
    event_id: str
    contract: str  # "YES" or "NO"
    entry_price: float
    max_size: int  # In contracts
    expected_value: float  # As percentage
    time_to_resolution: Optional[int]  # Seconds
    contributing_signals: list[str]
    risk_flags: list[str] = field(default_factory=list)

    # Display info
    league: str = ""
    matchup: str = ""
    market_title: str = ""

    # Scores
    rank_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "market_id": self.market_id,
            "event_id": self.event_id,
            "contract": self.contract,
            "entry_price": self.entry_price,
            "max_size": self.max_size,
            "expected_value": self.expected_value,
            "time_to_resolution": self.time_to_resolution,
            "contributing_signals": self.contributing_signals,
            "risk_flags": self.risk_flags,
            "league": self.league,
            "matchup": self.matchup,
            "rank_score": self.rank_score,
        }


class RecommendationRanker:
    """
    Rank and filter recommendations.

    Combines EV, confidence, liquidity, and timing.
    """

    def __init__(
        self,
        min_ev: float = 0.02,  # 2% minimum EV
        min_confidence: float = 0.3,
        max_recommendations: int = 10,
        ev_weight: float = 0.4,
        confidence_weight: float = 0.3,
        liquidity_weight: float = 0.2,
        timing_weight: float = 0.1,
    ):
        self.min_ev = min_ev
        self.min_confidence = min_confidence
        self.max_recommendations = max_recommendations

        # Ranking weights
        self.ev_weight = ev_weight
        self.confidence_weight = confidence_weight
        self.liquidity_weight = liquidity_weight
        self.timing_weight = timing_weight

    def _calculate_expected_value(
        self,
        agg: AggregatedSignal,
        entry_price: float,
        market: dict
    ) -> float:
        """
        Calculate expected value using dynamic vig and signal-derived edge.

        EV = (estimated_win_prob * win_payout) - (estimated_loss_prob * loss_amount) - transaction_costs

        For binary options:
        - Win payout = 1 - entry_price (profit per contract)
        - Loss amount = entry_price (cost per contract)

        Args:
            agg: Aggregated signal with score and confidence
            entry_price: Price to enter the position
            market: Market data including spread

        Returns:
            Expected value as a decimal (e.g., 0.05 = 5% EV)
        """
        # Dynamic vig calculation from spread
        # Spread represents the round-trip cost (bid-ask difference)
        spread = market.get("spread", 0.02)
        vig = spread / 2  # Half spread is our entry cost

        # Estimate our edge over the market
        # Signal score (0-1) represents strength, agreement ratio boosts confidence
        # Max edge we claim is 10% over market - being conservative
        max_edge = 0.10
        signal_edge = agg.aggregate_score * max_edge

        # Agreement ratio scales our confidence in the edge
        # Full agreement (1.0) = full edge, split signals = reduced edge
        agreement_scaling = 0.5 + 0.5 * agg.agreement_ratio
        estimated_edge = signal_edge * agreement_scaling

        # Our estimated win probability = market implied prob + our edge
        market_implied_prob = entry_price
        estimated_win_prob = min(0.95, market_implied_prob + estimated_edge)

        # Calculate EV
        # EV = P(win) * profit_if_win - P(lose) * loss_if_lose - vig
        win_profit = 1 - entry_price  # Payout is $1, we paid entry_price
        loss_amount = entry_price  # We lose our stake

        gross_ev = (estimated_win_prob * win_profit) - ((1 - estimated_win_prob) * loss_amount)

        # Subtract transaction costs (vig)
        net_ev = gross_ev - vig

        return net_ev

    def rank(
        self,
        aggregated_signals: list[AggregatedSignal],
        market_data: dict[str, dict],
    ) -> list[Recommendation]:
        """
        Create and rank recommendations.

        Args:
            aggregated_signals: Aggregated signals by market
            market_data: Market metadata (prices, liquidity, etc.)

        Returns:
            Ranked list of recommendations
        """
        recommendations = []

        for agg in aggregated_signals:
            market = market_data.get(agg.market_id, {})

            # Get entry price and spread for vig calculation
            if agg.direction == SignalDirection.YES:
                entry_price = market.get("yes_ask", 0.5)
            else:
                entry_price = market.get("no_ask", 0.5)

            # Calculate EV using dynamic vig and signal-derived edge
            ev = self._calculate_expected_value(agg, entry_price, market)

            if ev < self.min_ev:
                continue

            if agg.confidence < self.min_confidence:
                continue

            # Create recommendation
            rec = Recommendation(
                market_id=agg.market_id,
                event_id=market.get("event_id", ""),
                contract=agg.direction.value,
                entry_price=entry_price,
                max_size=self._calculate_max_size(agg, market),
                expected_value=ev,
                time_to_resolution=market.get("time_to_resolution"),
                contributing_signals=[s.name for s in agg.contributing_signals],
                risk_flags=self._identify_risks(agg, market),
                league=market.get("league", ""),
                matchup=market.get("matchup", ""),
                market_title=market.get("title", ""),
                confidence=agg.confidence,
            )

            # Calculate rank score
            rec.rank_score = self._calculate_rank_score(rec, market)
            recommendations.append(rec)

        # Sort by rank score
        recommendations.sort(key=lambda r: -r.rank_score)

        return recommendations[: self.max_recommendations]

    def rank_all(
        self,
        aggregated_signals: list[AggregatedSignal],
        market_data: dict[str, dict],
    ) -> tuple[list[Recommendation], list[CandidateOpportunity]]:
        """
        Create and rank recommendations, returning both approved and near-miss candidates.

        Args:
            aggregated_signals: Aggregated signals by market
            market_data: Market metadata (prices, liquidity, etc.)

        Returns:
            Tuple of (recommendations, watchlist_candidates)
            - recommendations: Opportunities that passed all filters
            - watchlist_candidates: All other opportunities, sorted by potential
        """
        recommendations = []
        watchlist = []

        for agg in aggregated_signals:
            market = market_data.get(agg.market_id, {})

            # Get entry price
            if agg.direction == SignalDirection.YES:
                entry_price = market.get("yes_ask", 0.5)
            else:
                entry_price = market.get("no_ask", 0.5)

            # Calculate EV
            ev = self._calculate_expected_value(agg, entry_price, market)

            # Track rejection reasons
            rejection_reasons = []
            
            if ev < self.min_ev:
                rejection_reasons.append(f"EV below threshold ({ev*100:.1f}% < {self.min_ev*100:.1f}%)")

            if agg.confidence < self.min_confidence:
                rejection_reasons.append(f"Confidence below threshold ({agg.confidence:.0%} < {self.min_confidence:.0%})")

            # Calculate rank score for ordering
            temp_rec = Recommendation(
                market_id=agg.market_id,
                event_id=market.get("event_id", ""),
                contract=agg.direction.value,
                entry_price=entry_price,
                max_size=self._calculate_max_size(agg, market),
                expected_value=ev,
                time_to_resolution=market.get("time_to_resolution"),
                contributing_signals=[s.name for s in agg.contributing_signals],
                risk_flags=self._identify_risks(agg, market),
                league=market.get("league", ""),
                matchup=market.get("matchup", ""),
                market_title=market.get("title", ""),
                confidence=agg.confidence,
            )
            rank_score = self._calculate_rank_score(temp_rec, market)

            if not rejection_reasons:
                # Passed all filters - add to recommendations
                temp_rec.rank_score = rank_score
                recommendations.append(temp_rec)
            else:
                # Create watchlist candidate
                candidate = CandidateOpportunity(
                    market_id=agg.market_id,
                    event_id=market.get("event_id", ""),
                    direction=agg.direction.value,
                    entry_price=entry_price,
                    expected_value=ev,
                    confidence=agg.confidence,
                    signals=[s.name for s in agg.contributing_signals],
                    rejection_reasons=rejection_reasons,
                    rank_score=rank_score,
                    league=market.get("league", ""),
                    matchup=market.get("matchup", ""),
                    market_title=market.get("title", ""),
                    ev_threshold=self.min_ev,
                    confidence_threshold=self.min_confidence,
                )
                watchlist.append(candidate)

        # Sort recommendations by rank score
        recommendations.sort(key=lambda r: -r.rank_score)
        
        # Sort watchlist by rank score (best near-misses first)
        watchlist.sort(key=lambda c: -c.rank_score)

        return (
            recommendations[: self.max_recommendations],
            watchlist
        )

    def _calculate_rank_score(
        self,
        rec: Recommendation,
        market: dict
    ) -> float:
        """Calculate composite ranking score."""
        # EV component (normalized to 0-1)
        ev_score = min(1, rec.expected_value / 0.10)  # 10% EV = max

        # Confidence component
        conf_score = rec.confidence

        # Liquidity component
        liquidity = market.get("liquidity_score", 0.5)

        # Timing component (prefer imminent kickoffs)
        time_to_kickoff = market.get("time_to_kickoff", 86400)
        timing_score = max(0, 1 - time_to_kickoff / 7200)  # 2 hour scale

        return (
            self.ev_weight * ev_score
            + self.confidence_weight * conf_score
            + self.liquidity_weight * liquidity
            + self.timing_weight * timing_score
        )

    def _calculate_max_size(
        self,
        agg: AggregatedSignal,
        market: dict
    ) -> int:
        """Calculate maximum position size."""
        # Base size from confidence
        base_size = int(100 * agg.confidence)  # $100 at max confidence

        # Adjust for liquidity
        liquidity = market.get("liquidity_score", 0.5)
        size = int(base_size * liquidity)

        # Cap at available depth
        depth = market.get("available_depth", 1000)
        size = min(size, int(depth * 0.1))  # Max 10% of depth

        return max(10, size)  # Minimum $10

    def _identify_risks(
        self,
        agg: AggregatedSignal,
        market: dict
    ) -> list[str]:
        """Identify risk flags for recommendation."""
        risks = []

        # Low liquidity
        if market.get("liquidity_score", 1) < 0.3:
            risks.append("low_liquidity")

        # Wide spread
        if market.get("spread", 0) > 0.05:
            risks.append("wide_spread")

        # Single signal
        if agg.signal_count == 1:
            risks.append("single_signal")

        # Low agreement
        if agg.agreement_ratio < 0.7:
            risks.append("signal_disagreement")

        # Close to resolution
        time_left = market.get("time_to_resolution", 86400)
        if time_left < 1800:  # 30 minutes
            risks.append("near_resolution")

        return risks


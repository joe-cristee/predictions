"""Pipeline statistics collection for reporting and analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import defaultdict

from kalshi.models import MarketSnapshot
from signals import Signal


@dataclass
class PipelineStats:
    """
    Collects statistics from each pipeline stage.
    
    Used by both CLI and dashboard to show comprehensive pipeline analysis
    even when no recommendations are generated.
    """
    
    # Stage 1: Markets polled
    markets_polled: int = 0
    markets_by_league: dict[str, int] = field(default_factory=dict)
    snapshots: list[MarketSnapshot] = field(default_factory=list)
    
    # Stage 2: Signals generated
    signals_generated: int = 0
    signals_by_type: dict[str, int] = field(default_factory=dict)  # signal_name -> count
    signals_by_market: dict[str, list[Signal]] = field(default_factory=dict)  # market_id -> signals
    all_signals: list[Signal] = field(default_factory=list)
    
    # Stage 3: Aggregation
    markets_with_signals: int = 0  # Markets that have at least 1 signal
    markets_aggregated: int = 0  # Markets that passed min_signals requirement
    aggregation_dropoff: int = 0  # Markets dropped due to insufficient signals
    
    # Stage 4: Filtering (from ranker)
    candidates_evaluated: int = 0
    filtered_by_ev: int = 0
    filtered_by_confidence: int = 0
    recommendations_count: int = 0
    watchlist_count: int = 0
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def funnel(self) -> list[tuple[str, int, str]]:
        """
        Pipeline funnel data for visualization.
        
        Returns list of (stage_name, count, description) tuples.
        """
        return [
            ("Markets Polled", self.markets_polled, f"{self.markets_polled} sports markets"),
            ("Signals Generated", self.signals_generated, f"{self.signals_generated} signals from {self.markets_with_signals} markets"),
            ("Aggregated", self.markets_aggregated, f"{self.markets_aggregated} markets passed aggregation"),
            ("Recommendations", self.recommendations_count, f"{self.recommendations_count} actionable bets"),
            ("Watchlist", self.watchlist_count, f"{self.watchlist_count} near-miss opportunities"),
        ]
    
    @property
    def conversion_rate(self) -> float:
        """Percentage of polled markets that became recommendations."""
        if self.markets_polled == 0:
            return 0.0
        return (self.recommendations_count / self.markets_polled) * 100
    
    @property
    def signal_rate(self) -> float:
        """Percentage of markets that generated at least one signal."""
        if self.markets_polled == 0:
            return 0.0
        return (self.markets_with_signals / self.markets_polled) * 100
    
    @property
    def aggregation_pass_rate(self) -> float:
        """Percentage of signal-bearing markets that passed aggregation."""
        if self.markets_with_signals == 0:
            return 0.0
        return (self.markets_aggregated / self.markets_with_signals) * 100
    
    @property
    def total_volume(self) -> int:
        """Sum of volume across all polled markets."""
        return sum(s.volume_total for s in self.snapshots)
    
    @property
    def avg_spread(self) -> Optional[float]:
        """Average spread across markets with valid spreads."""
        spreads = [s.spread for s in self.snapshots if s.spread is not None]
        if not spreads:
            return None
        return sum(spreads) / len(spreads)
    
    @property
    def total_depth(self) -> int:
        """Sum of bid + ask depth across all markets."""
        return sum(s.total_bid_depth + s.total_ask_depth for s in self.snapshots)
    
    def get_filtering_breakdown(self) -> dict[str, int]:
        """Get breakdown of why candidates were filtered."""
        return {
            "Passed (Recommendations)": self.recommendations_count,
            "EV Below Threshold": self.filtered_by_ev,
            "Confidence Below Threshold": self.filtered_by_confidence,
            "Insufficient Signals": self.aggregation_dropoff,
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "markets_polled": self.markets_polled,
            "markets_by_league": self.markets_by_league,
            "signals_generated": self.signals_generated,
            "signals_by_type": self.signals_by_type,
            "markets_with_signals": self.markets_with_signals,
            "markets_aggregated": self.markets_aggregated,
            "aggregation_dropoff": self.aggregation_dropoff,
            "candidates_evaluated": self.candidates_evaluated,
            "filtered_by_ev": self.filtered_by_ev,
            "filtered_by_confidence": self.filtered_by_confidence,
            "recommendations_count": self.recommendations_count,
            "watchlist_count": self.watchlist_count,
            "conversion_rate": self.conversion_rate,
            "signal_rate": self.signal_rate,
            "total_volume": self.total_volume,
            "avg_spread": self.avg_spread,
            "total_depth": self.total_depth,
        }


class PipelineStatsCollector:
    """
    Helper class to collect pipeline stats during execution.
    
    Usage:
        collector = PipelineStatsCollector()
        collector.record_snapshots(snapshots)
        collector.record_signals(signals_by_market)
        collector.record_aggregation(aggregated, dropped)
        collector.record_filtering(recs, watchlist, filtered_ev, filtered_conf)
        stats = collector.finalize()
    """
    
    def __init__(self):
        self._stats = PipelineStats()
    
    def record_snapshots(self, snapshots: list[MarketSnapshot]) -> None:
        """Record polled market snapshots."""
        self._stats.snapshots = snapshots
        self._stats.markets_polled = len(snapshots)
        
        # Count by league
        league_counts = defaultdict(int)
        for snapshot in snapshots:
            league = snapshot.league or "Unknown"
            league_counts[league] += 1
        self._stats.markets_by_league = dict(league_counts)
    
    def record_signals(self, signals_by_market: dict[str, list[Signal]]) -> None:
        """Record generated signals."""
        self._stats.signals_by_market = signals_by_market
        self._stats.markets_with_signals = len(signals_by_market)
        
        # Flatten and count
        all_signals = []
        signal_type_counts = defaultdict(int)
        
        for market_id, signals in signals_by_market.items():
            for signal in signals:
                all_signals.append(signal)
                signal_type_counts[signal.name] += 1
        
        self._stats.all_signals = all_signals
        self._stats.signals_generated = len(all_signals)
        self._stats.signals_by_type = dict(signal_type_counts)
    
    def record_aggregation(self, aggregated_count: int, dropped_count: int) -> None:
        """Record aggregation results."""
        self._stats.markets_aggregated = aggregated_count
        self._stats.aggregation_dropoff = dropped_count
    
    def record_filtering(
        self,
        recommendations_count: int,
        watchlist_count: int,
        filtered_by_ev: int = 0,
        filtered_by_confidence: int = 0
    ) -> None:
        """Record filtering/ranking results."""
        self._stats.recommendations_count = recommendations_count
        self._stats.watchlist_count = watchlist_count
        self._stats.filtered_by_ev = filtered_by_ev
        self._stats.filtered_by_confidence = filtered_by_confidence
        self._stats.candidates_evaluated = recommendations_count + watchlist_count
    
    def finalize(self) -> PipelineStats:
        """Finalize and return the collected stats."""
        self._stats.timestamp = datetime.now()
        return self._stats


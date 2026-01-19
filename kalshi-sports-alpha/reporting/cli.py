"""CLI terminal output for recommendations."""

from typing import Optional, TYPE_CHECKING
from datetime import datetime

from strategy.ranker import Recommendation, CandidateOpportunity

if TYPE_CHECKING:
    from .pipeline_stats import PipelineStats


class CLIReporter:
    """Terminal output for bet recommendations."""

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors

    def print_recommendations(
        self,
        recommendations: list[Recommendation],
        title: str = "Bet Recommendations"
    ) -> None:
        """
        Print recommendations as formatted table.

        Args:
            recommendations: List of recommendations to display
            title: Table title
        """
        if not recommendations:
            print("\nNo recommendations at this time.\n")
            return

        print(f"\n{'='*70}")
        print(f" {title}")
        print(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        for i, rec in enumerate(recommendations, 1):
            self._print_recommendation(i, rec)

        print(f"\n{'='*70}")
        print(f" Total recommendations: {len(recommendations)}")
        print(f"{'='*70}\n")

    def _print_recommendation(self, rank: int, rec: Recommendation) -> None:
        """Print a single recommendation."""
        # Header
        header = f"#{rank} | {rec.league} | {rec.matchup or rec.market_id}"
        print(self._colorize(header, "bold"))
        print("-" * 60)

        # Contract details
        print(f"  Contract: {rec.contract} @ {rec.entry_price:.2f}")
        print(f"  EV (adj): {rec.expected_value*100:+.1f}%")
        print(f"  Max Size: ${rec.max_size}")

        # Signals
        signals_str = ", ".join(rec.contributing_signals)
        print(f"  Signals: {signals_str}")

        # Risk flags
        if rec.risk_flags:
            flags_str = ", ".join(rec.risk_flags)
            print(f"  {self._colorize('Risks:', 'yellow')} {flags_str}")

        # Time
        if rec.time_to_resolution:
            hours = rec.time_to_resolution / 3600
            print(f"  Time to resolution: {hours:.1f}h")

        print()

    def _colorize(self, text: str, color: str) -> str:
        """Apply ANSI color codes if enabled."""
        if not self.use_colors:
            return text

        colors = {
            "bold": "\033[1m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "blue": "\033[94m",
            "reset": "\033[0m",
        }

        code = colors.get(color, "")
        reset = colors["reset"]
        return f"{code}{text}{reset}"

    def print_summary(
        self,
        total_recommendations: int,
        total_exposure: float,
        by_league: dict[str, int]
    ) -> None:
        """Print summary statistics."""
        print("\n" + "=" * 40)
        print(" SUMMARY")
        print("=" * 40)
        print(f"  Total recommendations: {total_recommendations}")
        print(f"  Total exposure: ${total_exposure:.0f}")
        print("  By league:")
        for league, count in by_league.items():
            print(f"    {league}: {count}")
        print()

    def print_watchlist(
        self,
        candidates: list[CandidateOpportunity],
        max_display: int = 5,
        title: str = "Watchlist (Near-Miss Opportunities)"
    ) -> None:
        """
        Print near-miss opportunities that didn't meet recommendation thresholds.

        Args:
            candidates: List of candidate opportunities (filtered out)
            max_display: Maximum number to display
            title: Section title
        """
        if not candidates:
            print("\n" + "-" * 70)
            print(" No near-miss opportunities to display.")
            print("-" * 70 + "\n")
            return

        display_candidates = candidates[:max_display]

        print(f"\n{'='*70}")
        print(f" {title} - Top {len(display_candidates)}")
        print(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        for i, candidate in enumerate(display_candidates, 1):
            self._print_candidate(i, candidate)

        if len(candidates) > max_display:
            print(f"  ... and {len(candidates) - max_display} more opportunities not shown.\n")

        print(f"{'='*70}")
        print(f" Total watchlist candidates: {len(candidates)}")
        print(f"{'='*70}\n")

    def _print_candidate(self, rank: int, candidate: CandidateOpportunity) -> None:
        """Print a single watchlist candidate."""
        # Header
        display_name = candidate.matchup or candidate.market_title or candidate.market_id
        header = f"#{rank} | {candidate.league or 'Unknown'} | {display_name}"
        print(self._colorize(header, "bold"))
        print("-" * 60)

        # Direction and price
        print(f"  Direction: {candidate.direction} @ {candidate.entry_price:.2f}")

        # Signals
        if candidate.signals:
            signals_str = ", ".join(candidate.signals)
            print(f"  Signals: {signals_str}")
        else:
            print(f"  Signals: (none)")

        # EV with threshold comparison
        ev_color = "green" if candidate.expected_value >= candidate.ev_threshold else "yellow"
        ev_str = f"{candidate.expected_value*100:+.1f}%"
        threshold_str = f"(threshold: {candidate.ev_threshold*100:.1f}%)"
        print(f"  EV: {self._colorize(ev_str, ev_color)} {threshold_str}")

        # Confidence with threshold comparison
        conf_color = "green" if candidate.confidence >= candidate.confidence_threshold else "yellow"
        conf_str = f"{candidate.confidence:.0%}"
        conf_threshold_str = f"(threshold: {candidate.confidence_threshold:.0%})"
        print(f"  Confidence: {self._colorize(conf_str, conf_color)} {conf_threshold_str}")

        # Rejection reasons
        if candidate.rejection_reasons:
            print(f"  {self._colorize('[!] Filtered:', 'red')}")
            for reason in candidate.rejection_reasons:
                print(f"      - {reason}")

        print()

    def print_pipeline_summary(self, stats: "PipelineStats") -> None:
        """
        Print pipeline funnel and key statistics.
        
        Shows the flow of data through each pipeline stage with visual funnel.
        
        Args:
            stats: Pipeline statistics collected during execution
        """
        print(f"\n{'='*70}")
        print(f" {self._colorize('Pipeline Summary', 'bold')}")
        print(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        # Key stats
        leagues_str = ", ".join(f"{k}: {v}" for k, v in sorted(stats.markets_by_league.items()))
        print(f"  Markets Polled:     {stats.markets_polled} ({leagues_str})")
        print(f"  Signals Generated:  {stats.signals_generated} across {stats.markets_with_signals} markets")
        print(f"  Aggregated:         {stats.markets_aggregated} markets ({stats.aggregation_dropoff} dropped - insufficient signals)")
        print(f"  Recommendations:    {stats.recommendations_count} ({stats.watchlist_count} -> watchlist)")
        print()
        
        # Visual funnel
        print("  " + self._colorize("Funnel:", "bold"))
        self._print_funnel_bar("Markets", stats.markets_polled, stats.markets_polled)
        self._print_funnel_bar("Signals", stats.signals_generated, stats.markets_polled)
        self._print_funnel_bar("Aggregated", stats.markets_aggregated, stats.markets_polled)
        self._print_funnel_bar("Recs", stats.recommendations_count, stats.markets_polled)
        print()
        
        # Signal breakdown
        if stats.signals_by_type:
            print("  " + self._colorize("Signal Breakdown:", "bold"))
            total_signals = sum(stats.signals_by_type.values())
            for signal_name, count in sorted(stats.signals_by_type.items(), key=lambda x: -x[1]):
                pct = (count / total_signals) * 100 if total_signals > 0 else 0
                print(f"    {signal_name}:{' ' * (20 - len(signal_name))}{count:3d} ({pct:.0f}%)")
        
        print(f"\n{'='*70}\n")

    def _print_funnel_bar(self, label: str, value: int, max_value: int) -> None:
        """Print a single funnel bar."""
        bar_width = 40
        if max_value > 0 and value > 0:
            filled = int((value / max_value) * bar_width)
            bar = "█" * filled + " " * (bar_width - filled)
            print(f"    {label:<12} {self._colorize(bar, 'blue')} {value}")
        else:
            print(f"    {label:<12} {'(none)':<{bar_width}} {value}")

    def print_markets_summary(self, stats: "PipelineStats", max_display: int = 10) -> None:
        """
        Print markets overview table.
        
        Args:
            stats: Pipeline statistics with snapshot data
            max_display: Maximum number of markets to display
        """
        print(f"\n{'='*70}")
        print(f" {self._colorize('Markets Summary', 'bold')}")
        print(f"{'='*70}\n")
        
        # Summary stats
        print(f"  Total Markets:  {stats.markets_polled}")
        print(f"  Total Volume:   {stats.total_volume:,}")
        if stats.avg_spread is not None:
            print(f"  Avg Spread:     ${stats.avg_spread:.3f}")
        print(f"  Total Depth:    {stats.total_depth:,}")
        print()
        
        # By league
        print("  " + self._colorize("By League:", "bold"))
        for league, count in sorted(stats.markets_by_league.items(), key=lambda x: -x[1]):
            print(f"    {league}: {count}")
        print()
        
        # Market table (top N)
        if stats.snapshots:
            print("  " + self._colorize(f"Top {min(max_display, len(stats.snapshots))} Markets:", "bold"))
            print("  " + "-" * 66)
            print(f"  {'League':<8} {'Bid':>6} {'Ask':>6} {'Spread':>8} {'Volume':>8} {'Depth':>8}")
            print("  " + "-" * 66)
            
            # Sort by volume descending
            sorted_snapshots = sorted(stats.snapshots, key=lambda s: s.volume_total, reverse=True)
            
            for snapshot in sorted_snapshots[:max_display]:
                league = (snapshot.league or "—")[:8]
                bid = f"${snapshot.best_bid:.2f}" if snapshot.best_bid else "—"
                ask = f"${snapshot.best_ask:.2f}" if snapshot.best_ask else "—"
                spread = f"${snapshot.spread:.3f}" if snapshot.spread else "—"
                volume = f"{snapshot.volume_total:,}"
                depth = f"{snapshot.total_bid_depth + snapshot.total_ask_depth:,}"
                
                print(f"  {league:<8} {bid:>6} {ask:>6} {spread:>8} {volume:>8} {depth:>8}")
            
            if len(stats.snapshots) > max_display:
                print(f"\n  ... and {len(stats.snapshots) - max_display} more markets")
        
        print(f"\n{'='*70}\n")

    def print_signals_summary(self, stats: "PipelineStats", max_display: int = 15) -> None:
        """
        Print signals breakdown and table.
        
        Args:
            stats: Pipeline statistics with signal data
            max_display: Maximum number of signals to display
        """
        print(f"\n{'='*70}")
        print(f" {self._colorize('Signals Summary', 'bold')}")
        print(f"{'='*70}\n")
        
        # Summary stats
        print(f"  Total Signals:      {stats.signals_generated}")
        print(f"  Markets w/ Signals: {stats.markets_with_signals}")
        print(f"  Signal Rate:        {stats.signal_rate:.1f}%")
        print()
        
        # Signal type distribution
        if stats.signals_by_type:
            print("  " + self._colorize("Signal Distribution:", "bold"))
            total = sum(stats.signals_by_type.values())
            max_count = max(stats.signals_by_type.values())
            
            for signal_name, count in sorted(stats.signals_by_type.items(), key=lambda x: -x[1]):
                pct = (count / total) * 100 if total > 0 else 0
                bar_width = int((count / max_count) * 20) if max_count > 0 else 0
                bar = "█" * bar_width
                print(f"    {signal_name:<20} {bar:<20} {count:3d} ({pct:.0f}%)")
            print()
        
        # Signal details table
        if stats.all_signals:
            print("  " + self._colorize(f"Recent Signals (top {min(max_display, len(stats.all_signals))}):", "bold"))
            print("  " + "-" * 66)
            print(f"  {'Signal':<18} {'Dir':>4} {'Str':>5} {'Conf':>5} {'Market':<20}")
            print("  " + "-" * 66)
            
            for signal in stats.all_signals[:max_display]:
                name = signal.name[:18]
                direction = signal.direction.value[:4]
                strength = f"{signal.strength:.0%}"
                confidence = f"{signal.confidence:.0%}"
                market = (signal.market_id or "—")[:20]
                
                print(f"  {name:<18} {direction:>4} {strength:>5} {confidence:>5} {market:<20}")
            
            if len(stats.all_signals) > max_display:
                print(f"\n  ... and {len(stats.all_signals) - max_display} more signals")
        else:
            print("  No signals generated.")
        
        print(f"\n{'='*70}\n")


def format_bet_slip(rec: Recommendation) -> str:
    """
    Format a single recommendation as a bet slip.

    Example output:
    ```
    NFL | Chiefs vs Bills
    Contract: Chiefs YES @ 0.44
    Signals: TailFlow(0.71), LateVol(0.63)
    EV (adj): +4.2%
    Max Size: $300
    ```
    """
    lines = [
        f"{rec.league} | {rec.matchup or rec.market_title}",
        f"Contract: {rec.contract} @ {rec.entry_price:.2f}",
        f"Signals: {', '.join(rec.contributing_signals)}",
        f"EV (adj): {rec.expected_value*100:+.1f}%",
        f"Max Size: ${rec.max_size}",
    ]

    if rec.risk_flags:
        lines.append(f"Risks: {', '.join(rec.risk_flags)}")

    return "\n".join(lines)


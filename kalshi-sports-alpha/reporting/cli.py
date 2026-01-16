"""CLI terminal output for recommendations."""

from typing import Optional
from datetime import datetime

from strategy.ranker import Recommendation


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


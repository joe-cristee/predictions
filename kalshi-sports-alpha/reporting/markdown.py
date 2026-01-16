"""Markdown report generation."""

from typing import Optional
from datetime import datetime
from pathlib import Path

from strategy.ranker import Recommendation


class MarkdownReporter:
    """Generate markdown bet slips and summaries."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        recommendations: list[Recommendation],
        title: str = "Daily Bet Recommendations"
    ) -> str:
        """
        Generate full markdown report.

        Args:
            recommendations: List of recommendations
            title: Report title

        Returns:
            Markdown string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"# {title}",
            f"",
            f"**Generated:** {timestamp}",
            f"",
            f"**Total Recommendations:** {len(recommendations)}",
            f"",
            "---",
            "",
        ]

        if not recommendations:
            lines.append("*No recommendations at this time.*")
        else:
            # Group by league
            by_league = {}
            for rec in recommendations:
                by_league.setdefault(rec.league, []).append(rec)

            for league, recs in sorted(by_league.items()):
                lines.append(f"## {league}")
                lines.append("")

                for rec in recs:
                    lines.extend(self._format_recommendation(rec))
                    lines.append("")

        # Summary
        lines.extend([
            "---",
            "",
            "## Summary",
            "",
        ])
        lines.extend(self._generate_summary(recommendations))

        return "\n".join(lines)

    def _format_recommendation(self, rec: Recommendation) -> list[str]:
        """Format single recommendation as markdown."""
        lines = [
            f"### {rec.matchup or rec.market_title}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Contract | **{rec.contract}** @ {rec.entry_price:.2f} |",
            f"| Expected Value | {rec.expected_value*100:+.1f}% |",
            f"| Max Size | ${rec.max_size} |",
            f"| Confidence | {rec.confidence:.0%} |",
            "",
        ]

        # Signals
        lines.append("**Contributing Signals:**")
        for signal in rec.contributing_signals:
            lines.append(f"- {signal}")
        lines.append("")

        # Risk flags
        if rec.risk_flags:
            lines.append("**Risk Flags:**")
            for flag in rec.risk_flags:
                lines.append(f"- ⚠️ {flag}")
            lines.append("")

        return lines

    def _generate_summary(self, recommendations: list[Recommendation]) -> list[str]:
        """Generate summary section."""
        if not recommendations:
            return ["*No recommendations to summarize.*"]

        total_exposure = sum(r.entry_price * r.max_size for r in recommendations)
        avg_ev = sum(r.expected_value for r in recommendations) / len(recommendations)

        by_league = {}
        for rec in recommendations:
            by_league[rec.league] = by_league.get(rec.league, 0) + 1

        lines = [
            f"- **Total Exposure:** ${total_exposure:.0f}",
            f"- **Average EV:** {avg_ev*100:+.1f}%",
            "",
            "**By League:**",
        ]
        for league, count in sorted(by_league.items()):
            lines.append(f"- {league}: {count} recommendation(s)")

        return lines

    def save_report(
        self,
        recommendations: list[Recommendation],
        filename: Optional[str] = None
    ) -> Path:
        """
        Save report to file.

        Args:
            recommendations: List of recommendations
            filename: Output filename (auto-generated if None)

        Returns:
            Path to saved file
        """
        if filename is None:
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recommendations_{date_str}.md"

        filepath = self.output_dir / filename
        content = self.generate_report(recommendations)

        with open(filepath, "w") as f:
            f.write(content)

        return filepath

    def generate_bet_slip(self, rec: Recommendation) -> str:
        """
        Generate a compact bet slip for a single recommendation.

        Args:
            rec: Recommendation

        Returns:
            Markdown bet slip
        """
        signals = ", ".join(rec.contributing_signals)

        return f"""```
{rec.league} | {rec.matchup or rec.market_title}
Contract: {rec.contract} @ {rec.entry_price:.2f}
Signals: {signals}
EV (adj): {rec.expected_value*100:+.1f}%
Max Size: ${rec.max_size}
```"""


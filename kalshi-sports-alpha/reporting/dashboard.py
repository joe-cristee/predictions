"""Streamlit dashboard for recommendations, watchlist, and pipeline analysis."""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import defaultdict

# Add parent directory to path for imports when running as streamlit app
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from strategy.ranker import Recommendation, CandidateOpportunity
from .pipeline_stats import PipelineStats


def recommendations_to_dataframe(recommendations: list[Recommendation]) -> pd.DataFrame:
    """Convert recommendations to a pandas DataFrame for display."""
    if not recommendations:
        return pd.DataFrame()
    
    data = []
    for rec in recommendations:
        data.append({
            "Rank": rec.rank_score,
            "League": rec.league or "—",
            "Matchup": rec.matchup or rec.market_title or rec.market_id,
            "Contract": rec.contract,
            "Price": f"${rec.entry_price:.2f}",
            "EV": f"{rec.expected_value*100:+.1f}%",
            "Confidence": f"{rec.confidence:.0%}",
            "Max Size": f"${rec.max_size}",
            "Signals": ", ".join(rec.contributing_signals),
            "Risks": ", ".join(rec.risk_flags) if rec.risk_flags else "—",
        })
    
    df = pd.DataFrame(data)
    return df.sort_values("Rank", ascending=False).reset_index(drop=True)


def watchlist_to_dataframe(candidates: list[CandidateOpportunity]) -> pd.DataFrame:
    """Convert watchlist candidates to a pandas DataFrame for display."""
    if not candidates:
        return pd.DataFrame()
    
    data = []
    for candidate in candidates:
        data.append({
            "Score": candidate.rank_score,
            "League": candidate.league or "—",
            "Matchup": candidate.matchup or candidate.market_title or candidate.market_id,
            "Direction": candidate.direction,
            "Price": f"${candidate.entry_price:.2f}",
            "EV": f"{candidate.expected_value*100:+.1f}%",
            "Confidence": f"{candidate.confidence:.0%}",
            "Signals": ", ".join(candidate.signals) if candidate.signals else "—",
            "Rejection": "; ".join(candidate.rejection_reasons),
        })
    
    df = pd.DataFrame(data)
    return df.sort_values("Score", ascending=False).reset_index(drop=True)


def snapshots_to_dataframe(stats: PipelineStats) -> pd.DataFrame:
    """Convert market snapshots to a pandas DataFrame for display."""
    if not stats.snapshots:
        return pd.DataFrame()
    
    data = []
    for snapshot in stats.snapshots:
        # Get signals for this market
        signals = stats.signals_by_market.get(snapshot.market_id, [])
        signal_names = [s.name for s in signals]
        
        # Format time to kickoff
        if snapshot.time_to_kickoff_seconds is not None:
            hours = snapshot.time_to_kickoff_seconds / 3600
            if hours < 1:
                kickoff_str = f"{int(hours * 60)}m"
            else:
                kickoff_str = f"{hours:.1f}h"
        else:
            kickoff_str = "—"
        
        data.append({
            "League": snapshot.league or "—",
            "Market": snapshot.market_id,
            "Bid": f"${snapshot.best_bid:.2f}" if snapshot.best_bid else "—",
            "Ask": f"${snapshot.best_ask:.2f}" if snapshot.best_ask else "—",
            "Spread": f"${snapshot.spread:.3f}" if snapshot.spread else "—",
            "Volume": snapshot.volume_total,
            "Depth": snapshot.total_bid_depth + snapshot.total_ask_depth,
            "Kickoff": kickoff_str,
            "Signals": len(signals),
            "Signal Types": ", ".join(signal_names) if signal_names else "—",
        })
    
    return pd.DataFrame(data)


def signals_to_dataframe(stats: PipelineStats) -> pd.DataFrame:
    """Convert all signals to a pandas DataFrame for display."""
    if not stats.all_signals:
        return pd.DataFrame()
    
    data = []
    for signal in stats.all_signals:
        data.append({
            "Market": signal.market_id or "—",
            "Signal": signal.name,
            "Direction": signal.direction.value,
            "Strength": f"{signal.strength:.0%}",
            "Confidence": f"{signal.confidence:.0%}",
            "Score": f"{signal.composite_score:.2f}",
            "Rationale": signal.rationale[:80] + "..." if len(signal.rationale) > 80 else signal.rationale,
        })
    
    return pd.DataFrame(data)


def render_funnel_chart(stats: PipelineStats) -> None:
    """Render a text-based funnel visualization."""
    funnel_data = stats.funnel
    max_value = max(item[1] for item in funnel_data) if funnel_data else 1
    
    st.subheader("Pipeline Funnel")
    
    for stage_name, count, description in funnel_data:
        # Calculate bar width (max 40 chars)
        if max_value > 0:
            bar_width = int((count / max_value) * 40)
        else:
            bar_width = 0
        
        bar = "█" * bar_width
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            st.write(f"**{stage_name}**")
        with col2:
            if count > 0:
                st.code(f"{bar} {count}")
            else:
                st.code(f"(none) 0")
        with col3:
            st.caption(description)


def render_filtering_breakdown(stats: PipelineStats) -> None:
    """Render pie chart showing filtering breakdown."""
    breakdown = stats.get_filtering_breakdown()
    
    # Filter out zero values
    filtered_breakdown = {k: v for k, v in breakdown.items() if v > 0}
    
    if not filtered_breakdown:
        st.info("No filtering data available.")
        return
    
    df = pd.DataFrame([
        {"Reason": k, "Count": v}
        for k, v in filtered_breakdown.items()
    ])
    
    st.bar_chart(df.set_index("Reason"))


def render_overview_tab(stats: PipelineStats) -> None:
    """Render the Overview tab with funnel and key metrics."""
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Markets Polled", stats.markets_polled)
    with col2:
        st.metric("Signals Generated", stats.signals_generated)
    with col3:
        st.metric("Recommendations", stats.recommendations_count)
    with col4:
        st.metric("Conversion Rate", f"{stats.conversion_rate:.1f}%")
    
    st.divider()
    
    # Funnel visualization
    col_funnel, col_breakdown = st.columns([2, 1])
    
    with col_funnel:
        render_funnel_chart(stats)
    
    with col_breakdown:
        st.subheader("Filtering Breakdown")
        render_filtering_breakdown(stats)
    
    st.divider()
    
    # Additional stats
    st.subheader("Pipeline Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Markets**")
        st.write(f"- Total Volume: {stats.total_volume:,}")
        st.write(f"- Avg Spread: ${stats.avg_spread:.3f}" if stats.avg_spread else "- Avg Spread: —")
        st.write(f"- Total Depth: {stats.total_depth:,}")
    
    with col2:
        st.write("**Signals**")
        st.write(f"- Signal Rate: {stats.signal_rate:.1f}%")
        st.write(f"- Markets w/ Signals: {stats.markets_with_signals}")
        st.write(f"- Aggregation Pass: {stats.aggregation_pass_rate:.1f}%")
    
    with col3:
        st.write("**By League**")
        for league, count in sorted(stats.markets_by_league.items()):
            st.write(f"- {league}: {count}")


def render_markets_tab(stats: PipelineStats) -> None:
    """Render the Markets tab with all polled markets."""
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Markets", stats.markets_polled)
    with col2:
        st.metric("Total Volume", f"{stats.total_volume:,}")
    with col3:
        st.metric("Avg Spread", f"${stats.avg_spread:.3f}" if stats.avg_spread else "—")
    with col4:
        st.metric("Total Depth", f"{stats.total_depth:,}")
    
    st.divider()
    
    # League filter
    all_leagues = ["All"] + sorted(stats.markets_by_league.keys())
    selected_league = st.selectbox("Filter by League", all_leagues, key="markets_league_filter")
    
    # Markets by league breakdown
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.subheader("Markets by League")
        league_df = pd.DataFrame([
            {"League": k, "Count": v}
            for k, v in sorted(stats.markets_by_league.items(), key=lambda x: -x[1])
        ])
        if not league_df.empty:
            st.bar_chart(league_df.set_index("League"))
    
    with col1:
        st.subheader("All Markets")
        markets_df = snapshots_to_dataframe(stats)
        
        if selected_league != "All":
            markets_df = markets_df[markets_df["League"] == selected_league]
        
        if not markets_df.empty:
            st.dataframe(
                markets_df,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No markets to display.")


def render_signals_tab(stats: PipelineStats) -> None:
    """Render the Signals tab with all generated signals."""
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Signals", stats.signals_generated)
    with col2:
        st.metric("Markets w/ Signals", stats.markets_with_signals)
    with col3:
        st.metric("Signal Types", len(stats.signals_by_type))
    with col4:
        avg_strength = sum(s.strength for s in stats.all_signals) / len(stats.all_signals) if stats.all_signals else 0
        st.metric("Avg Strength", f"{avg_strength:.0%}")
    
    st.divider()
    
    # Signal distribution chart
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Signal Distribution")
        if stats.signals_by_type:
            signal_df = pd.DataFrame([
                {"Signal": k, "Count": v}
                for k, v in sorted(stats.signals_by_type.items(), key=lambda x: -x[1])
            ])
            st.bar_chart(signal_df.set_index("Signal"))
            
            # Also show percentages
            total = sum(stats.signals_by_type.values())
            for signal_name, count in sorted(stats.signals_by_type.items(), key=lambda x: -x[1]):
                pct = (count / total) * 100 if total > 0 else 0
                st.write(f"- **{signal_name}**: {count} ({pct:.0f}%)")
        else:
            st.info("No signals generated.")
    
    with col2:
        st.subheader("All Signals")
        
        # Filter options
        signal_type_filter = st.selectbox(
            "Filter by Signal Type",
            ["All"] + sorted(stats.signals_by_type.keys()),
            key="signal_type_filter"
        )
        
        signals_df = signals_to_dataframe(stats)
        
        if signal_type_filter != "All":
            signals_df = signals_df[signals_df["Signal"] == signal_type_filter]
        
        if not signals_df.empty:
            st.dataframe(
                signals_df,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No signals to display.")
    
    st.divider()
    
    # Signals by market (expandable)
    st.subheader("Signals by Market")
    
    if stats.signals_by_market:
        for market_id, signals in sorted(stats.signals_by_market.items()):
            with st.expander(f"{market_id} ({len(signals)} signals)"):
                for signal in signals:
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        st.write(f"**{signal.name}**")
                        st.write(f"{signal.direction.value}")
                    with col2:
                        st.write(f"Strength: {signal.strength:.0%}")
                        st.write(f"Confidence: {signal.confidence:.0%}")
                    with col3:
                        st.write(signal.rationale)
                    st.divider()
    else:
        st.info("No signals generated for any market.")


def render_recommendations_tab(
    recommendations: list[Recommendation],
    watchlist: list[CandidateOpportunity],
    stats: PipelineStats
) -> None:
    """Render the Recommendations & Watchlist tab."""
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Recommendations", len(recommendations))
    with col2:
        st.metric("Watchlist", len(watchlist))
    with col3:
        if recommendations:
            avg_ev = sum(r.expected_value for r in recommendations) / len(recommendations)
            st.metric("Avg EV", f"{avg_ev*100:+.1f}%")
        else:
            st.metric("Avg EV", "—")
    with col4:
        if recommendations:
            total_exposure = sum(r.entry_price * r.max_size for r in recommendations)
            st.metric("Total Exposure", f"${total_exposure:.0f}")
        else:
            st.metric("Total Exposure", "$0")
    
    st.divider()
    
    # Recommendations table
    st.subheader("🎯 Active Recommendations")
    
    if recommendations:
        recs_df = recommendations_to_dataframe(recommendations)
        st.dataframe(
            recs_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recommendations at this time. Check the Watchlist for near-miss opportunities.")
    
    st.divider()
    
    # Watchlist table
    st.subheader("👀 Watchlist (Near-Miss)")
    
    max_watchlist = st.slider(
        "Show top N candidates",
        min_value=5,
        max_value=50,
        value=10,
        key="watchlist_limit"
    )
    
    if watchlist:
        watchlist_df = watchlist_to_dataframe(watchlist[:max_watchlist])
        st.dataframe(
            watchlist_df,
            use_container_width=True,
            hide_index=True,
        )
        
        if len(watchlist) > max_watchlist:
            st.caption(f"Showing {max_watchlist} of {len(watchlist)} candidates")
    else:
        st.info("No watchlist candidates.")


def run_dashboard(
    recommendations: list[Recommendation],
    watchlist: list[CandidateOpportunity],
    stats: Optional[PipelineStats] = None,
    refresh_callback: Optional[callable] = None
):
    """
    Run the Streamlit dashboard.
    
    Args:
        recommendations: List of approved recommendations
        watchlist: List of near-miss candidates
        stats: Pipeline statistics for analysis views
        refresh_callback: Optional callback to refresh data
    """
    st.set_page_config(
        page_title="Kalshi Sports Alpha",
        page_icon="📊",
        layout="wide",
    )
    
    # Header
    st.title("📊 Kalshi Sports Alpha")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Refresh button in header
    col1, col2 = st.columns([6, 1])
    with col2:
        if refresh_callback and st.button("🔄 Refresh", use_container_width=True):
            refresh_callback()
            st.rerun()
    
    # Create default stats if not provided
    if stats is None:
        stats = PipelineStats(
            markets_polled=0,
            recommendations_count=len(recommendations),
            watchlist_count=len(watchlist),
        )
    
    # Tabs
    tab_overview, tab_markets, tab_signals, tab_recs = st.tabs([
        "📈 Overview",
        "🏪 Markets",
        "⚡ Signals", 
        "🎯 Recommendations"
    ])
    
    with tab_overview:
        render_overview_tab(stats)
    
    with tab_markets:
        render_markets_tab(stats)
    
    with tab_signals:
        render_signals_tab(stats)
    
    with tab_recs:
        render_recommendations_tab(recommendations, watchlist, stats)


# Entry point for running as standalone Streamlit app
if __name__ == "__main__":
    # Demo mode with sample data
    st.warning("Running in demo mode with sample data. For live data, import and call run_dashboard() with actual recommendations.")
    
    # Create sample data for demo
    sample_recs = []
    sample_watchlist = []
    sample_stats = PipelineStats()
    
    run_dashboard(sample_recs, sample_watchlist, sample_stats)

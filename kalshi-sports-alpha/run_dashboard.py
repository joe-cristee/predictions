"""
Streamlit Dashboard Runner for Kalshi Sports Alpha

Usage:
    streamlit run run_dashboard.py

Or run directly:
    python run_dashboard.py
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

import streamlit as st

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent))

from kalshi.api import KalshiClient
from ingestion import MarketPoller
from features import FeatureRegistry
from features.microstructure.liquidity import compute_liquidity_score
from signals import TailInformedFlowSignal, FadeOverreactionSignal
from signals.late_kickoff_vol import LateKickoffVolSignal
from signals.fragile_market import FragileMarketSignal
from strategy import SignalAggregator, RecommendationRanker
from reporting.dashboard import run_dashboard
from reporting.pipeline_stats import PipelineStatsCollector


@st.cache_resource
def get_client():
    """Initialize and cache the Kalshi client."""
    load_dotenv()
    
    api_key = os.getenv("KALSHI_API_KEY_ID")
    if not api_key:
        st.error("KALSHI_API_KEY_ID not found in environment variables")
        st.stop()
    
    pem_path_env = os.getenv("KALSHI_PRIVATE_KEY_PATH")
    if pem_path_env:
        pem_path = Path(pem_path_env)
    else:
        pem_path = Path(__file__).parent / "ksa-test.pem"
    
    if not pem_path.exists():
        st.error(f"Private key file not found: {pem_path}")
        st.stop()
    
    with open(pem_path, "r") as f:
        private_key = f.read()
    
    return KalshiClient(
        api_key=api_key,
        private_key_pem=private_key,
    )


def fetch_data():
    """Fetch and process market data, returning recommendations, watchlist, and pipeline stats."""
    client = get_client()
    
    # Initialize components
    poller = MarketPoller(client)
    registry = FeatureRegistry()
    stats_collector = PipelineStatsCollector()
    
    generators = [
        TailInformedFlowSignal(),
        FadeOverreactionSignal(),
        LateKickoffVolSignal(),
        FragileMarketSignal(),
    ]
    
    aggregator = SignalAggregator(
        min_signals=2,
        require_agreement=True,
        min_agreement_ratio=0.6,
    )
    ranker = RecommendationRanker()
    
    # Stage 1: Fetch snapshots
    with st.spinner("Polling markets..."):
        snapshots = poller.poll_once()
        stats_collector.record_snapshots(snapshots)
    
    # Stage 2: Process each snapshot and generate signals
    signals_by_market = defaultdict(list)
    market_data = {}
    
    with st.spinner(f"Processing {len(snapshots)} markets..."):
        for snapshot in snapshots:
            features = registry.compute_all(snapshot)
            
            for gen in generators:
                signal = gen.generate(snapshot, features)
                if signal is not None:
                    signals_by_market[snapshot.market_id].append(signal)
            
            market_data[snapshot.market_id] = {
                "event_id": snapshot.event_id,
                "league": snapshot.league,
                "matchup": f"{snapshot.team_home} vs {snapshot.team_away}" if snapshot.team_home else "",
                "title": snapshot.market_id,
                "yes_ask": snapshot.best_ask,
                "no_ask": 1 - snapshot.best_bid if snapshot.best_bid else None,
                "spread": snapshot.spread,
                "liquidity_score": compute_liquidity_score(snapshot),
                "time_to_kickoff": snapshot.time_to_kickoff_seconds,
                "time_to_resolution": snapshot.time_to_resolution_seconds,
                "available_depth": snapshot.total_bid_depth + snapshot.total_ask_depth,
            }
    
    stats_collector.record_signals(dict(signals_by_market))
    
    # Stage 3: Aggregate signals
    aggregated = aggregator.aggregate_batch(dict(signals_by_market))
    aggregation_dropoff = len(signals_by_market) - len(aggregated)
    stats_collector.record_aggregation(len(aggregated), aggregation_dropoff)
    
    # Stage 4: Rank and filter
    recommendations, watchlist = ranker.rank_all(aggregated, market_data)
    
    # Count filtering reasons from watchlist
    filtered_by_ev = sum(1 for c in watchlist if any("EV" in r for r in c.rejection_reasons))
    filtered_by_conf = sum(1 for c in watchlist if any("Confidence" in r for r in c.rejection_reasons))
    stats_collector.record_filtering(len(recommendations), len(watchlist), filtered_by_ev, filtered_by_conf)
    
    # Finalize stats
    pipeline_stats = stats_collector.finalize()
    
    return recommendations, watchlist, pipeline_stats


def refresh_callback():
    """Callback to refresh data."""
    st.cache_data.clear()


# Main entry point
if __name__ == "__main__":
    # Check if running via streamlit
    if "streamlit" in sys.modules:
        # Fetch data and run dashboard
        try:
            recommendations, watchlist, pipeline_stats = fetch_data()
            run_dashboard(recommendations, watchlist, stats=pipeline_stats, refresh_callback=refresh_callback)
        except Exception as e:
            st.error(f"Error loading data: {e}")
            st.exception(e)
    else:
        # Run streamlit programmatically
        import subprocess
        subprocess.run(["streamlit", "run", __file__])

#%%

import os
import logging
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from kalshi.api import KalshiClient
from ingestion import MarketPoller
from features import FeatureRegistry
from features.microstructure.liquidity import compute_liquidity_score
from signals import TailInformedFlowSignal, FadeOverreactionSignal
from signals.late_kickoff_vol import LateKickoffVolSignal
from signals.fragile_market import FragileMarketSignal
from strategy import SignalAggregator, RecommendationRanker
from reporting import CLIReporter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


#%%
# Load credentials from .env and .pem files
load_dotenv()  # Loads from .env file in current directory


api_key = os.getenv("KALSHI_API_KEY_ID")
print(f"Using API key: {api_key[:8]}..." if api_key else "WARNING: No API key found!")
# Read private key from path specified in .env, or fallback to local file
pem_path_env = os.getenv("KALSHI_PRIVATE_KEY_PATH")
if pem_path_env:
    pem_path = Path(pem_path_env)
else:
    pem_path = Path(__file__).parent / "ksa-test.pem"

print(f"Loading private key from: {pem_path}")
with open(pem_path, "r") as f:
    private_key = f.read()

# Initialize the Kalshi API client
client = KalshiClient(
    api_key=api_key,
    private_key_pem=private_key,
)

# Initialize components
poller = MarketPoller(client)
registry = FeatureRegistry()

# Use all available signal generators
generators = [
    TailInformedFlowSignal(),
    FadeOverreactionSignal(),
    LateKickoffVolSignal(),
    FragileMarketSignal(),
]

# Aggregator now requires min 2 signals with agreement by default
aggregator = SignalAggregator(
    min_signals=2,
    require_agreement=True,
    min_agreement_ratio=0.6,
)
ranker = RecommendationRanker()
reporter = CLIReporter()

# Generate recommendations
snapshots = poller.poll_once()
print(f"Polled {len(snapshots)} market snapshots")

# Process each snapshot
signals_by_market = defaultdict(list)
market_data = {}

for snapshot in snapshots:
    # Compute features for this snapshot
    features = registry.compute_all(snapshot)
    
    # Generate signals from each generator
    for gen in generators:
        signal = gen.generate(snapshot, features)
        if signal is not None:
            signals_by_market[snapshot.market_id].append(signal)
    
    # Store market data for ranker (includes fields needed for EV calculation)
    market_data[snapshot.market_id] = {
        "event_id": snapshot.event_id,
        "league": snapshot.league,
        "matchup": f"{snapshot.team_home} vs {snapshot.team_away}" if snapshot.team_home else "",
        "title": snapshot.market_id,
        "yes_ask": snapshot.best_ask,
        "no_ask": 1 - snapshot.best_bid if snapshot.best_bid else None,
        "spread": snapshot.spread,  # Needed for dynamic vig calculation
        "liquidity_score": compute_liquidity_score(snapshot),  # Needed for sizing
        "time_to_kickoff": snapshot.time_to_kickoff_seconds,
        "time_to_resolution": snapshot.time_to_resolution_seconds,
        "available_depth": snapshot.total_bid_depth + snapshot.total_ask_depth,
    }

total_signals = sum(len(s) for s in signals_by_market.values())
print(f"Generated {total_signals} signals across {len(signals_by_market)} markets")

# Aggregate and rank
aggregated = aggregator.aggregate_batch(dict(signals_by_market))
recommendations = ranker.rank(aggregated, market_data)

print(f"Produced {len(recommendations)} recommendations")
reporter.print_recommendations(recommendations)

# Kalshi Sports Alpha

A sports-only alpha discovery system for Kalshi prediction markets.

## Overview

This system implements a **market-behavior-driven** approach to identifying positive expected value (EV) contracts on Kalshi's sports markets. Rather than predicting game outcomes, it analyzes market microstructure, behavioral patterns, and timing signals to find mispricings.

## Architecture

```
Kalshi API
   ↓
Market Snapshots (normalized)
   ↓
Feature Engineering
   ↓
Signals (directional insights)
   ↓
Strategy (ranking, sizing, filtering)
   ↓
Human-readable recommendations
   ↓
(Phase 2) Execution Engine
```

## Project Structure

```
kalshi-sports-alpha/
├── kalshi/              # API client and data models
│   ├── api/             # Client, endpoints, rate limiting
│   ├── models/          # Market, Trade, OrderBook schemas
│   └── sports/          # League configs, schedules, metadata
│
├── ingestion/           # Data collection
│   ├── poller.py        # Real-time snapshot loop
│   ├── backfill.py      # Historical data collection
│   └── persistence.py   # Data storage
│
├── features/            # Feature engineering
│   ├── microstructure/  # Liquidity, order flow, price impact
│   ├── temporal/        # Kickoff windows, volatility, time decay
│   ├── behavioral/      # Overreaction, FLB, absorption
│   └── structural/      # Cross-market, rule complexity
│
├── signals/             # Signal generators
│   ├── tail_informed_flow.py
│   ├── fade_overreaction.py
│   ├── late_kickoff_vol.py
│   └── fragile_market.py
│
├── strategy/            # Strategy layer
│   ├── aggregator.py    # Combine signals
│   ├── ranker.py        # EV ranking
│   ├── portfolio.py     # Correlation control
│   └── sizing.py        # Position sizing
│
├── reporting/           # Output generation
│   ├── cli.py           # Terminal output
│   └── markdown.py      # Bet slips
│
├── backtest/            # Backtesting
│   ├── simulator.py     # Trade replay
│   ├── fills.py         # Slippage model
│   └── metrics.py       # Performance metrics
│
├── execution/           # Phase 2 (stubbed)
│   ├── order_manager.py
│   └── risk.py
│
├── config/              # Configuration
│   ├── sports.yaml      # Enabled leagues
│   ├── signals.yaml     # Signal parameters
│   └── risk.yaml        # Risk limits
│
├── data/                # Data storage
├── notebooks/           # Research
└── tests/               # Test suite
```

## Signals

### 1. Tail Informed Flow
Follow large, informed accumulation patterns characterized by high trade clustering, large notional, low price impact, and narrow spreads.

### 2. Fade Overreaction
Fade narrative-driven price moves with high velocity but low volume confirmation.

### 3. Late Kickoff Volatility
Exploit fragile pricing near kickoff when volatility spikes and liquidity thins.

### 4. Fragile Market Snipe
Identify illiquid markets where small capital can move price, approaching resolution.

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure API credentials:**
```bash
export KALSHI_API_KEY="your_api_key"
export KALSHI_API_SECRET="your_api_secret"
```

3. **Run the system:**
```python
from ingestion import MarketPoller
from features import FeatureRegistry
from signals import TailInformedFlowSignal, FadeOverreactionSignal
from strategy import SignalAggregator, RecommendationRanker
from reporting import CLIReporter

# Initialize components
poller = MarketPoller(client)
generators = [TailInformedFlowSignal(), FadeOverreactionSignal()]
aggregator = SignalAggregator()
ranker = RecommendationRanker()
reporter = CLIReporter()

# Generate recommendations
snapshots = poller.poll_once()
signals = [gen.generate(s, features) for s in snapshots for gen in generators]
aggregated = aggregator.aggregate_batch(signals)
recommendations = ranker.rank(aggregated, market_data)
reporter.print_recommendations(recommendations)
```

## Configuration

Edit YAML files in `config/` to customize:
- **sports.yaml**: Enabled leagues and market types
- **signals.yaml**: Signal parameters and weights
- **risk.yaml**: Position and loss limits
- **runtime.yaml**: API and operational settings

## Development Roadmap

- [x] **Milestone 1**: Data ingestion + snapshots
- [x] **Milestone 2**: Feature computation
- [x] **Milestone 3**: Signal generation
- [x] **Milestone 4**: Ranking & reporting
- [x] **Milestone 5**: Backtesting
- [ ] **Milestone 6**: Automated execution (Phase 2)

## Design Principles

- **Separation of concerns**: Each layer has a clear responsibility
- **Deterministic contracts**: Clear data interfaces between layers
- **Research-first**: Designed for experimentation and iteration
- **Automation-ready**: Architecture supports future auto-execution
- **Sports-only**: Baked-in assumptions for sports markets

## Non-Goals

- Outcome prediction models
- Deep learning (initially)
- Non-sports markets
- High-frequency trading

## License

Proprietary - All rights reserved.


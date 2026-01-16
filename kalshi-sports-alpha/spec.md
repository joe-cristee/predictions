# Kalshi Sports Alpha – Full Repository Specification

## 1. Purpose & Scope

This repository implements a **sports-only Kalshi alpha discovery system**. Its purpose is to:

1. Ingest real-time and historical Kalshi sports market data
2. Engineer market microstructure, behavioral, temporal, and structural features
3. Generate actionable signals identifying positive expected value (EV) contracts
4. Rank and present bets for **manual execution** on Kalshi
5. Cleanly support a future phase of **automated order execution** without architectural refactor

The system is **market-behavior–driven**, not outcome-prediction–driven.

---

## 2. Design Principles

* **Separation of concerns**: ingestion ≠ features ≠ signals ≠ strategy ≠ execution
* **Deterministic data contracts** between layers
* **Research-first, automation-ready**
* **Sports-only assumptions baked in** (game time, kickoff windows, league metadata)
* **Stateless computation wherever possible**

---

## 3. High-Level Architecture

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

---

## 4. Repository Directory Structure

```
kalshi-sports-alpha/
├── data/
│   ├── raw/                    # Unmodified API payloads
│   ├── normalized/             # Canonical market snapshots
│   ├── features/               # Feature matrices (time-indexed)
│   ├── signals/                # Signal outputs
│   └── external/               # Sportsbooks, weather, injury feeds
│
├── kalshi/
│   ├── api/
│   │   ├── client.py            # Auth, retries, pagination
│   │   ├── endpoints.py         # Market, trade, order book fetchers
│   │   └── rate_limit.py
│   │
│   ├── models/
│   │   ├── market.py            # Market, Event, Contract schemas
│   │   ├── trade.py
│   │   ├── orderbook.py
│   │   └── snapshot.py
│   │
│   └── sports/
│       ├── leagues.py           # NFL, NBA, MLB, etc.
│       ├── schedule.py          # Game time normalization
│       └── metadata.py          # Teams, venues, season context
│
├── ingestion/
│   ├── poller.py                # Real-time snapshot loop
│   ├── backfill.py              # Historical data collection
│   └── persistence.py           # Disk / DB writers
│
├── features/
│   ├── microstructure/
│   │   ├── liquidity.py
│   │   ├── order_flow.py
│   │   └── price_impact.py
│   │
│   ├── temporal/
│   │   ├── kickoff_window.py
│   │   ├── volatility.py
│   │   └── time_decay.py
│   │
│   ├── behavioral/
│   │   ├── overreaction.py
│   │   ├── favorite_longshot.py
│   │   └── absorption.py
│   │
│   ├── structural/
│   │   ├── cross_market.py
│   │   └── rule_complexity.py
│   │
│   └── registry.py              # Feature discovery & execution
│
├── signals/
│   ├── tail_informed_flow.py
│   ├── fade_overreaction.py
│   ├── late_kickoff_vol.py
│   ├── fragile_market.py
│   └── signal_base.py
│
├── strategy/
│   ├── aggregator.py            # Combine multiple signals
│   ├── ranker.py                # EV & confidence ranking
│   ├── portfolio.py             # Correlation & exposure control
│   └── sizing.py                # Position sizing logic
│
├── reporting/
│   ├── cli.py                   # Terminal output
│   ├── markdown.py              # Bet slips / summaries
│   └── dashboard.py             # Optional web UI
│
├── backtest/
│   ├── simulator.py             # Trade replay engine
│   ├── fills.py                 # Slippage & partial fill model
│   ├── metrics.py               # Sharpe, drawdown, hit rate
│   └── scenarios.py
│
├── execution/                   # Phase 2 (initially stubbed)
│   ├── order_manager.py
│   ├── risk.py
│   └── reconciliation.py
│
├── config/
│   ├── sports.yaml              # Enabled leagues & markets
│   ├── signals.yaml             # Thresholds & weights
│   ├── risk.yaml                # Exposure limits
│   └── runtime.yaml
│
├── notebooks/                   # Research & visualization
├── tests/
└── README.md
```

---

## 5. Core Data Contracts

### 5.1 MarketSnapshot

Represents a single point-in-time view of a contract.

Fields (non-exhaustive):

* market_id
* event_id
* league
* team_home / team_away
* contract_side (YES / NO)
* best_bid
* best_ask
* mid_price
* last_trade_price
* last_trade_size
* volume_1m / 5m / 1h
* total_bid_depth
* total_ask_depth
* time_to_kickoff_seconds
* time_to_resolution_seconds

---

### 5.2 FeatureVector

Derived from `MarketSnapshot`.

* spread
* liquidity_imbalance
* price_impact_per_dollar
* trade_size_zscore
* trade_cluster_score
* price_velocity
* volatility_ratio
* absorption_ratio
* overreaction_score
* rule_complexity_score

All features are **numeric, deterministic, and side-agnostic**.

---

### 5.3 Signal

Directional insight produced from one or more features.

```
Signal:
  name: str
  direction: YES | NO
  strength: float   # 0–1
  confidence: float # 0–1
  rationale: str
```

---

### 5.4 Recommendation

Final output delivered to the user.

* market
* contract
* entry_price
* max_size
* expected_value
* time_to_resolution
* contributing_signals
* risk_flags

---

## 6. Sports-Specific Logic

### 6.1 Kickoff Windows

Defined regimes:

* T-24h to T-2h
* T-2h to T-10m
* T-10m to kickoff
* In-play (if applicable)

Signals are **window-aware**.

---

### 6.2 Common Sports Market Types

Handled explicitly:

* Moneyline (team wins)
* Totals (over / under)
* Binary milestones ("Will X score?", "Will Y lead at half?")

Each has different liquidity and bias profiles.

---

## 7. Signal Definitions (Initial Set)

### 7.1 Tail Informed Flow

**Intent**: Follow informed accumulation.

Criteria:

* High trade clustering
* Large notional
* Low price impact
* Narrow spread

Direction: Same as dominant flow.

---

### 7.2 Fade Overreaction

**Intent**: Fade narrative-driven moves.

Criteria:

* High price velocity
* Low volume confirmation
* No external news
* Short time horizon

Direction: Opposite price move.

---

### 7.3 Late Kickoff Volatility

**Intent**: Exploit fragile pricing near kickoff.

Criteria:

* Volatility spike
* Liquidity thinning
* Short time to kickoff

Direction: Based on imbalance.

---

### 7.4 Fragile Market Snipe

**Intent**: Identify markets where small capital moves price.

Criteria:

* Low depth
* High price impact
* Approaching resolution

---

## 8. Strategy Layer

### 8.1 Signal Aggregation

* Weighted linear or logistic combination
* Configurable via `signals.yaml`

### 8.2 Correlation Control

* Avoid multiple bets on same game outcome
* Penalize highly correlated contracts

### 8.3 Position Sizing

Inputs:

* Signal confidence
* Liquidity
* Time to resolution

Outputs:

* Suggested max order size

---

## 9. Reporting & UX

Initial output targets:

* CLI table (ranked bets)
* Markdown bet slip per game

Example:

```
NFL | Chiefs vs Bills
Contract: Chiefs YES @ 0.44
Signals: TailFlow(0.71), LateVol(0.63)
EV (adj): +4.2%
Max Size: $300
```

---

## 10. Phase 2 – Automation Readiness

Execution layer remains isolated.

Requirements:

* Idempotent order placement
* Kill-switch per market
* Exposure caps per league
* Manual approval toggle

---

## 11. Development Roadmap

**Milestone 1**: Data ingestion + snapshots
**Milestone 2**: Feature computation
**Milestone 3**: Signal generation
**Milestone 4**: Ranking & reporting
**Milestone 5**: Backtesting

---

## 12. Non-Goals (Explicit)

* Outcome prediction models
* Deep learning (initially)
* Non-sports markets
* High-frequency trading

---

## 13. Success Criteria

* Signals are explainable
* Recommendations are actionable
* Architecture does not change when automation begins

---

End of specification.

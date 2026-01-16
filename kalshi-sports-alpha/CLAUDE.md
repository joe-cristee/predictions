# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **sports-only Kalshi alpha discovery system** focused on market microstructure analysis. The goal is to identify positive expected value (EV) contracts through market behavior analysis, not outcome prediction. Currently in early alpha phase with standalone analysis scripts.

## Running Scripts

All scripts are standalone Python files run directly:

```bash
python large_bets.py        # NFL/NBA/NCAAF/NCAAB large wager detection
python sharpmoney.py        # Money flow bias analysis
python cbb_large_bets.py    # College basketball specific analysis
python college_ball.py      # College basketball market discovery
python main.py              # Balance/auth check
```

Configuration is currently hardcoded at the top of each script:
- `TARGET_DATE`: Date filter string (e.g., "26JAN15")
- `LOOKBACK_HOURS`: Trade history lookback (default 240 hours)

## Environment Setup

Required environment variables (via `.env` file):
- `KALSHI_API_KEY_ID`: Kalshi API key
- `KALSHI_PRIVATE_KEY_PATH`: Path to RSA private key for request signing

Dependencies (no requirements.txt yet):
- `requests`
- `python-dotenv`
- `cryptography`

## Architecture

```
Kalshi API (RSA-signed requests)
    ↓
Market Discovery (filter by date, league, "win" in title)
    ↓
Trade History Aggregation (YES/NO exposure calculation)
    ↓
CLI Output (tables showing money flow and large bets)
```

**Current state**: Standalone scripts for manual analysis. The `spec.md` file describes the planned full architecture with feature engineering, signal generation, and automated execution layers.

## Key Patterns

**API Authentication**: All API calls use RSA-PSS signing with SHA256. The pattern is:
```python
message = f"{timestamp}{method}{full_path}"
signature = private_key.sign(message, PSS_padding, SHA256)
```

**Exposure Calculation**: For binary markets (Team1 vs Team2):
- Team1 total exposure = Team1 YES volume + Team2 NO volume
- This accounts for NO bets being equivalent to betting YES on the opponent

**Market Filtering**: Scripts filter for moneyline markets using:
- Date string in ticker
- "win" in title (case-insensitive)
- Excludes "points" in title (filters out totals/spreads)

**League Codes**:
- `KXNFLGAME` (NFL)
- `KXNBAGAME` (NBA)
- `KXNCAAFGAME` (College Football)
- `KXNCAABGAME` (College Basketball)

## Planned Architecture (from spec.md)

The codebase is evolving toward a layered architecture:
1. **Ingestion Layer**: Market snapshots with normalized data
2. **Feature Engineering**: Microstructure, temporal, behavioral, structural features
3. **Signal Generation**: TailInformedFlow, FadeOverreaction, LateKickoffVol, FragileMarket
4. **Strategy Layer**: Signal aggregation, ranking, position sizing
5. **Execution Layer**: Phase 2 (stubbed for now)

See `spec.md` for complete architectural specification and data contracts.

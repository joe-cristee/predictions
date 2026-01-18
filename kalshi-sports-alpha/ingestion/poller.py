"""Real-time market snapshot polling."""

import time
import logging
from datetime import datetime, timezone
from typing import Optional, Callable
from dataclasses import dataclass

from kalshi.api import KalshiClient
from kalshi.models import MarketSnapshot
from kalshi.sports.leagues import get_league, SUPPORTED_LEAGUES, LeagueCode


logger = logging.getLogger(__name__)


# Sports-related series tickers on Kalshi
SPORTS_SERIES_PATTERNS = [
    "NFL", "NBA", "MLB", "NHL", "NCAAF", "NCAAB", "MLS", "SOCCER",
    "GOLF", "TENNIS", "UFC", "BOXING", "F1", "NASCAR"
]


@dataclass
class PollerConfig:
    """Configuration for market poller."""

    poll_interval_seconds: float = 5.0
    leagues: list[str] = None
    market_status: str = "open"
    include_orderbook: bool = True
    include_trades: bool = True

    def __post_init__(self):
        if self.leagues is None:
            self.leagues = ["NFL", "NBA", "MLB", "NCAAF", "NCAAB"]


class MarketPoller:
    """Real-time snapshot loop for sports markets."""

    def __init__(
        self,
        client: KalshiClient,
        config: Optional[PollerConfig] = None,
        on_snapshot: Optional[Callable[[MarketSnapshot], None]] = None,
    ):
        self.client = client
        self.config = config or PollerConfig()
        self.on_snapshot = on_snapshot
        self._running = False
        self._snapshots: list[MarketSnapshot] = []

    def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        logger.info("Starting market poller")

        while self._running:
            try:
                self._poll_cycle()
            except Exception as e:
                logger.error(f"Poll cycle error: {e}")

            time.sleep(self.config.poll_interval_seconds)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        logger.info("Stopping market poller")

    def poll_once(self) -> list[MarketSnapshot]:
        """Execute a single poll cycle and return snapshots."""
        self._snapshots.clear()
        self._poll_cycle()
        return self._snapshots.copy()

    def _poll_cycle(self) -> None:
        """Execute a single poll cycle."""
        timestamp = datetime.now(timezone.utc)

        # Fetch markets for each league
        for league in self.config.leagues:
            try:
                markets = self._fetch_league_markets(league)
                logger.info(f"Fetched {len(markets)} markets for {league}")

                for market in markets:
                    try:
                        snapshot = self._create_snapshot(market, timestamp, league)

                        if self.on_snapshot:
                            self.on_snapshot(snapshot)

                        self._snapshots.append(snapshot)
                    except Exception as e:
                        logger.warning(f"Failed to create snapshot for {market.get('ticker', 'unknown')}: {e}")

            except Exception as e:
                logger.error(f"Failed to fetch markets for {league}: {e}")

        logger.debug(f"Poll cycle complete: {len(self._snapshots)} snapshots")

    def _fetch_league_markets(self, league: str) -> list[dict]:
        """Fetch open markets for a league/series."""
        try:
            # Get the correct Kalshi series ticker from league config
            league_config = get_league(league)
            if league_config:
                series_ticker = league_config.kalshi_series
            else:
                # Fallback to KX{LEAGUE}GAME pattern
                series_ticker = f"KX{league}GAME"
            
            # Fetch markets filtered by series ticker and status
            markets = self.client.markets.get_markets(
                series_ticker=series_ticker,
                status=self.config.market_status
            )
            return markets
        except Exception as e:
            logger.error(f"API error fetching {league} markets: {e}")
            return []
    
    def _fetch_orderbook(self, ticker: str) -> Optional[dict]:
        """Fetch orderbook for a market."""
        if not self.config.include_orderbook:
            return None
        try:
            return self.client.orderbook.get_orderbook(ticker)
        except Exception as e:
            logger.warning(f"Failed to fetch orderbook for {ticker}: {e}")
            return None

    def _create_snapshot(
        self,
        market: dict,
        timestamp: datetime,
        league: str = ""
    ) -> MarketSnapshot:
        """Create a MarketSnapshot from Kalshi API market data."""
        ticker = market.get("ticker", "")
        
        # Fetch orderbook for depth info
        orderbook = self._fetch_orderbook(ticker)
        
        # Calculate bid/ask from orderbook if available
        best_bid = None
        best_ask = None
        total_bid_depth = 0
        total_ask_depth = 0
        
        if orderbook:
            # Kalshi orderbook has 'yes' and 'no' sides
            # 'yes' bids are bids to buy YES, 'no' bids are bids to buy NO
            yes_bids = orderbook.get("orderbook", {}).get("yes", [])
            no_bids = orderbook.get("orderbook", {}).get("no", [])
            
            # Best YES bid is top of yes_bids (highest price someone will pay for YES)
            if yes_bids:
                best_bid = yes_bids[0][0] / 100.0  # Convert cents to dollars
                total_bid_depth = sum(qty for price, qty in yes_bids)
            
            # Best YES ask = 100 - top NO bid (lowest price to buy YES = 1 - highest NO bid)
            if no_bids:
                best_ask = 1 - (no_bids[0][0] / 100.0)
                total_ask_depth = sum(qty for price, qty in no_bids)
        
        # Fallback to market yes_bid/yes_ask if no orderbook
        if best_bid is None:
            best_bid = market.get("yes_bid", 0) / 100.0 if market.get("yes_bid") else None
        if best_ask is None:
            best_ask = market.get("yes_ask", 0) / 100.0 if market.get("yes_ask") else None
        
        # Calculate mid price
        mid_price = None
        if best_bid is not None and best_ask is not None:
            mid_price = (best_bid + best_ask) / 2
        
        # Parse close time for time_to_resolution
        time_to_resolution = None
        close_time_str = market.get("close_time")
        if close_time_str:
            try:
                close_time = datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
                time_to_resolution = int((close_time - timestamp).total_seconds())
            except (ValueError, TypeError):
                pass
        
        # Parse expected expiration for time_to_kickoff (game time)
        time_to_kickoff = None
        expiration_str = market.get("expected_expiration_time") or market.get("expiration_time")
        if expiration_str:
            try:
                expiration = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
                time_to_kickoff = int((expiration - timestamp).total_seconds())
            except (ValueError, TypeError):
                pass

        return MarketSnapshot(
            market_id=ticker,
            event_id=market.get("event_ticker", ""),
            snapshot_time=timestamp,
            league=league or self._detect_league(market),
            team_home=None,  # Would need to parse from title/subtitle
            team_away=None,
            market_type=self._detect_market_type(market),
            contract_side="YES",
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,
            last_trade_price=market.get("last_price", 0) / 100.0 if market.get("last_price") else None,
            volume_total=market.get("volume", 0),
            total_bid_depth=total_bid_depth,
            total_ask_depth=total_ask_depth,
            time_to_kickoff_seconds=time_to_kickoff,
            time_to_resolution_seconds=time_to_resolution,
        )
    
    def _detect_league(self, market: dict) -> str:
        """Detect league from market data."""
        series = market.get("series_ticker", "")
        for pattern in SPORTS_SERIES_PATTERNS:
            if pattern in series.upper():
                return pattern
        return series
    
    def _detect_market_type(self, market: dict) -> str:
        """Detect market type from market data."""
        title = (market.get("title", "") + market.get("subtitle", "")).lower()
        
        if "over" in title or "under" in title or "total" in title:
            return "total"
        elif "prop" in title or "will" in title:
            return "prop"
        else:
            return "moneyline"

    @property
    def snapshots(self) -> list[MarketSnapshot]:
        """Get collected snapshots."""
        return self._snapshots.copy()

    def clear_snapshots(self) -> None:
        """Clear collected snapshots."""
        self._snapshots.clear()


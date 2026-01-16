"""Real-time market snapshot polling."""

import time
import logging
from datetime import datetime, timezone
from typing import Optional, Callable
from dataclasses import dataclass

from kalshi.api import KalshiClient
from kalshi.models import MarketSnapshot


logger = logging.getLogger(__name__)


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
            self.leagues = ["NFL", "NBA", "MLB"]


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

    def _poll_cycle(self) -> None:
        """Execute a single poll cycle."""
        timestamp = datetime.now(timezone.utc)

        # Fetch markets for each league
        for league in self.config.leagues:
            markets = self._fetch_league_markets(league)

            for market in markets:
                snapshot = self._create_snapshot(market, timestamp)

                if self.on_snapshot:
                    self.on_snapshot(snapshot)

                self._snapshots.append(snapshot)

        logger.debug(f"Poll cycle complete: {len(self._snapshots)} snapshots")

    def _fetch_league_markets(self, league: str) -> list[dict]:
        """Fetch open markets for a league."""
        # TODO: Implement actual API call
        # markets = self.client.markets.get_markets(
        #     series_ticker=league,
        #     status=self.config.market_status
        # )
        return []

    def _create_snapshot(
        self,
        market: dict,
        timestamp: datetime
    ) -> MarketSnapshot:
        """Create a MarketSnapshot from market data."""
        return MarketSnapshot(
            market_id=market.get("ticker", ""),
            event_id=market.get("event_ticker", ""),
            snapshot_time=timestamp,
            league=market.get("league", ""),
            best_bid=market.get("yes_bid"),
            best_ask=market.get("yes_ask"),
            volume_total=market.get("volume", 0),
        )

    @property
    def snapshots(self) -> list[MarketSnapshot]:
        """Get collected snapshots."""
        return self._snapshots.copy()

    def clear_snapshots(self) -> None:
        """Clear collected snapshots."""
        self._snapshots.clear()


"""Historical data collection and backfill."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Generator
from dataclasses import dataclass

from kalshi.api import KalshiClient


logger = logging.getLogger(__name__)


@dataclass
class BackfillConfig:
    """Configuration for historical backfill."""

    start_date: datetime
    end_date: Optional[datetime] = None
    leagues: list[str] = None
    include_settled: bool = True
    batch_size: int = 100

    def __post_init__(self):
        if self.end_date is None:
            self.end_date = datetime.now(timezone.utc)
        if self.leagues is None:
            self.leagues = ["NFL", "NBA", "MLB"]


class HistoricalBackfill:
    """Historical data collection for backtesting."""

    def __init__(self, client: KalshiClient, config: BackfillConfig):
        self.client = client
        self.config = config

    def run(self) -> Generator[dict, None, None]:
        """
        Run backfill and yield historical records.

        Yields:
            Historical market/trade records
        """
        logger.info(
            f"Starting backfill from {self.config.start_date} to {self.config.end_date}"
        )

        for league in self.config.leagues:
            yield from self._backfill_league(league)

    def _backfill_league(self, league: str) -> Generator[dict, None, None]:
        """Backfill data for a single league."""
        logger.info(f"Backfilling {league}")

        # Fetch historical events
        events = self._fetch_historical_events(league)

        for event in events:
            # Fetch markets for event
            markets = self._fetch_event_markets(event)

            for market in markets:
                # Fetch trade history
                trades = self._fetch_market_trades(market)

                yield {
                    "event": event,
                    "market": market,
                    "trades": trades,
                }

    def _fetch_historical_events(self, league: str) -> list[dict]:
        """Fetch historical events for a league."""
        # TODO: Implement with pagination
        # events = self.client.events.get_events(
        #     series_ticker=league,
        #     status="settled" if self.config.include_settled else "open"
        # )
        return []

    def _fetch_event_markets(self, event: dict) -> list[dict]:
        """Fetch markets for an event."""
        # TODO: Implement
        return []

    def _fetch_market_trades(self, market: dict) -> list[dict]:
        """Fetch trade history for a market."""
        # TODO: Implement with pagination
        return []


def generate_date_ranges(
    start: datetime,
    end: datetime,
    chunk_days: int = 7
) -> Generator[tuple[datetime, datetime], None, None]:
    """Generate date range chunks for batch processing."""
    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=chunk_days), end)
        yield (current, chunk_end)
        current = chunk_end


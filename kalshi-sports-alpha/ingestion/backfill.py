"""Historical data collection and backfill."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Generator
from dataclasses import dataclass

from kalshi.api import KalshiClient
from kalshi.sports.leagues import get_league


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
        """
        Fetch historical events for a league.

        Args:
            league: League code (e.g., "NFL", "NBA")

        Returns:
            List of event dicts from the API
        """
        try:
            # Get the proper Kalshi series ticker from league config
            league_config = get_league(league)
            if league_config:
                series_ticker = league_config.kalshi_series
            else:
                # Fallback to KX{LEAGUE}GAME pattern
                series_ticker = f"KX{league}GAME"

            logger.debug(f"Fetching events for series: {series_ticker}")

            # Fetch all events for this series
            all_events = self.client.markets.get_events(series_ticker=series_ticker)

            # Filter events by date range
            filtered_events = []
            for event in all_events:
                # Parse event end time to filter by date range
                end_time_str = event.get("end_date") or event.get("expected_expiration_time")
                if end_time_str:
                    try:
                        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))

                        # Include events that ended within our date range
                        if self.config.start_date <= end_time <= self.config.end_date:
                            filtered_events.append(event)
                        # Also include events that started before end_date (might have data in range)
                        elif end_time >= self.config.start_date:
                            filtered_events.append(event)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not parse event date: {end_time_str}, {e}")
                        # Include event if we can't determine date
                        filtered_events.append(event)
                else:
                    # Include if no date info available
                    filtered_events.append(event)

            # Filter by status if needed
            if not self.config.include_settled:
                filtered_events = [
                    e for e in filtered_events
                    if e.get("status") != "settled"
                ]

            logger.info(f"Found {len(filtered_events)} events for {league} in date range")
            return filtered_events

        except Exception as e:
            logger.error(f"Failed to fetch events for {league}: {e}")
            return []

    def _fetch_event_markets(self, event: dict) -> list[dict]:
        """
        Fetch markets for an event.

        Args:
            event: Event dict from the API

        Returns:
            List of market dicts for this event
        """
        try:
            event_ticker = event.get("event_ticker") or event.get("ticker")
            if not event_ticker:
                logger.warning(f"Event missing ticker: {event}")
                return []

            logger.debug(f"Fetching markets for event: {event_ticker}")

            # Fetch markets filtered by event ticker
            markets = self.client.markets.get_markets(event_ticker=event_ticker)

            logger.debug(f"Found {len(markets)} markets for event {event_ticker}")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch markets for event {event.get('event_ticker')}: {e}")
            return []

    def _fetch_market_trades(self, market: dict) -> list[dict]:
        """
        Fetch trade history for a market.

        Args:
            market: Market dict from the API

        Returns:
            List of trade dicts for this market within the configured date range
        """
        try:
            ticker = market.get("ticker")
            if not ticker:
                logger.warning(f"Market missing ticker: {market}")
                return []

            logger.debug(f"Fetching trades for market: {ticker}")

            # Fetch trades with date range filter
            trades = self.client.trades.get_trades(
                ticker=ticker,
                min_ts=self.config.start_date,
                max_ts=self.config.end_date,
                limit=self.config.batch_size,
            )

            logger.debug(f"Found {len(trades)} trades for market {ticker}")
            return trades

        except Exception as e:
            logger.error(f"Failed to fetch trades for market {market.get('ticker')}: {e}")
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


"""Historical trade data pipeline for fetching and storing trade history."""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from kalshi.api import KalshiClient
from kalshi.models.trade import Trade


logger = logging.getLogger(__name__)


@dataclass
class TradeHistoryConfig:
    """Configuration for trade history pipeline."""

    lookback_hours: int = 24  # How far back to fetch trades
    cache_dir: Optional[Path] = None  # Directory for caching trade data
    max_trades_per_market: int = 5000  # Max trades to store per market


@dataclass
class MarketTradeHistory:
    """Trade history for a single market."""

    ticker: str
    trades: list[Trade] = field(default_factory=list)
    last_updated: Optional[datetime] = None

    @property
    def trade_count(self) -> int:
        """Number of trades stored."""
        return len(self.trades)

    @property
    def total_volume(self) -> int:
        """Total contracts traded."""
        return sum(t.count for t in self.trades)

    @property
    def total_notional(self) -> float:
        """Total notional value."""
        return sum(t.notional or 0 for t in self.trades)

    def get_trades_since(self, since: datetime) -> list[Trade]:
        """Get trades since a specific time."""
        return [t for t in self.trades if t.timestamp >= since]

    def get_trades_in_window(
        self, start: datetime, end: datetime
    ) -> list[Trade]:
        """Get trades within a time window."""
        return [t for t in self.trades if start <= t.timestamp <= end]

    def get_recent_trades(self, count: int) -> list[Trade]:
        """Get the N most recent trades."""
        sorted_trades = sorted(self.trades, key=lambda t: t.timestamp, reverse=True)
        return sorted_trades[:count]


class TradeHistoryStore:
    """
    In-memory store for trade history with disk persistence.

    Provides efficient access to historical trade data for feature computation.
    """

    def __init__(self, config: Optional[TradeHistoryConfig] = None):
        self.config = config or TradeHistoryConfig()
        self._history: dict[str, MarketTradeHistory] = {}

    def add_trades(self, ticker: str, trades: list[Trade]) -> None:
        """Add trades to the history for a market."""
        if ticker not in self._history:
            self._history[ticker] = MarketTradeHistory(ticker=ticker)

        history = self._history[ticker]

        # Merge new trades (avoid duplicates by trade_id)
        existing_ids = {t.trade_id for t in history.trades}
        new_trades = [t for t in trades if t.trade_id not in existing_ids]

        history.trades.extend(new_trades)
        history.last_updated = datetime.now(timezone.utc)

        # Trim to max size (keep most recent)
        if len(history.trades) > self.config.max_trades_per_market:
            history.trades = sorted(
                history.trades, key=lambda t: t.timestamp, reverse=True
            )[: self.config.max_trades_per_market]

        logger.debug(f"Added {len(new_trades)} trades for {ticker}")

    def get_history(self, ticker: str) -> Optional[MarketTradeHistory]:
        """Get trade history for a market."""
        return self._history.get(ticker)

    def get_trades(
        self,
        ticker: str,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[Trade]:
        """Get trades for a market with optional filters."""
        history = self._history.get(ticker)
        if not history:
            return []

        trades = history.trades
        if since:
            trades = [t for t in trades if t.timestamp >= since]

        # Sort by timestamp descending
        trades = sorted(trades, key=lambda t: t.timestamp, reverse=True)

        if limit:
            trades = trades[:limit]

        return trades

    def get_all_tickers(self) -> list[str]:
        """Get all tickers with stored history."""
        return list(self._history.keys())

    def clear(self, ticker: Optional[str] = None) -> None:
        """Clear history for a market or all markets."""
        if ticker:
            self._history.pop(ticker, None)
        else:
            self._history.clear()


class TradeHistoryPipeline:
    """
    Pipeline for fetching and maintaining trade history from Kalshi API.

    This replaces the proxy features by providing actual trade data.
    """

    def __init__(
        self,
        client: KalshiClient,
        store: Optional[TradeHistoryStore] = None,
        config: Optional[TradeHistoryConfig] = None,
    ):
        self.client = client
        self.config = config or TradeHistoryConfig()
        self.store = store or TradeHistoryStore(self.config)

    def fetch_trades(
        self,
        ticker: str,
        lookback_hours: Optional[int] = None,
    ) -> list[Trade]:
        """
        Fetch trades from Kalshi API for a market.

        Args:
            ticker: Market ticker
            lookback_hours: How far back to fetch (defaults to config)

        Returns:
            List of Trade objects
        """
        lookback = lookback_hours or self.config.lookback_hours
        min_ts = datetime.now(timezone.utc) - timedelta(hours=lookback)

        try:
            raw_trades = self.client.trades.get_trades(
                ticker=ticker,
                min_ts=min_ts,
            )

            trades = [Trade.from_api_response(t) for t in raw_trades]
            logger.info(f"Fetched {len(trades)} trades for {ticker}")
            return trades

        except Exception as e:
            logger.error(f"Failed to fetch trades for {ticker}: {e}")
            return []

    def update_market(self, ticker: str) -> MarketTradeHistory:
        """
        Fetch and store latest trades for a market.

        Returns:
            Updated MarketTradeHistory
        """
        trades = self.fetch_trades(ticker)
        self.store.add_trades(ticker, trades)
        return self.store.get_history(ticker)

    def update_markets(self, tickers: list[str]) -> dict[str, MarketTradeHistory]:
        """
        Update trade history for multiple markets.

        Returns:
            Dict of ticker -> MarketTradeHistory
        """
        results = {}
        for ticker in tickers:
            history = self.update_market(ticker)
            if history:
                results[ticker] = history
        return results

    def compute_trade_metrics(
        self,
        ticker: str,
        window_minutes: int = 60,
    ) -> dict[str, float]:
        """
        Compute trade metrics for a market over a time window.

        Returns metrics that can replace proxy features:
        - trade_flow_imbalance: Net buy-sell imbalance (-1 to 1)
        - trade_clustering: Measure of trade time clustering (0 to 1)
        - price_velocity: Rate of price change (cents per minute)
        - volume_rate: Trades per minute
        - avg_trade_size: Average trade size
        - large_trade_ratio: Ratio of volume from large trades

        Args:
            ticker: Market ticker
            window_minutes: Time window for computation

        Returns:
            Dict of metric name -> value
        """
        window_start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        trades = self.store.get_trades(ticker, since=window_start)

        if not trades:
            return {
                "trade_flow_imbalance": 0.0,
                "trade_clustering": 0.0,
                "price_velocity": 0.0,
                "volume_rate": 0.0,
                "avg_trade_size": 0.0,
                "large_trade_ratio": 0.0,
            }

        # Trade flow imbalance
        buy_volume = sum(t.count for t in trades if t.is_buyer_initiated)
        sell_volume = sum(t.count for t in trades if t.is_seller_initiated)
        total_volume = buy_volume + sell_volume
        flow_imbalance = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0

        # Trade clustering (based on inter-arrival times)
        clustering = self._compute_clustering(trades)

        # Price velocity
        if len(trades) >= 2:
            sorted_trades = sorted(trades, key=lambda t: t.timestamp)
            first_price = sorted_trades[0].price
            last_price = sorted_trades[-1].price
            time_span_minutes = (
                sorted_trades[-1].timestamp - sorted_trades[0].timestamp
            ).total_seconds() / 60
            price_velocity = (last_price - first_price) * 100 / max(1, time_span_minutes)
        else:
            price_velocity = 0.0

        # Volume rate
        volume_rate = len(trades) / window_minutes

        # Average trade size
        avg_trade_size = total_volume / len(trades) if trades else 0

        # Large trade ratio (trades > 50 contracts)
        large_volume = sum(t.count for t in trades if t.count > 50)
        large_trade_ratio = large_volume / total_volume if total_volume > 0 else 0

        return {
            "trade_flow_imbalance": flow_imbalance,
            "trade_clustering": clustering,
            "price_velocity": price_velocity,
            "volume_rate": volume_rate,
            "avg_trade_size": avg_trade_size,
            "large_trade_ratio": large_trade_ratio,
        }

    def _compute_clustering(self, trades: list[Trade]) -> float:
        """
        Compute trade clustering score from inter-arrival times.

        High clustering (low CV of inter-arrival times) suggests informed trading.

        Returns:
            Clustering score 0-1 (higher = more clustered)
        """
        if len(trades) < 2:
            return 0.0

        sorted_trades = sorted(trades, key=lambda t: t.timestamp)
        intervals = []

        for i in range(1, len(sorted_trades)):
            delta = (
                sorted_trades[i].timestamp - sorted_trades[i - 1].timestamp
            ).total_seconds()
            intervals.append(delta)

        if not intervals:
            return 0.0

        mean_interval = sum(intervals) / len(intervals)
        if mean_interval == 0:
            return 1.0  # All trades at same time = max clustering

        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_interval = variance ** 0.5
        cv = std_interval / mean_interval  # Coefficient of variation

        # Invert and normalize: low CV = high clustering
        # CV of 0 = perfectly regular (or all at once) = 1.0
        # CV of 2+ = very irregular = 0.0
        clustering = max(0, 1 - cv / 2)
        return min(1.0, clustering)


# Singleton instance for global access
_pipeline_instance: Optional[TradeHistoryPipeline] = None


def get_trade_pipeline() -> Optional[TradeHistoryPipeline]:
    """Get the global trade history pipeline instance."""
    return _pipeline_instance


def init_trade_pipeline(
    client: KalshiClient,
    config: Optional[TradeHistoryConfig] = None,
) -> TradeHistoryPipeline:
    """Initialize the global trade history pipeline."""
    global _pipeline_instance
    _pipeline_instance = TradeHistoryPipeline(client, config=config)
    return _pipeline_instance


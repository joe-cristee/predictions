"""Tests for trade history pipeline."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from kalshi.models.trade import Trade, TradeSide
from ingestion.trade_history import (
    TradeHistoryStore,
    TradeHistoryConfig,
    MarketTradeHistory,
    TradeHistoryPipeline,
)


class TestMarketTradeHistory:
    """Tests for MarketTradeHistory model."""

    def _create_trade(
        self,
        trade_id: str,
        price: float = 0.50,
        count: int = 100,
        is_buy: bool = True,
        seconds_ago: int = 0,
    ) -> Trade:
        """Helper to create test trades."""
        return Trade(
            trade_id=trade_id,
            ticker="TEST",
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago),
            price=price,
            count=count,
            taker_side=TradeSide.BUY if is_buy else TradeSide.SELL,
        )

    def test_trade_count(self):
        """Test trade count property."""
        history = MarketTradeHistory(ticker="TEST")
        history.trades = [
            self._create_trade("t1"),
            self._create_trade("t2"),
            self._create_trade("t3"),
        ]
        
        assert history.trade_count == 3

    def test_total_volume(self):
        """Test total volume calculation."""
        history = MarketTradeHistory(ticker="TEST")
        history.trades = [
            self._create_trade("t1", count=100),
            self._create_trade("t2", count=200),
            self._create_trade("t3", count=50),
        ]
        
        assert history.total_volume == 350

    def test_get_trades_since(self):
        """Test filtering trades by time."""
        now = datetime.now(timezone.utc)
        history = MarketTradeHistory(ticker="TEST")
        history.trades = [
            self._create_trade("t1", seconds_ago=3600),  # 1 hour ago
            self._create_trade("t2", seconds_ago=1800),  # 30 min ago
            self._create_trade("t3", seconds_ago=300),   # 5 min ago
        ]
        
        # Get trades from last 45 minutes
        since = now - timedelta(minutes=45)
        recent = history.get_trades_since(since)
        
        assert len(recent) == 2  # Only last 30min and 5min trades

    def test_get_recent_trades(self):
        """Test getting N most recent trades."""
        history = MarketTradeHistory(ticker="TEST")
        history.trades = [
            self._create_trade("t1", seconds_ago=300),
            self._create_trade("t2", seconds_ago=200),
            self._create_trade("t3", seconds_ago=100),
        ]
        
        recent = history.get_recent_trades(2)
        
        assert len(recent) == 2
        assert recent[0].trade_id == "t3"  # Most recent first


class TestTradeHistoryStore:
    """Tests for TradeHistoryStore."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = TradeHistoryConfig(max_trades_per_market=100)
        self.store = TradeHistoryStore(self.config)

    def _create_trade(
        self,
        trade_id: str,
        ticker: str = "TEST",
        price: float = 0.50,
        count: int = 100,
    ) -> Trade:
        """Helper to create test trades."""
        return Trade(
            trade_id=trade_id,
            ticker=ticker,
            timestamp=datetime.now(timezone.utc),
            price=price,
            count=count,
            taker_side=TradeSide.BUY,
        )

    def test_trade_store_adds_trades(self):
        """Test store adds trades correctly."""
        trades = [
            self._create_trade("t1"),
            self._create_trade("t2"),
        ]
        
        self.store.add_trades("TEST", trades)
        
        history = self.store.get_history("TEST")
        assert history is not None
        assert history.trade_count == 2

    def test_trade_store_deduplicates(self):
        """Test store deduplicates by trade_id."""
        trades1 = [
            self._create_trade("t1"),
            self._create_trade("t2"),
        ]
        trades2 = [
            self._create_trade("t2"),  # Duplicate
            self._create_trade("t3"),  # New
        ]
        
        self.store.add_trades("TEST", trades1)
        self.store.add_trades("TEST", trades2)
        
        history = self.store.get_history("TEST")
        assert history.trade_count == 3  # Not 4

    def test_trade_store_trims_to_max(self):
        """Test store trims to max_trades_per_market."""
        config = TradeHistoryConfig(max_trades_per_market=5)
        store = TradeHistoryStore(config)
        
        trades = [self._create_trade(f"t{i}") for i in range(10)]
        store.add_trades("TEST", trades)
        
        history = store.get_history("TEST")
        assert history.trade_count == 5

    def test_trade_store_multiple_markets(self):
        """Test store handles multiple markets independently."""
        self.store.add_trades("MARKET1", [self._create_trade("t1", ticker="MARKET1")])
        self.store.add_trades("MARKET2", [self._create_trade("t2", ticker="MARKET2")])
        
        assert self.store.get_history("MARKET1").trade_count == 1
        assert self.store.get_history("MARKET2").trade_count == 1
        assert len(self.store.get_all_tickers()) == 2

    def test_trade_store_clear(self):
        """Test store clear functionality."""
        self.store.add_trades("TEST", [self._create_trade("t1")])
        
        self.store.clear("TEST")
        
        assert self.store.get_history("TEST") is None

    def test_trade_store_clear_all(self):
        """Test store clear all functionality."""
        self.store.add_trades("MARKET1", [self._create_trade("t1")])
        self.store.add_trades("MARKET2", [self._create_trade("t2")])
        
        self.store.clear()
        
        assert len(self.store.get_all_tickers()) == 0


class TestTradeHistoryPipeline:
    """Tests for TradeHistoryPipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.trades = Mock()
        self.config = TradeHistoryConfig(lookback_hours=24)
        self.pipeline = TradeHistoryPipeline(
            client=self.mock_client,
            config=self.config,
        )

    def _create_api_trade(self, trade_id: str, price: int = 50, count: int = 100) -> dict:
        """Create mock API trade response."""
        return {
            "trade_id": trade_id,
            "ticker": "TEST",
            "created_time": datetime.now(timezone.utc).isoformat(),
            "yes_price": price,
            "count": count,
            "taker_side": "buy",
        }

    def test_trade_metrics_flow_imbalance(self):
        """Test flow imbalance calculation from trades."""
        # Add trades: 300 buy, 100 sell
        now = datetime.now(timezone.utc)
        trades = [
            Trade("t1", "TEST", now, 0.50, 200, TradeSide.BUY),
            Trade("t2", "TEST", now, 0.50, 100, TradeSide.BUY),
            Trade("t3", "TEST", now, 0.50, 100, TradeSide.SELL),
        ]
        self.pipeline.store.add_trades("TEST", trades)
        
        metrics = self.pipeline.compute_trade_metrics("TEST", window_minutes=60)
        
        # (300 - 100) / 400 = 0.5
        assert metrics["trade_flow_imbalance"] == pytest.approx(0.5, rel=0.01)

    def test_trade_metrics_balanced_flow(self):
        """Test flow imbalance when balanced."""
        now = datetime.now(timezone.utc)
        trades = [
            Trade("t1", "TEST", now, 0.50, 100, TradeSide.BUY),
            Trade("t2", "TEST", now, 0.50, 100, TradeSide.SELL),
        ]
        self.pipeline.store.add_trades("TEST", trades)
        
        metrics = self.pipeline.compute_trade_metrics("TEST", window_minutes=60)
        
        assert metrics["trade_flow_imbalance"] == pytest.approx(0.0, abs=0.01)

    def test_trade_metrics_clustering(self):
        """Test trade clustering calculation."""
        # Create trades with small time gaps (clustered)
        now = datetime.now(timezone.utc)
        trades = [
            Trade("t1", "TEST", now - timedelta(seconds=5), 0.50, 100, TradeSide.BUY),
            Trade("t2", "TEST", now - timedelta(seconds=4), 0.50, 100, TradeSide.BUY),
            Trade("t3", "TEST", now - timedelta(seconds=3), 0.50, 100, TradeSide.BUY),
            Trade("t4", "TEST", now - timedelta(seconds=2), 0.50, 100, TradeSide.BUY),
        ]
        self.pipeline.store.add_trades("TEST", trades)
        
        metrics = self.pipeline.compute_trade_metrics("TEST", window_minutes=60)
        
        # Clustered trades should have high clustering score
        assert metrics["trade_clustering"] > 0.5

    def test_trade_metrics_price_velocity(self):
        """Test price velocity calculation."""
        now = datetime.now(timezone.utc)
        trades = [
            Trade("t1", "TEST", now - timedelta(minutes=10), 0.40, 100, TradeSide.BUY),
            Trade("t2", "TEST", now - timedelta(minutes=5), 0.45, 100, TradeSide.BUY),
            Trade("t3", "TEST", now, 0.50, 100, TradeSide.BUY),  # +10 cents over 10 min
        ]
        self.pipeline.store.add_trades("TEST", trades)
        
        metrics = self.pipeline.compute_trade_metrics("TEST", window_minutes=60)
        
        # Price went from 0.40 to 0.50 = +10 cents in 10 min = 1 cent/min
        assert metrics["price_velocity"] == pytest.approx(1.0, rel=0.2)

    def test_trade_metrics_volume_rate(self):
        """Test volume rate calculation."""
        now = datetime.now(timezone.utc)
        trades = [
            Trade("t1", "TEST", now - timedelta(minutes=30), 0.50, 100, TradeSide.BUY),
            Trade("t2", "TEST", now - timedelta(minutes=20), 0.50, 100, TradeSide.BUY),
            Trade("t3", "TEST", now - timedelta(minutes=10), 0.50, 100, TradeSide.BUY),
        ]
        self.pipeline.store.add_trades("TEST", trades)
        
        metrics = self.pipeline.compute_trade_metrics("TEST", window_minutes=60)
        
        # 3 trades in 60 min window = 0.05 trades/min
        assert metrics["volume_rate"] == pytest.approx(3/60, rel=0.1)

    def test_trade_metrics_large_trade_ratio(self):
        """Test large trade ratio calculation."""
        now = datetime.now(timezone.utc)
        trades = [
            Trade("t1", "TEST", now, 0.50, 100, TradeSide.BUY),  # Large
            Trade("t2", "TEST", now, 0.50, 20, TradeSide.BUY),   # Small
            Trade("t3", "TEST", now, 0.50, 30, TradeSide.BUY),   # Small
        ]
        self.pipeline.store.add_trades("TEST", trades)
        
        metrics = self.pipeline.compute_trade_metrics("TEST", window_minutes=60)
        
        # 100 large out of 150 total = 0.667
        assert metrics["large_trade_ratio"] == pytest.approx(100/150, rel=0.01)

    def test_trade_metrics_no_trades(self):
        """Test metrics return zeros when no trades."""
        metrics = self.pipeline.compute_trade_metrics("NONEXISTENT", window_minutes=60)
        
        assert metrics["trade_flow_imbalance"] == 0.0
        assert metrics["trade_clustering"] == 0.0
        assert metrics["price_velocity"] == 0.0
        assert metrics["volume_rate"] == 0.0

    def test_pipeline_fetches_and_stores(self):
        """Test pipeline fetches from API and stores."""
        self.mock_client.trades.get_trades.return_value = [
            self._create_api_trade("t1"),
            self._create_api_trade("t2"),
        ]
        
        history = self.pipeline.update_market("TEST")
        
        assert history is not None
        assert history.trade_count == 2
        self.mock_client.trades.get_trades.assert_called_once()

    def test_pipeline_handles_api_error(self):
        """Test pipeline handles API errors gracefully."""
        self.mock_client.trades.get_trades.side_effect = Exception("API Error")
        
        trades = self.pipeline.fetch_trades("TEST")
        
        assert trades == []  # Should return empty list, not raise


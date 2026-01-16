"""Tests for data models."""

import pytest
from datetime import datetime, timezone

from kalshi.models import (
    Market,
    MarketStatus,
    Trade,
    TradeSide,
    OrderBook,
    OrderBookLevel,
    MarketSnapshot,
)


class TestMarketSnapshot:
    """Tests for MarketSnapshot model."""

    def test_spread_calculation(self):
        """Test spread property."""
        snapshot = MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=0.45,
            best_ask=0.48,
        )
        assert snapshot.spread == pytest.approx(0.03)

    def test_spread_none_when_missing_quotes(self):
        """Test spread returns None when quotes missing."""
        snapshot = MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=0.45,
            best_ask=None,
        )
        assert snapshot.spread is None

    def test_depth_imbalance(self):
        """Test depth imbalance calculation."""
        snapshot = MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            total_bid_depth=100,
            total_ask_depth=50,
        )
        # (100 - 50) / (100 + 50) = 50/150 = 0.333
        assert snapshot.depth_imbalance == pytest.approx(0.333, rel=0.01)

    def test_kickoff_window_categorization(self):
        """Test kickoff window determination."""
        # Far (> 2 hours)
        snapshot = MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            time_to_kickoff_seconds=10000,
        )
        assert snapshot.kickoff_window == "far"

        # Approaching (2h to 10m)
        snapshot.time_to_kickoff_seconds = 3600
        assert snapshot.kickoff_window == "approaching"

        # Imminent (< 10m)
        snapshot.time_to_kickoff_seconds = 300
        assert snapshot.kickoff_window == "imminent"

        # Live (negative)
        snapshot.time_to_kickoff_seconds = -100
        assert snapshot.kickoff_window == "live"


class TestOrderBook:
    """Tests for OrderBook model."""

    def test_best_bid_ask(self):
        """Test best bid/ask extraction."""
        book = OrderBook(
            ticker="TEST-123",
            timestamp=datetime.now(timezone.utc),
            bids=[
                OrderBookLevel(price=0.45, quantity=100),
                OrderBookLevel(price=0.44, quantity=200),
            ],
            asks=[
                OrderBookLevel(price=0.48, quantity=150),
                OrderBookLevel(price=0.49, quantity=100),
            ],
        )
        assert book.best_bid == 0.45
        assert book.best_ask == 0.48

    def test_mid_price(self):
        """Test mid price calculation."""
        book = OrderBook(
            ticker="TEST-123",
            timestamp=datetime.now(timezone.utc),
            bids=[OrderBookLevel(price=0.45, quantity=100)],
            asks=[OrderBookLevel(price=0.48, quantity=150)],
        )
        assert book.mid_price == pytest.approx(0.465)

    def test_depth_imbalance(self):
        """Test order book depth imbalance."""
        book = OrderBook(
            ticker="TEST-123",
            timestamp=datetime.now(timezone.utc),
            bids=[
                OrderBookLevel(price=0.45, quantity=100),
                OrderBookLevel(price=0.44, quantity=100),
            ],
            asks=[
                OrderBookLevel(price=0.48, quantity=50),
            ],
        )
        # Bids: 200, Asks: 50
        # (200 - 50) / (200 + 50) = 0.6
        assert book.depth_imbalance == pytest.approx(0.6)


class TestTrade:
    """Tests for Trade model."""

    def test_trade_creation(self):
        """Test trade creation and properties."""
        trade = Trade(
            trade_id="trade-123",
            ticker="TEST-123",
            timestamp=datetime.now(timezone.utc),
            price=0.45,
            count=100,
            taker_side=TradeSide.BUY,
        )
        assert trade.is_buyer_initiated
        assert not trade.is_seller_initiated
        assert trade.notional == pytest.approx(45.0)


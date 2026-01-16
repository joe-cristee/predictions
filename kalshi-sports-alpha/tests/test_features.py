"""Tests for feature computation."""

import pytest
from datetime import datetime, timezone

from kalshi.models import MarketSnapshot, Trade, TradeSide
from features.microstructure.liquidity import (
    compute_spread,
    compute_depth_imbalance,
    compute_liquidity_score,
)
from features.microstructure.order_flow import (
    compute_trade_clustering,
    compute_large_trade_ratio,
)


class TestLiquidityFeatures:
    """Tests for liquidity features."""

    def test_compute_spread(self):
        """Test spread computation."""
        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=0.45,
            best_ask=0.48,
        )
        spread = compute_spread(snapshot)
        assert spread == pytest.approx(0.03)

    def test_compute_spread_returns_none(self):
        """Test spread returns None when quotes missing."""
        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=None,
            best_ask=0.48,
        )
        spread = compute_spread(snapshot)
        assert spread is None

    def test_compute_depth_imbalance_balanced(self):
        """Test depth imbalance with equal depth."""
        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            total_bid_depth=100,
            total_ask_depth=100,
        )
        imbalance = compute_depth_imbalance(snapshot)
        assert imbalance == 0.0

    def test_compute_depth_imbalance_bid_heavy(self):
        """Test depth imbalance with more bids."""
        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            total_bid_depth=150,
            total_ask_depth=50,
        )
        imbalance = compute_depth_imbalance(snapshot)
        assert imbalance == pytest.approx(0.5)  # (150-50)/(150+50)

    def test_compute_liquidity_score(self):
        """Test composite liquidity score."""
        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=0.48,
            best_ask=0.49,  # 1 cent spread
            total_bid_depth=500,
            total_ask_depth=500,
            volume_1h=250,
        )
        score = compute_liquidity_score(snapshot)
        assert 0 < score <= 1


class TestOrderFlowFeatures:
    """Tests for order flow features."""

    def create_trade(
        self,
        price: float,
        count: int,
        is_buy: bool,
        seconds_ago: int = 0
    ) -> Trade:
        """Helper to create test trades."""
        from datetime import timedelta
        return Trade(
            trade_id=f"trade-{seconds_ago}",
            ticker="TEST",
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago),
            price=price,
            count=count,
            taker_side=TradeSide.BUY if is_buy else TradeSide.SELL,
        )

    def test_large_trade_ratio_no_large(self):
        """Test large trade ratio with no large trades."""
        trades = [
            self.create_trade(0.45, 10, True),
            self.create_trade(0.46, 20, True),
            self.create_trade(0.45, 30, False),
        ]
        ratio = compute_large_trade_ratio(trades, size_threshold=100)
        assert ratio == 0.0

    def test_large_trade_ratio_all_large(self):
        """Test large trade ratio with all large trades."""
        trades = [
            self.create_trade(0.45, 150, True),
            self.create_trade(0.46, 200, True),
        ]
        ratio = compute_large_trade_ratio(trades, size_threshold=100)
        assert ratio == 1.0

    def test_large_trade_ratio_mixed(self):
        """Test large trade ratio with mixed sizes."""
        trades = [
            self.create_trade(0.45, 150, True),   # Large: 150
            self.create_trade(0.46, 50, True),    # Small: 50
        ]
        ratio = compute_large_trade_ratio(trades, size_threshold=100)
        assert ratio == pytest.approx(0.75)  # 150 / 200


"""Extended tests for behavioral and structural features."""

import pytest
from datetime import datetime, timezone

from kalshi.models import MarketSnapshot
from features.behavioral.overreaction import (
    compute_overreaction_score,
    compute_mean_reversion_signal,
    compute_overreaction_score_from_history,
    compute_mean_reversion_signal_from_history,
    detect_narrative_move,
    compute_contrarian_opportunity,
)
from features.microstructure.order_flow import (
    compute_trade_flow_imbalance,
    compute_trade_clustering,
    compute_large_trade_ratio,
    compute_price_velocity,
    compute_volume_rate,
)


class TestOverreactionScore:
    """Tests for overreaction score computation."""

    def _create_snapshot(
        self,
        best_bid: float = 0.45,
        best_ask: float = 0.48,
        total_bid_depth: int = 100,
        total_ask_depth: int = 100,
    ) -> MarketSnapshot:
        """Helper to create test snapshots."""
        return MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=best_bid,
            best_ask=best_ask,
            total_bid_depth=total_bid_depth,
            total_ask_depth=total_ask_depth,
        )

    def test_overreaction_low_spread_balanced(self):
        """Test low score when spread is narrow and depth balanced."""
        snapshot = self._create_snapshot(
            best_bid=0.49,
            best_ask=0.50,  # 1 cent spread
            total_bid_depth=100,
            total_ask_depth=100,  # Balanced
        )
        
        score = compute_overreaction_score(snapshot)
        
        assert score < 0.3, "Low spread + balanced depth should give low score"

    def test_overreaction_wide_spread(self):
        """Test higher score when spread is wide."""
        snapshot = self._create_snapshot(
            best_bid=0.40,
            best_ask=0.50,  # 10 cent spread
            total_bid_depth=100,
            total_ask_depth=100,
        )
        
        score = compute_overreaction_score(snapshot)
        
        assert score >= 0.5, "Wide spread should increase score"

    def test_overreaction_imbalanced_depth(self):
        """Test higher score when depth is imbalanced."""
        snapshot = self._create_snapshot(
            best_bid=0.49,
            best_ask=0.50,
            total_bid_depth=200,
            total_ask_depth=50,  # Heavy imbalance
        )
        
        score = compute_overreaction_score(snapshot)
        
        assert score >= 0.3, "Imbalanced depth should increase score"

    def test_overreaction_max_score_capped(self):
        """Test score is capped at 1.0."""
        snapshot = self._create_snapshot(
            best_bid=0.30,
            best_ask=0.50,  # 20 cent spread
            total_bid_depth=1000,
            total_ask_depth=10,  # Extreme imbalance
        )
        
        score = compute_overreaction_score(snapshot)
        
        assert score <= 1.0, "Score should be capped at 1.0"

    def test_overreaction_handles_none_spread(self):
        """Test handles missing spread gracefully."""
        snapshot = self._create_snapshot(
            best_bid=None,  # Missing
            best_ask=0.50,
        )
        
        score = compute_overreaction_score(snapshot)
        
        assert score >= 0.0  # Should still compute from imbalance


class TestMeanReversionSignal:
    """Tests for mean reversion signal computation."""

    def _create_snapshot(self, mid_price: float = 0.50) -> MarketSnapshot:
        """Helper to create test snapshots."""
        # Set bid/ask to create desired mid price
        spread = 0.02
        return MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=mid_price - spread/2,
            best_ask=mid_price + spread/2,
        )

    def test_mean_reversion_neutral_at_50(self):
        """Test signal is near zero at 50% price."""
        snapshot = self._create_snapshot(mid_price=0.50)
        
        signal = compute_mean_reversion_signal(snapshot)
        
        assert signal == pytest.approx(0.0, abs=0.05)

    def test_mean_reversion_positive_below_50(self):
        """Test positive signal when price below 50% (expect rise)."""
        snapshot = self._create_snapshot(mid_price=0.30)
        
        signal = compute_mean_reversion_signal(snapshot)
        
        assert signal > 0, "Should signal positive when price below 50%"

    def test_mean_reversion_negative_above_50(self):
        """Test negative signal when price above 50% (expect fall)."""
        snapshot = self._create_snapshot(mid_price=0.70)
        
        signal = compute_mean_reversion_signal(snapshot)
        
        assert signal < 0, "Should signal negative when price above 50%"

    def test_mean_reversion_clamped_to_range(self):
        """Test signal is clamped to [-1, 1]."""
        snapshot = self._create_snapshot(mid_price=0.10)
        
        signal = compute_mean_reversion_signal(snapshot)
        
        assert -1 <= signal <= 1

    def test_mean_reversion_handles_none(self):
        """Test handles missing mid_price."""
        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            best_bid=None,
            best_ask=None,
        )
        
        signal = compute_mean_reversion_signal(snapshot)
        
        assert signal == 0.0


class TestHistoricalOverreaction:
    """Tests for history-based overreaction computation."""

    def test_overreaction_from_history_high_price_low_volume(self):
        """Test high score when price moves without volume."""
        score = compute_overreaction_score_from_history(
            price_change=10,  # 10 cents
            volume_change=0.5,  # Half normal volume
            time_window_minutes=10,  # Fast move
        )
        
        assert score > 0.5, "High price/low volume should give high score"

    def test_overreaction_from_history_confirmed_by_volume(self):
        """Test low score when price move confirmed by volume."""
        score = compute_overreaction_score_from_history(
            price_change=10,
            volume_change=5.0,  # 5x normal volume
            time_window_minutes=30,
        )
        
        assert score < 0.5, "Volume-confirmed move should give low score"

    def test_overreaction_from_history_zero_volume(self):
        """Test handles zero volume."""
        score = compute_overreaction_score_from_history(
            price_change=10,
            volume_change=0,
        )
        
        assert score == 0.0


class TestHistoricalMeanReversion:
    """Tests for history-based mean reversion computation."""

    def test_mean_reversion_from_history_above_ma(self):
        """Test negative signal when price above MA."""
        signal = compute_mean_reversion_signal_from_history(
            current_price=0.60,
            moving_average=0.50,
            std_dev=0.05,
        )
        
        assert signal < 0, "Should signal negative when above MA"

    def test_mean_reversion_from_history_below_ma(self):
        """Test positive signal when price below MA."""
        signal = compute_mean_reversion_signal_from_history(
            current_price=0.40,
            moving_average=0.50,
            std_dev=0.05,
        )
        
        assert signal > 0, "Should signal positive when below MA"

    def test_mean_reversion_from_history_at_ma(self):
        """Test zero signal when at MA."""
        signal = compute_mean_reversion_signal_from_history(
            current_price=0.50,
            moving_average=0.50,
            std_dev=0.05,
        )
        
        assert signal == pytest.approx(0.0, abs=0.01)

    def test_mean_reversion_from_history_zero_std(self):
        """Test handles zero std dev."""
        signal = compute_mean_reversion_signal_from_history(
            current_price=0.60,
            moving_average=0.50,
            std_dev=0,
        )
        
        assert signal == 0.0


class TestNarrativeMoveDetection:
    """Tests for narrative vs informed move detection."""

    def test_detects_narrative_move(self):
        """Test detects high velocity / low volume as narrative."""
        result = detect_narrative_move(
            price_velocity=1.0,  # High
            volume_ratio=0.5,  # Low
            has_news=False,
        )
        
        assert result["is_narrative"] is True
        assert result["confidence"] > 0

    def test_not_narrative_with_volume(self):
        """Test doesn't flag as narrative when volume confirms."""
        result = detect_narrative_move(
            price_velocity=1.0,
            volume_ratio=3.0,  # High volume
            has_news=False,
        )
        
        assert result["is_narrative"] is False

    def test_not_narrative_with_news(self):
        """Test doesn't flag as narrative when news present."""
        result = detect_narrative_move(
            price_velocity=1.0,
            volume_ratio=0.5,
            has_news=True,  # News explains move
        )
        
        assert result["is_narrative"] is False
        assert result["confidence"] == 0.0

    def test_fade_signal_direction(self):
        """Test fade signal is opposite of move direction."""
        result_up = detect_narrative_move(price_velocity=1.0, volume_ratio=0.5)
        result_down = detect_narrative_move(price_velocity=-1.0, volume_ratio=0.5)
        
        assert result_up["fade_signal"] < 0  # Fade up move
        assert result_down["fade_signal"] > 0  # Fade down move


class TestContrarianOpportunity:
    """Tests for contrarian opportunity scoring."""

    def test_contrarian_opportunity_high(self):
        """Test high score with ideal conditions."""
        score = compute_contrarian_opportunity(
            overreaction_score=0.8,
            liquidity_score=0.9,
            time_to_kickoff=7200,  # 2 hours
        )
        
        assert score > 0.5

    def test_contrarian_opportunity_low_liquidity(self):
        """Test zero score when liquidity too low."""
        score = compute_contrarian_opportunity(
            overreaction_score=0.8,
            liquidity_score=0.2,  # Below 0.3 threshold
            time_to_kickoff=7200,
        )
        
        assert score == 0.0

    def test_contrarian_opportunity_time_scaling(self):
        """Test score scales with time to kickoff."""
        score_far = compute_contrarian_opportunity(
            overreaction_score=0.8,
            liquidity_score=0.9,
            time_to_kickoff=7200,  # 2 hours
        )
        score_near = compute_contrarian_opportunity(
            overreaction_score=0.8,
            liquidity_score=0.9,
            time_to_kickoff=1800,  # 30 minutes
        )
        
        assert score_far > score_near


class TestOrderFlowFeatures:
    """Tests for order flow features with trade history integration."""

    def _create_snapshot(
        self,
        total_bid_depth: int = 100,
        total_ask_depth: int = 100,
        volume_1m: int = 10,
        volume_5m: int = 50,
        last_trade_size: int = 25,
    ) -> MarketSnapshot:
        """Helper to create test snapshots."""
        return MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            total_bid_depth=total_bid_depth,
            total_ask_depth=total_ask_depth,
            volume_1m=volume_1m,
            volume_5m=volume_5m,
            last_trade_size=last_trade_size,
        )

    def test_trade_flow_imbalance_fallback(self):
        """Test trade flow imbalance uses depth as fallback."""
        snapshot = self._create_snapshot(
            total_bid_depth=150,
            total_ask_depth=50,
        )
        
        imbalance = compute_trade_flow_imbalance(snapshot)
        
        # Falls back to depth_imbalance: (150-50)/(150+50) = 0.5
        assert imbalance == pytest.approx(0.5, rel=0.01)

    def test_trade_clustering_fallback(self):
        """Test trade clustering uses volume ratio as fallback."""
        snapshot = self._create_snapshot(
            volume_1m=20,
            volume_5m=50,  # Ratio = 0.4, clustered
        )
        
        clustering = compute_trade_clustering(snapshot)
        
        assert clustering > 0.5  # High clustering

    def test_trade_clustering_zero_volume(self):
        """Test handles zero 5m volume."""
        snapshot = self._create_snapshot(
            volume_1m=10,
            volume_5m=0,
        )
        
        clustering = compute_trade_clustering(snapshot)
        
        assert clustering == 0.0

    def test_large_trade_ratio_fallback(self):
        """Test large trade ratio uses last_trade_size as fallback."""
        # Large trade
        snapshot_large = self._create_snapshot(last_trade_size=100)
        ratio_large = compute_large_trade_ratio(snapshot_large)
        
        # Small trade
        snapshot_small = self._create_snapshot(last_trade_size=20)
        ratio_small = compute_large_trade_ratio(snapshot_small)
        
        assert ratio_large > ratio_small

    def test_large_trade_ratio_none(self):
        """Test handles None last_trade_size."""
        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            last_trade_size=None,
        )
        
        ratio = compute_large_trade_ratio(snapshot)
        
        assert ratio == 0.0

    def test_price_velocity_returns_zero_without_history(self):
        """Test price velocity returns 0 when no history available."""
        snapshot = self._create_snapshot()
        
        velocity = compute_price_velocity(snapshot)
        
        # Without trade history pipeline, falls back to 0
        assert velocity == 0.0

    def test_volume_rate_fallback(self):
        """Test volume rate uses volume_1m as fallback."""
        snapshot = self._create_snapshot(volume_1m=30)
        
        rate = compute_volume_rate(snapshot)
        
        assert rate == 30.0


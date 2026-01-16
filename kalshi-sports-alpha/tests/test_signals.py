"""Tests for signal generators."""

import pytest
from datetime import datetime, timezone

from kalshi.models import MarketSnapshot
from signals import Signal, SignalDirection
from signals.tail_informed_flow import TailInformedFlowSignal
from signals.fade_overreaction import FadeOverreactionSignal


class TestSignalBase:
    """Tests for base Signal class."""

    def test_signal_creation(self):
        """Test signal creation and properties."""
        signal = Signal(
            name="test_signal",
            direction=SignalDirection.YES,
            strength=0.7,
            confidence=0.8,
            rationale="Test rationale",
        )
        assert signal.composite_score == pytest.approx(0.56)
        assert signal.is_actionable

    def test_signal_clamping(self):
        """Test that strength/confidence are clamped to 0-1."""
        signal = Signal(
            name="test_signal",
            direction=SignalDirection.YES,
            strength=1.5,
            confidence=-0.2,
            rationale="Test",
        )
        assert signal.strength == 1.0
        assert signal.confidence == 0.0

    def test_neutral_not_actionable(self):
        """Test that neutral signals are not actionable."""
        signal = Signal(
            name="test_signal",
            direction=SignalDirection.NEUTRAL,
            strength=0.9,
            confidence=0.9,
            rationale="Test",
        )
        assert not signal.is_actionable


class TestTailInformedFlowSignal:
    """Tests for TailInformedFlowSignal generator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = TailInformedFlowSignal()
        self.snapshot = MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
        )

    def test_no_signal_without_required_features(self):
        """Test that no signal is generated without required features."""
        features = {}
        signal = self.generator.generate(self.snapshot, features)
        assert signal is None

    def test_no_signal_low_clustering(self):
        """Test that low clustering doesn't trigger signal."""
        features = {
            "trade_clustering": 0.3,
            "spread": 0.02,
            "trade_flow_imbalance": 0.5,
            "price_impact_100": 0.01,
        }
        signal = self.generator.generate(self.snapshot, features)
        assert signal is None

    def test_generates_yes_signal_on_positive_flow(self):
        """Test YES signal on positive flow imbalance."""
        features = {
            "trade_clustering": 0.8,
            "spread": 0.02,
            "trade_flow_imbalance": 0.6,
            "price_impact_100": 0.01,
        }
        signal = self.generator.generate(self.snapshot, features)
        assert signal is not None
        assert signal.direction == SignalDirection.YES

    def test_generates_no_signal_on_negative_flow(self):
        """Test NO signal on negative flow imbalance."""
        features = {
            "trade_clustering": 0.8,
            "spread": 0.02,
            "trade_flow_imbalance": -0.6,
            "price_impact_100": 0.01,
        }
        signal = self.generator.generate(self.snapshot, features)
        assert signal is not None
        assert signal.direction == SignalDirection.NO


class TestFadeOverreactionSignal:
    """Tests for FadeOverreactionSignal generator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = FadeOverreactionSignal()
        self.snapshot = MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            time_to_kickoff_seconds=7200,  # 2 hours
        )

    def test_no_signal_near_kickoff(self):
        """Test no signal when too close to kickoff."""
        self.snapshot.time_to_kickoff_seconds = 600  # 10 minutes
        features = {
            "price_velocity": 1.0,
            "overreaction_score": 0.8,
        }
        signal = self.generator.generate(self.snapshot, features)
        assert signal is None

    def test_fades_upward_move(self):
        """Test fading an upward price move."""
        features = {
            "price_velocity": 1.0,  # Positive = up
            "overreaction_score": 0.7,
            "mean_reversion_signal": -0.5,
            "liquidity_score": 0.8,
        }
        signal = self.generator.generate(self.snapshot, features)
        assert signal is not None
        assert signal.direction == SignalDirection.NO  # Fade up = go NO


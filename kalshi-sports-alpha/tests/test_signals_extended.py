"""Extended tests for signal generators - LateKickoffVol and FragileMarket."""

import pytest
from datetime import datetime, timezone

from kalshi.models import MarketSnapshot
from signals import Signal, SignalDirection
from signals.late_kickoff_vol import LateKickoffVolSignal
from signals.fragile_market import FragileMarketSignal


class TestLateKickoffVolSignal:
    """Tests for LateKickoffVolSignal generator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = LateKickoffVolSignal(
            volatility_ratio_threshold=1.5,
            max_time_to_kickoff=600,  # 10 minutes
            min_imbalance=0.3,
            liquidity_warning=0.3,
        )

    def _create_snapshot(
        self,
        time_to_kickoff: int = 300,
        total_bid_depth: int = 100,
        total_ask_depth: int = 100,
    ) -> MarketSnapshot:
        """Helper to create test snapshots."""
        return MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            time_to_kickoff_seconds=time_to_kickoff,
            time_to_resolution_seconds=time_to_kickoff + 3600,
            total_bid_depth=total_bid_depth,
            total_ask_depth=total_ask_depth,
        )

    def test_no_signal_far_from_kickoff(self):
        """Test no signal when far from kickoff."""
        snapshot = self._create_snapshot(time_to_kickoff=7200)  # 2 hours
        features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": 0.5,
            "liquidity_score": 0.8,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal when far from kickoff"

    def test_no_signal_low_volatility(self):
        """Test no signal when volatility is normal."""
        snapshot = self._create_snapshot(time_to_kickoff=300)
        features = {
            "volatility_ratio": 1.0,  # Below threshold
            "depth_imbalance": 0.5,
            "liquidity_score": 0.8,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal when volatility is normal"

    def test_no_signal_low_imbalance(self):
        """Test no signal when order book is balanced."""
        snapshot = self._create_snapshot(time_to_kickoff=300)
        features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": 0.1,  # Below threshold
            "liquidity_score": 0.8,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal when order book balanced"

    def test_generates_yes_signal_positive_imbalance(self):
        """Test YES signal on positive depth imbalance (more bids)."""
        snapshot = self._create_snapshot(time_to_kickoff=300)
        features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": 0.5,  # Positive = more bids
            "liquidity_score": 0.8,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is not None
        assert signal.direction == SignalDirection.YES

    def test_generates_no_signal_negative_imbalance(self):
        """Test NO signal on negative depth imbalance (more asks)."""
        snapshot = self._create_snapshot(time_to_kickoff=300)
        features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": -0.5,  # Negative = more asks
            "liquidity_score": 0.8,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is not None
        assert signal.direction == SignalDirection.NO

    def test_low_liquidity_reduces_confidence(self):
        """Test low liquidity reduces signal confidence."""
        snapshot = self._create_snapshot(time_to_kickoff=300)
        
        # High liquidity signal
        high_liq_features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": 0.5,
            "liquidity_score": 0.8,
        }
        high_signal = self.generator.generate(snapshot, high_liq_features)
        
        # Low liquidity signal
        low_liq_features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": 0.5,
            "liquidity_score": 0.2,  # Below warning threshold
        }
        low_signal = self.generator.generate(snapshot, low_liq_features)
        
        assert high_signal is not None
        assert low_signal is not None
        assert low_signal.confidence < high_signal.confidence

    def test_no_signal_after_kickoff(self):
        """Test no signal when game already started."""
        snapshot = self._create_snapshot(time_to_kickoff=-300)  # Negative = live
        features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": 0.5,
            "liquidity_score": 0.8,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal after kickoff"

    def test_signal_has_correct_features_used(self):
        """Test signal tracks which features were used."""
        snapshot = self._create_snapshot(time_to_kickoff=300)
        features = {
            "volatility_ratio": 2.0,
            "depth_imbalance": 0.5,
            "liquidity_score": 0.8,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is not None
        assert "volatility_ratio" in signal.features_used
        assert "depth_imbalance" in signal.features_used


class TestFragileMarketSignal:
    """Tests for FragileMarketSignal generator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = FragileMarketSignal(
            max_depth=200,
            min_impact=0.03,
            max_time_to_resolution=7200,  # 2 hours
            min_edge=0.02,
        )

    def _create_snapshot(
        self,
        time_to_resolution: int = 3600,
        total_bid_depth: int = 50,
        total_ask_depth: int = 50,
    ) -> MarketSnapshot:
        """Helper to create test snapshots."""
        return MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            time_to_kickoff_seconds=time_to_resolution - 3600,
            time_to_resolution_seconds=time_to_resolution,
            total_bid_depth=total_bid_depth,
            total_ask_depth=total_ask_depth,
        )

    def test_no_signal_far_from_resolution(self):
        """Test no signal when far from resolution."""
        snapshot = self._create_snapshot(time_to_resolution=86400)  # 24 hours
        features = {
            "price_impact_100": 0.05,
            "implied_edge": 5.0,  # 5 cents edge
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal when far from resolution"

    def test_no_signal_deep_market(self):
        """Test no signal when market has sufficient depth."""
        snapshot = self._create_snapshot(
            time_to_resolution=3600,
            total_bid_depth=500,
            total_ask_depth=500,
        )
        features = {
            "price_impact_100": 0.05,
            "implied_edge": 5.0,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal when market is deep"

    def test_no_signal_low_impact(self):
        """Test no signal when price impact is low."""
        snapshot = self._create_snapshot(time_to_resolution=3600)
        features = {
            "price_impact_100": 0.01,  # Below threshold
            "implied_edge": 5.0,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal when impact is low"

    def test_no_signal_no_edge(self):
        """Test no signal when no edge detected."""
        snapshot = self._create_snapshot(time_to_resolution=3600)
        features = {
            "price_impact_100": 0.05,
            "implied_edge": 0.5,  # Below min_edge * 100 = 2 cents
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None, "Should not signal when no edge"

    def test_generates_yes_signal_positive_edge(self):
        """Test YES signal on positive implied edge."""
        snapshot = self._create_snapshot(time_to_resolution=3600)
        features = {
            "price_impact_100": 0.05,
            "implied_edge": 5.0,  # Positive edge
            "favorite_longshot_bias": 0,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is not None
        assert signal.direction == SignalDirection.YES

    def test_generates_no_signal_negative_edge(self):
        """Test NO signal on negative implied edge."""
        snapshot = self._create_snapshot(time_to_resolution=3600)
        features = {
            "price_impact_100": 0.05,
            "implied_edge": -5.0,  # Negative edge
            "favorite_longshot_bias": 0,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is not None
        assert signal.direction == SignalDirection.NO

    def test_signal_has_risk_metadata(self):
        """Test signal includes risk flags in metadata."""
        snapshot = self._create_snapshot(time_to_resolution=3600)
        features = {
            "price_impact_100": 0.05,
            "implied_edge": 5.0,
            "favorite_longshot_bias": 0,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is not None
        assert "risk_flags" in signal.metadata
        assert "illiquid" in signal.metadata["risk_flags"]

    def test_no_signal_missing_resolution_time(self):
        """Test no signal when time_to_resolution is None."""
        snapshot = MarketSnapshot(
            market_id="TEST-123",
            event_id="EVT-456",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            time_to_resolution_seconds=None,  # Missing
            total_bid_depth=50,
            total_ask_depth=50,
        )
        features = {
            "price_impact_100": 0.05,
            "implied_edge": 5.0,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is None

    def test_signal_tracks_features_used(self):
        """Test signal tracks which features were used."""
        snapshot = self._create_snapshot(time_to_resolution=3600)
        features = {
            "price_impact_100": 0.05,
            "implied_edge": 5.0,
            "favorite_longshot_bias": 0.1,
        }
        
        signal = self.generator.generate(snapshot, features)
        assert signal is not None
        assert "price_impact_100" in signal.features_used
        assert "implied_edge" in signal.features_used


class TestSignalFeaturesTracking:
    """Tests for signal features_used tracking across all generators."""

    def test_all_signals_track_features(self):
        """Test that all signal generators populate features_used."""
        from signals.tail_informed_flow import TailInformedFlowSignal
        from signals.fade_overreaction import FadeOverreactionSignal

        generators_and_features = [
            (
                TailInformedFlowSignal(),
                {
                    "trade_clustering": 0.8,
                    "spread": 0.02,
                    "trade_flow_imbalance": 0.6,
                    "price_impact_100": 0.01,
                },
            ),
            (
                FadeOverreactionSignal(),
                {
                    "price_velocity": 1.0,
                    "overreaction_score": 0.7,
                    "mean_reversion_signal": -0.5,
                    "liquidity_score": 0.8,
                },
            ),
        ]

        snapshot = MarketSnapshot(
            market_id="TEST",
            event_id="EVT",
            snapshot_time=datetime.now(timezone.utc),
            league="NFL",
            time_to_kickoff_seconds=7200,
        )

        for generator, features in generators_and_features:
            signal = generator.generate(snapshot, features)
            if signal is not None:
                assert len(signal.features_used) > 0, (
                    f"{generator.name} should populate features_used"
                )


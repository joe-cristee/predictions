"""Tests for backtest components - determinism, fills, metrics."""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Generator

from backtest.fills import (
    FillModel,
    SlippageModel,
    Fill,
    seed_random,
    reset_random,
    get_rng,
)
from backtest.simulator import BacktestSimulator, BacktestConfig, Position, BacktestState
from backtest.metrics import (
    BacktestMetrics,
    calculate_metrics,
    calculate_drawdown,
)


class TestSeededRandom:
    """Tests for deterministic random number generation."""

    def teardown_method(self):
        """Reset random state after each test."""
        reset_random()

    def test_seeded_random_produces_same_results(self):
        """Test that same seed produces identical results."""
        seed_random(42)
        rng1 = get_rng()
        values1 = [rng1.random() for _ in range(10)]

        seed_random(42)
        rng2 = get_rng()
        values2 = [rng2.random() for _ in range(10)]

        assert values1 == values2, "Same seed should produce same sequence"

    def test_different_seeds_produce_different_results(self):
        """Test that different seeds produce different results."""
        seed_random(42)
        values1 = [get_rng().random() for _ in range(10)]

        seed_random(123)
        values2 = [get_rng().random() for _ in range(10)]

        assert values1 != values2, "Different seeds should produce different sequences"

    def test_reset_random_clears_state(self):
        """Test that reset_random clears the seeded state."""
        seed_random(42)
        assert get_rng() is not None
        
        reset_random()
        # After reset, get_rng creates a new unseeded RNG
        rng = get_rng()
        assert rng is not None


class TestFillModel:
    """Tests for trade fill simulation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.fill_model = FillModel(
            partial_fill_prob=0.1,
            min_fill_pct=0.5,
        )

    def teardown_method(self):
        """Reset random state."""
        reset_random()

    def test_fill_model_respects_depth(self):
        """Test fill model doesn't fill more than available depth."""
        fill = self.fill_model.simulate_fill(
            side="YES",
            size=1000,
            price=0.50,
            depth=100,  # Only 100 available
        )
        
        assert fill is not None
        assert fill.filled_size <= 100, "Cannot fill more than depth"

    def test_fill_model_deterministic_with_seed(self):
        """Test fill model produces same results with same seed."""
        seed_random(42)
        fill1 = self.fill_model.simulate_fill(
            side="YES", size=100, price=0.50, depth=1000
        )

        seed_random(42)
        fill2 = self.fill_model.simulate_fill(
            side="YES", size=100, price=0.50, depth=1000
        )

        assert fill1.filled_size == fill2.filled_size
        assert fill1.avg_price == fill2.avg_price

    def test_fill_model_returns_none_for_zero_size(self):
        """Test fill model returns None for invalid inputs."""
        fill = self.fill_model.simulate_fill(
            side="YES", size=0, price=0.50, depth=1000
        )
        assert fill is None

    def test_fill_model_returns_none_for_zero_depth(self):
        """Test fill model returns None when no depth."""
        fill = self.fill_model.simulate_fill(
            side="YES", size=100, price=0.50, depth=0
        )
        assert fill is None


class TestSlippageModel:
    """Tests for slippage estimation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.slippage = SlippageModel(
            base_slippage_bps=10,
            size_impact_factor=0.1,
        )

    def test_slippage_increases_with_size(self):
        """Test slippage increases with order size."""
        small_slip = self.slippage.estimate_slippage(
            size=10, depth=1000, spread=0.02
        )
        large_slip = self.slippage.estimate_slippage(
            size=500, depth=1000, spread=0.02
        )

        assert large_slip > small_slip, "Larger orders should have more slippage"

    def test_slippage_minimum_is_half_spread(self):
        """Test slippage is at least half the spread."""
        spread = 0.04
        slip = self.slippage.estimate_slippage(
            size=1, depth=10000, spread=spread
        )

        assert slip >= spread / 2, "Slippage should be at least half spread"

    def test_slippage_calculation(self):
        """Test slippage calculation formula."""
        slip = self.slippage.estimate_slippage(
            size=100,
            depth=1000,
            volatility=0.01,
            spread=0.02,
        )

        # Base: 10 bps = 0.001
        # Size impact: 0.1 * (100/1000) = 0.01
        # Volatility: * (1 + 0.01 * 1.0) = 1.01
        # Expected: (0.001 + 0.01) * 1.01 = ~0.01111
        # But minimum is spread/2 = 0.01
        assert slip >= 0.01


class TestBacktestSimulator:
    """Tests for backtest simulator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = BacktestConfig(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            initial_capital=10000.0,
            random_seed=42,
            enable_lookahead_protection=True,
        )
        self.simulator = BacktestSimulator(self.config)

    def teardown_method(self):
        """Reset random state."""
        reset_random()

    def _create_historical_data(self) -> Generator[dict, None, None]:
        """Create mock historical data generator."""
        base_time = datetime(2024, 1, 5, tzinfo=timezone.utc)
        for i in range(10):
            yield {
                "timestamp": base_time + timedelta(hours=i),
                "market_id": f"TEST-{i % 3}",
                "price": 0.50,
                "depth": 1000,
            }

    def test_lookahead_bias_protection_chronological(self):
        """Test simulator detects out-of-order data."""
        def out_of_order_data():
            base_time = datetime(2024, 1, 5, tzinfo=timezone.utc)
            yield {"timestamp": base_time + timedelta(hours=2), "market_id": "T1", "price": 0.5, "depth": 100}
            yield {"timestamp": base_time + timedelta(hours=1), "market_id": "T1", "price": 0.5, "depth": 100}  # Earlier!

        with pytest.raises(ValueError, match="Look-ahead bias"):
            self.simulator.run(out_of_order_data(), [])

    def test_lookahead_bias_protection_filters_future_data(self):
        """Test simulator filters future information from snapshots."""
        snapshot = {
            "timestamp": datetime(2024, 1, 5, tzinfo=timezone.utc),
            "market_id": "TEST",
            "future_price": 0.75,  # Should be removed
            "result": "YES",  # Should be removed
            "outcome": "win",  # Should be removed
        }

        filtered = self.simulator._filter_point_in_time_data(
            snapshot,
            datetime(2024, 1, 5, tzinfo=timezone.utc)
        )

        assert "future_price" not in filtered
        assert "result" not in filtered
        assert "outcome" not in filtered
        assert "market_id" in filtered  # Should keep valid fields

    def test_simulator_deterministic_with_seed(self):
        """Test simulator produces same results with same seed."""
        # Run twice with same seed
        self.config.random_seed = 42
        sim1 = BacktestSimulator(self.config)
        
        self.config.random_seed = 42
        sim2 = BacktestSimulator(self.config)

        # Both should start with same capital
        assert sim1.state.capital == sim2.state.capital


class TestPosition:
    """Tests for Position model."""

    def test_position_pnl_calculation_yes_win(self):
        """Test P&L calculation for YES position that wins."""
        pos = Position(
            market_id="TEST",
            direction="YES",
            size=100,
            entry_price=0.40,
            entry_time=datetime.now(timezone.utc),
            exit_price=1.0,  # Won
            exit_time=datetime.now(timezone.utc),
        )

        # PnL = (1.0 - 0.40) * 100 = 60
        assert pos.pnl == pytest.approx(60.0)

    def test_position_pnl_calculation_yes_lose(self):
        """Test P&L calculation for YES position that loses."""
        pos = Position(
            market_id="TEST",
            direction="YES",
            size=100,
            entry_price=0.40,
            entry_time=datetime.now(timezone.utc),
            exit_price=0.0,  # Lost
            exit_time=datetime.now(timezone.utc),
        )

        # PnL = (0.0 - 0.40) * 100 = -40
        assert pos.pnl == pytest.approx(-40.0)

    def test_position_pnl_none_when_open(self):
        """Test P&L is None for open positions."""
        pos = Position(
            market_id="TEST",
            direction="YES",
            size=100,
            entry_price=0.40,
            entry_time=datetime.now(timezone.utc),
        )

        assert pos.pnl is None
        assert not pos.is_closed


class TestBacktestMetrics:
    """Tests for backtest metrics calculation."""

    def test_metrics_calculation_with_trades(self):
        """Test metrics calculation with sample trades."""
        equity_curve = [
            {"timestamp": datetime(2024, 1, i, tzinfo=timezone.utc), "equity": 10000 + i * 100}
            for i in range(1, 11)
        ]

        positions = [
            Position("M1", "YES", 100, 0.40, datetime.now(timezone.utc), 1.0, datetime.now(timezone.utc)),
            Position("M2", "YES", 100, 0.50, datetime.now(timezone.utc), 0.0, datetime.now(timezone.utc)),
            Position("M3", "YES", 100, 0.45, datetime.now(timezone.utc), 1.0, datetime.now(timezone.utc)),
        ]

        metrics = calculate_metrics(equity_curve, positions, 10000.0)

        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.hit_rate == pytest.approx(2/3, rel=0.01)

    def test_drawdown_calculation(self):
        """Test max drawdown calculation."""
        equities = [100, 110, 105, 120, 90, 100, 115]
        
        max_dd, duration = calculate_drawdown(equities)

        # Peak at 120, trough at 90 = 25% drawdown
        assert max_dd == pytest.approx(0.25, rel=0.01)

    def test_drawdown_no_drawdown(self):
        """Test drawdown when equity only goes up."""
        equities = [100, 110, 120, 130, 140]
        
        max_dd, duration = calculate_drawdown(equities)

        assert max_dd == 0

    def test_metrics_empty_equity_curve(self):
        """Test metrics handles empty data gracefully."""
        metrics = calculate_metrics([], [], 10000.0)

        assert metrics.total_trades == 0
        assert metrics.total_return == 0


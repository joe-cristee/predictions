"""Scenario definitions and batch testing."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable
import logging

from .simulator import BacktestSimulator, BacktestConfig
from .metrics import BacktestMetrics


logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    """Defines a backtest scenario."""

    name: str
    description: str
    start_date: datetime
    end_date: datetime

    # Configuration overrides
    initial_capital: float = 10000.0
    signal_weights: dict[str, float] = field(default_factory=dict)
    leagues: list[str] = field(default_factory=list)

    # Filters
    min_ev: Optional[float] = None
    max_time_to_kickoff: Optional[int] = None


@dataclass
class ScenarioResult:
    """Results from a scenario run."""

    scenario: Scenario
    metrics: BacktestMetrics
    run_time_seconds: float
    errors: list[str] = field(default_factory=list)


class ScenarioRunner:
    """Run multiple backtest scenarios."""

    def __init__(self, data_loader: Callable):
        """
        Initialize scenario runner.

        Args:
            data_loader: Callable that takes (start, end) and returns data generator
        """
        self.data_loader = data_loader
        self.results: list[ScenarioResult] = []

    def run_scenario(
        self,
        scenario: Scenario,
        signal_generators: list
    ) -> ScenarioResult:
        """
        Run a single scenario.

        Args:
            scenario: Scenario definition
            signal_generators: List of signal generators

        Returns:
            ScenarioResult
        """
        import time
        start_time = time.time()
        errors = []

        logger.info(f"Running scenario: {scenario.name}")

        try:
            # Create config
            config = BacktestConfig(
                start_date=scenario.start_date,
                end_date=scenario.end_date,
                initial_capital=scenario.initial_capital,
            )

            # Load data
            data = self.data_loader(scenario.start_date, scenario.end_date)

            # Run backtest
            simulator = BacktestSimulator(config)
            metrics = simulator.run(data, signal_generators)

        except Exception as e:
            logger.error(f"Scenario failed: {e}")
            errors.append(str(e))
            metrics = BacktestMetrics(
                total_return=0, annualized_return=0, sharpe_ratio=0,
                sortino_ratio=0, max_drawdown=0, max_drawdown_duration=0,
                volatility=0, total_trades=0, winning_trades=0,
                losing_trades=0, hit_rate=0, avg_win=0, avg_loss=0,
                profit_factor=0, avg_trade=0, avg_exposure=0,
                max_exposure=0, time_in_market=0,
            )

        run_time = time.time() - start_time

        result = ScenarioResult(
            scenario=scenario,
            metrics=metrics,
            run_time_seconds=run_time,
            errors=errors,
        )

        self.results.append(result)
        return result

    def run_all(
        self,
        scenarios: list[Scenario],
        signal_generators: list
    ) -> list[ScenarioResult]:
        """Run multiple scenarios."""
        results = []
        for scenario in scenarios:
            result = self.run_scenario(scenario, signal_generators)
            results.append(result)
        return results

    def compare_results(self) -> dict:
        """Compare results across scenarios."""
        if not self.results:
            return {}

        comparison = {}
        for result in self.results:
            comparison[result.scenario.name] = {
                "total_return": result.metrics.total_return,
                "sharpe": result.metrics.sharpe_ratio,
                "max_dd": result.metrics.max_drawdown,
                "trades": result.metrics.total_trades,
                "hit_rate": result.metrics.hit_rate,
            }

        return comparison


# Pre-defined scenarios
STANDARD_SCENARIOS = [
    Scenario(
        name="full_sample",
        description="Full historical sample",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
    ),
    Scenario(
        name="nfl_season",
        description="NFL 2024 regular season",
        start_date=datetime(2024, 9, 5),
        end_date=datetime(2025, 1, 5),
        leagues=["NFL"],
    ),
    Scenario(
        name="nba_season",
        description="NBA 2024-25 season",
        start_date=datetime(2024, 10, 22),
        end_date=datetime(2025, 4, 13),
        leagues=["NBA"],
    ),
    Scenario(
        name="high_ev_only",
        description="Only high EV opportunities",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        min_ev=0.05,
    ),
]


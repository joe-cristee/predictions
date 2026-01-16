"""Trade replay engine for backtesting."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Generator
import logging

from strategy.ranker import Recommendation
from .fills import FillModel, Fill
from .metrics import BacktestMetrics


logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest."""

    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    max_position_pct: float = 0.05  # Max 5% per position
    include_fees: bool = True
    fee_per_contract: float = 0.01  # $0.01 per contract


@dataclass
class Position:
    """Represents an open position."""

    market_id: str
    direction: str
    size: int
    entry_price: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None

    @property
    def is_closed(self) -> bool:
        return self.exit_price is not None

    @property
    def pnl(self) -> Optional[float]:
        if self.exit_price is None:
            return None
        if self.direction == "YES":
            return (self.exit_price - self.entry_price) * self.size
        else:
            return (self.entry_price - self.exit_price) * self.size


@dataclass
class BacktestState:
    """Current state of backtest."""

    capital: float
    positions: list[Position] = field(default_factory=list)
    closed_positions: list[Position] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)

    @property
    def equity(self) -> float:
        """Current equity including unrealized P&L."""
        # For simplicity, just return capital
        # Full implementation would mark positions to market
        return self.capital

    @property
    def total_pnl(self) -> float:
        """Total realized P&L."""
        return sum(p.pnl or 0 for p in self.closed_positions)


class BacktestSimulator:
    """
    Trade replay engine for historical backtesting.

    Simulates signal generation and trade execution on historical data.
    """

    def __init__(
        self,
        config: BacktestConfig,
        fill_model: Optional[FillModel] = None
    ):
        self.config = config
        self.fill_model = fill_model or FillModel()
        self.state = BacktestState(capital=config.initial_capital)

    def run(
        self,
        historical_data: Generator[dict, None, None],
        signal_generators: list,
    ) -> BacktestMetrics:
        """
        Run backtest on historical data.

        Args:
            historical_data: Generator yielding historical snapshots
            signal_generators: List of signal generators to use

        Returns:
            BacktestMetrics with results
        """
        logger.info(
            f"Starting backtest from {self.config.start_date} "
            f"to {self.config.end_date}"
        )

        equity_curve = []

        for snapshot in historical_data:
            timestamp = snapshot.get("timestamp")

            # Skip if outside date range
            if timestamp < self.config.start_date:
                continue
            if timestamp > self.config.end_date:
                break

            # Check for position exits (settlements)
            self._check_settlements(snapshot)

            # Generate signals
            signals = self._generate_signals(snapshot, signal_generators)

            # Execute trades
            for signal in signals:
                self._execute_signal(signal, snapshot)

            # Record equity
            equity_curve.append({
                "timestamp": timestamp,
                "equity": self.state.equity,
            })

        # Calculate final metrics
        return self._calculate_metrics(equity_curve)

    def _generate_signals(self, snapshot: dict, generators: list) -> list:
        """Generate signals from snapshot."""
        signals = []
        for gen in generators:
            try:
                signal = gen.generate(snapshot)
                if signal is not None:
                    signals.append(signal)
            except Exception as e:
                logger.warning(f"Signal generation failed: {e}")
        return signals

    def _execute_signal(self, signal, snapshot: dict) -> None:
        """Execute a signal by opening a position."""
        # Size the position
        max_size = self.state.capital * self.config.max_position_pct
        size = min(signal.max_size, max_size)

        if size < 10:  # Minimum size
            return

        # Simulate fill
        fill = self.fill_model.simulate_fill(
            side=signal.direction,
            size=size,
            price=snapshot.get("price", 0.5),
            depth=snapshot.get("depth", 1000),
        )

        if fill is None:
            return

        # Create position
        position = Position(
            market_id=snapshot.get("market_id", ""),
            direction=signal.direction,
            size=fill.filled_size,
            entry_price=fill.avg_price,
            entry_time=snapshot.get("timestamp"),
        )

        # Update state
        cost = fill.filled_size * fill.avg_price
        if self.config.include_fees:
            cost += fill.filled_size * self.config.fee_per_contract

        self.state.capital -= cost
        self.state.positions.append(position)
        self.state.fills.append(fill)

    def _check_settlements(self, snapshot: dict) -> None:
        """Check for and process position settlements."""
        settled_markets = snapshot.get("settled_markets", [])

        for position in self.state.positions[:]:
            if position.market_id in settled_markets:
                result = settled_markets[position.market_id]

                # Determine payout
                if position.direction == result:
                    payout = position.size * 1.0  # Full payout
                else:
                    payout = 0

                position.exit_price = 1.0 if position.direction == result else 0.0
                position.exit_time = snapshot.get("timestamp")

                self.state.capital += payout
                self.state.positions.remove(position)
                self.state.closed_positions.append(position)

    def _calculate_metrics(self, equity_curve: list) -> BacktestMetrics:
        """Calculate backtest metrics from results."""
        from .metrics import calculate_metrics

        return calculate_metrics(
            equity_curve=equity_curve,
            positions=self.state.closed_positions,
            initial_capital=self.config.initial_capital,
        )


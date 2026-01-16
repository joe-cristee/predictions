"""Backtest metrics - Sharpe, drawdown, hit rate, etc."""

from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class BacktestMetrics:
    """Comprehensive backtest performance metrics."""

    # Returns
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float

    # Risk
    max_drawdown: float
    max_drawdown_duration: int  # In days
    volatility: float

    # Trading
    total_trades: int
    winning_trades: int
    losing_trades: int
    hit_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avg_trade: float

    # Exposure
    avg_exposure: float
    max_exposure: float
    time_in_market: float  # Percentage

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_return": f"{self.total_return:.2%}",
            "annualized_return": f"{self.annualized_return:.2%}",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "sortino_ratio": f"{self.sortino_ratio:.2f}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "volatility": f"{self.volatility:.2%}",
            "total_trades": self.total_trades,
            "hit_rate": f"{self.hit_rate:.1%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "avg_trade": f"${self.avg_trade:.2f}",
        }

    def summary(self) -> str:
        """Generate summary string."""
        return f"""
Backtest Results
================
Total Return: {self.total_return:.2%}
Annualized Return: {self.annualized_return:.2%}
Sharpe Ratio: {self.sharpe_ratio:.2f}
Max Drawdown: {self.max_drawdown:.2%}

Trading Statistics
------------------
Total Trades: {self.total_trades}
Win Rate: {self.hit_rate:.1%}
Profit Factor: {self.profit_factor:.2f}
Average Trade: ${self.avg_trade:.2f}
"""


def calculate_metrics(
    equity_curve: list[dict],
    positions: list,
    initial_capital: float,
    risk_free_rate: float = 0.02,  # 2% annual
) -> BacktestMetrics:
    """
    Calculate comprehensive backtest metrics.

    Args:
        equity_curve: List of {timestamp, equity} dicts
        positions: List of closed positions
        initial_capital: Starting capital
        risk_free_rate: Annual risk-free rate for Sharpe

    Returns:
        BacktestMetrics object
    """
    if not equity_curve:
        return _empty_metrics()

    # Extract equity values
    equities = [e["equity"] for e in equity_curve]
    final_equity = equities[-1]

    # Returns
    total_return = (final_equity - initial_capital) / initial_capital

    # Calculate daily returns
    returns = []
    for i in range(1, len(equities)):
        if equities[i - 1] > 0:
            ret = (equities[i] - equities[i - 1]) / equities[i - 1]
            returns.append(ret)

    if not returns:
        return _empty_metrics()

    # Annualized metrics (assume 252 trading days)
    mean_return = sum(returns) / len(returns)
    annualized_return = mean_return * 252

    # Volatility
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    daily_vol = math.sqrt(variance)
    volatility = daily_vol * math.sqrt(252)

    # Sharpe ratio
    if volatility > 0:
        sharpe = (annualized_return - risk_free_rate) / volatility
    else:
        sharpe = 0

    # Sortino ratio (downside deviation)
    negative_returns = [r for r in returns if r < 0]
    if negative_returns:
        downside_var = sum(r ** 2 for r in negative_returns) / len(negative_returns)
        downside_vol = math.sqrt(downside_var) * math.sqrt(252)
        sortino = (annualized_return - risk_free_rate) / downside_vol if downside_vol > 0 else 0
    else:
        sortino = sharpe  # No downside

    # Drawdown
    max_dd, max_dd_duration = calculate_drawdown(equities)

    # Trading statistics
    total_trades = len(positions)
    pnls = [p.pnl or 0 for p in positions]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    winning_trades = len(wins)
    losing_trades = len(losses)
    hit_rate = winning_trades / total_trades if total_trades > 0 else 0

    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    avg_trade = sum(pnls) / len(pnls) if pnls else 0

    # Profit factor
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Exposure (simplified)
    avg_exposure = initial_capital * 0.3  # Placeholder
    max_exposure = initial_capital * 0.5
    time_in_market = 0.5

    return BacktestMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=max_dd,
        max_drawdown_duration=max_dd_duration,
        volatility=volatility,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        hit_rate=hit_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        avg_trade=avg_trade,
        avg_exposure=avg_exposure,
        max_exposure=max_exposure,
        time_in_market=time_in_market,
    )


def calculate_drawdown(equities: list[float]) -> tuple[float, int]:
    """
    Calculate maximum drawdown and duration.

    Returns:
        (max_drawdown, duration_in_periods)
    """
    if not equities:
        return 0, 0

    peak = equities[0]
    max_dd = 0
    max_duration = 0
    current_duration = 0

    for equity in equities:
        if equity > peak:
            peak = equity
            current_duration = 0
        else:
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)
            current_duration += 1
            max_duration = max(max_duration, current_duration)

    return max_dd, max_duration


def _empty_metrics() -> BacktestMetrics:
    """Return empty metrics object."""
    return BacktestMetrics(
        total_return=0,
        annualized_return=0,
        sharpe_ratio=0,
        sortino_ratio=0,
        max_drawdown=0,
        max_drawdown_duration=0,
        volatility=0,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        hit_rate=0,
        avg_win=0,
        avg_loss=0,
        profit_factor=0,
        avg_trade=0,
        avg_exposure=0,
        max_exposure=0,
        time_in_market=0,
    )


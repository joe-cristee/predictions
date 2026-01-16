"""Position and P&L reconciliation - Phase 2 stub."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging


logger = logging.getLogger(__name__)


@dataclass
class PositionRecord:
    """Record of a position for reconciliation."""

    market_id: str
    side: str
    size: int
    avg_price: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None


@dataclass
class ReconciliationResult:
    """Result of a reconciliation check."""

    timestamp: datetime
    is_matched: bool
    local_positions: list[PositionRecord]
    exchange_positions: list[dict]
    discrepancies: list[str]


class Reconciliation:
    """
    Position and P&L reconciliation with exchange.
    
    Phase 2 implementation - currently stubbed.
    
    Compares local position tracking with exchange records.
    """

    def __init__(self, client=None):
        """
        Initialize reconciliation.

        Args:
            client: Kalshi API client
        """
        self.client = client
        self.local_positions: dict[str, PositionRecord] = {}
        self.last_reconciliation: Optional[ReconciliationResult] = None

    def update_local_position(
        self,
        market_id: str,
        side: str,
        size_delta: int,
        price: float
    ) -> None:
        """
        Update local position tracking.

        Args:
            market_id: Market identifier
            side: Position side
            size_delta: Change in position size
            price: Execution price
        """
        key = f"{market_id}_{side}"

        if key in self.local_positions:
            pos = self.local_positions[key]
            # Update average price
            total_cost = pos.avg_price * pos.size + price * size_delta
            pos.size += size_delta
            if pos.size > 0:
                pos.avg_price = total_cost / pos.size
        else:
            self.local_positions[key] = PositionRecord(
                market_id=market_id,
                side=side,
                size=size_delta,
                avg_price=price,
            )

    def fetch_exchange_positions(self) -> list[dict]:
        """Fetch positions from exchange."""
        # TODO: Implement API call
        # return self.client.portfolio.get_positions()
        raise NotImplementedError("Exchange position fetch not implemented")

    def reconcile(self) -> ReconciliationResult:
        """
        Perform reconciliation between local and exchange positions.

        Returns:
            ReconciliationResult with any discrepancies
        """
        try:
            exchange_positions = self.fetch_exchange_positions()
        except NotImplementedError:
            logger.warning("Exchange reconciliation not available")
            return ReconciliationResult(
                timestamp=datetime.now(),
                is_matched=False,
                local_positions=list(self.local_positions.values()),
                exchange_positions=[],
                discrepancies=["exchange_fetch_not_implemented"],
            )

        discrepancies = []

        # Compare positions
        exchange_by_market = {p["ticker"]: p for p in exchange_positions}

        for key, local_pos in self.local_positions.items():
            exchange_pos = exchange_by_market.get(local_pos.market_id)

            if exchange_pos is None:
                discrepancies.append(
                    f"Local position {local_pos.market_id} not found on exchange"
                )
            elif exchange_pos.get("position") != local_pos.size:
                discrepancies.append(
                    f"Size mismatch for {local_pos.market_id}: "
                    f"local={local_pos.size}, exchange={exchange_pos.get('position')}"
                )

        # Check for exchange positions not in local
        for ticker, exchange_pos in exchange_by_market.items():
            local_key = f"{ticker}_{exchange_pos.get('side', 'YES')}"
            if local_key not in self.local_positions:
                discrepancies.append(
                    f"Exchange position {ticker} not found locally"
                )

        result = ReconciliationResult(
            timestamp=datetime.now(),
            is_matched=len(discrepancies) == 0,
            local_positions=list(self.local_positions.values()),
            exchange_positions=exchange_positions,
            discrepancies=discrepancies,
        )

        self.last_reconciliation = result

        if not result.is_matched:
            logger.warning(f"Reconciliation failed: {discrepancies}")

        return result

    def get_pnl_summary(self) -> dict:
        """Get P&L summary for all positions."""
        realized_pnl = 0
        unrealized_pnl = 0

        for pos in self.local_positions.values():
            if pos.current_price is not None:
                if pos.side == "YES":
                    pos.unrealized_pnl = (pos.current_price - pos.avg_price) * pos.size
                else:
                    pos.unrealized_pnl = (pos.avg_price - pos.current_price) * pos.size
                unrealized_pnl += pos.unrealized_pnl

        return {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": realized_pnl + unrealized_pnl,
            "positions": len(self.local_positions),
        }


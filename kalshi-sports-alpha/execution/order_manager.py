"""Order management - Phase 2 stub."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import logging


logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status states."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class Order:
    """Represents an order."""

    order_id: str
    market_id: str
    side: str  # "YES" or "NO"
    size: int
    order_type: OrderType
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_size: int = 0
    avg_fill_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


class OrderManager:
    """
    Manages order lifecycle.
    
    Phase 2 implementation - currently stubbed.
    
    Requirements for full implementation:
    - Idempotent order placement
    - Kill-switch per market
    - Exposure caps per league
    - Manual approval toggle
    """

    def __init__(self, client=None, auto_execute: bool = False):
        """
        Initialize order manager.

        Args:
            client: Kalshi API client
            auto_execute: Whether to auto-execute orders (False = manual approval)
        """
        self.client = client
        self.auto_execute = auto_execute
        self.orders: dict[str, Order] = {}
        self._kill_switches: set[str] = set()  # Markets with kill switch active

    def create_order(
        self,
        market_id: str,
        side: str,
        size: int,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: Optional[float] = None,
    ) -> Order:
        """
        Create a new order.

        Args:
            market_id: Market ticker
            side: "YES" or "NO"
            size: Number of contracts
            order_type: Market or limit
            limit_price: Price for limit orders

        Returns:
            Created Order object
        """
        # Check kill switch
        if market_id in self._kill_switches:
            raise ValueError(f"Kill switch active for {market_id}")

        order_id = f"ord_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        order = Order(
            order_id=order_id,
            market_id=market_id,
            side=side,
            size=size,
            order_type=order_type,
            limit_price=limit_price,
        )

        self.orders[order_id] = order
        logger.info(f"Created order {order_id}: {side} {size} @ {limit_price}")

        return order

    def submit_order(self, order_id: str) -> bool:
        """
        Submit an order to the exchange.

        Args:
            order_id: Order ID to submit

        Returns:
            Success status
        """
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        if not self.auto_execute:
            logger.info(f"Order {order_id} requires manual approval")
            return False

        # TODO: Implement actual API submission
        # response = self.client.orders.create(
        #     ticker=order.market_id,
        #     side=order.side,
        #     count=order.size,
        #     type=order.order_type.value,
        #     price=int(order.limit_price * 100) if order.limit_price else None,
        # )

        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.now()

        raise NotImplementedError("Order submission not yet implemented")

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        order = self.orders.get(order_id)
        if not order:
            return False

        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
            return False

        # TODO: Implement API cancellation
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()

        logger.info(f"Cancelled order {order_id}")
        return True

    def activate_kill_switch(self, market_id: str) -> None:
        """Activate kill switch for a market."""
        self._kill_switches.add(market_id)
        logger.warning(f"Kill switch activated for {market_id}")

        # Cancel all pending orders for this market
        for order in self.orders.values():
            if order.market_id == market_id and order.status == OrderStatus.PENDING:
                self.cancel_order(order.order_id)

    def deactivate_kill_switch(self, market_id: str) -> None:
        """Deactivate kill switch for a market."""
        self._kill_switches.discard(market_id)
        logger.info(f"Kill switch deactivated for {market_id}")

    def get_open_orders(self) -> list[Order]:
        """Get all open orders."""
        return [
            o for o in self.orders.values()
            if o.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)
        ]


"""Kalshi API endpoint fetchers for markets, trades, and order books."""

from typing import Any, Optional
from datetime import datetime


class MarketEndpoints:
    """Endpoints for fetching market data."""

    def __init__(self, client):
        self.client = client

    def get_markets(
        self,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
    ) -> list[dict]:
        """Fetch markets with optional filters."""
        params = {}
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker

        return self.client.paginate("/markets", params)

    def get_market(self, ticker: str) -> dict:
        """Fetch a single market by ticker."""
        return self.client.get(f"/markets/{ticker}")

    def get_events(self, series_ticker: Optional[str] = None) -> list[dict]:
        """Fetch events with optional series filter."""
        params = {}
        if series_ticker:
            params["series_ticker"] = series_ticker
        return self.client.paginate("/events", params)


class TradeEndpoints:
    """Endpoints for fetching trade data."""

    def __init__(self, client):
        self.client = client

    def get_trades(
        self,
        ticker: Optional[str] = None,
        min_ts: Optional[datetime] = None,
        max_ts: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Fetch recent trades with optional filters."""
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = int(min_ts.timestamp())
        if max_ts:
            params["max_ts"] = int(max_ts.timestamp())

        return self.client.paginate("/trades", params)


class OrderBookEndpoints:
    """Endpoints for fetching order book data."""

    def __init__(self, client):
        self.client = client

    def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        """Fetch order book for a market."""
        return self.client.get(f"/markets/{ticker}/orderbook", {"depth": depth})

    def get_orderbooks_batch(self, tickers: list[str], depth: int = 10) -> dict[str, dict]:
        """Fetch order books for multiple markets."""
        return {ticker: self.get_orderbook(ticker, depth) for ticker in tickers}


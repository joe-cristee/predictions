"""Kalshi API client with authentication, retries, and pagination."""

from typing import Any, Optional
import requests
from .rate_limit import RateLimiter


class KalshiClient:
    """Main client for interacting with the Kalshi API."""

    BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = requests.Session()
        self._token: Optional[str] = None

    def authenticate(self) -> None:
        """Authenticate with Kalshi and obtain session token."""
        # TODO: Implement authentication flow
        raise NotImplementedError

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Any:
        """Make an authenticated request to the API."""
        self.rate_limiter.wait()

        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    def _get_headers(self) -> dict:
        """Get headers for authenticated requests."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[dict] = None) -> Any:
        """Make a POST request."""
        return self._request("POST", endpoint, data=data)

    def paginate(self, endpoint: str, params: Optional[dict] = None) -> list:
        """Paginate through all results from an endpoint."""
        results = []
        cursor = None
        params = params or {}

        while True:
            if cursor:
                params["cursor"] = cursor

            response = self.get(endpoint, params)
            results.extend(response.get("markets", response.get("trades", [])))

            cursor = response.get("cursor")
            if not cursor:
                break

        return results


"""Kalshi API client with authentication, retries, and pagination."""

from typing import Any, Optional
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from .rate_limit import RateLimiter


class KalshiClient:
    """Main client for interacting with the Kalshi API."""

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key_pem: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.api_key = api_key
        self.private_key_pem = private_key_pem
        self.private_key = None
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = requests.Session()
        
        # Load private key if provided
        if private_key_pem:
            self._load_private_key(private_key_pem)
        
        # Initialize endpoint accessors (will be set after import)
        self._markets = None
        self._trades = None
        self._orderbook = None

    def _load_private_key(self, pem_data: str) -> None:
        """Load RSA private key from PEM string."""
        self.private_key = serialization.load_pem_private_key(
            pem_data.encode(),
            password=None,
            backend=default_backend()
        )

    def _sign_request(self, method: str, path: str, timestamp: int) -> str:
        """
        Sign a request using RSA-PSS.
        
        The signature is computed over: timestamp + method + path
        """
        if not self.private_key:
            raise ValueError("Private key not loaded - cannot sign request")
        
        message = f"{timestamp}{method}{path}"
        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        import base64
        return base64.b64encode(signature).decode()

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
        headers = self._get_headers(method, endpoint)

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    def _get_headers(self, method: str = "GET", endpoint: str = "") -> dict:
        """Get headers for authenticated requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Add authentication headers if we have credentials
        if self.api_key and self.private_key:
            timestamp = int(time.time() * 1000)  # milliseconds
            signature = self._sign_request(method, endpoint, timestamp)
            
            headers["KALSHI-ACCESS-KEY"] = self.api_key
            headers["KALSHI-ACCESS-SIGNATURE"] = signature
            headers["KALSHI-ACCESS-TIMESTAMP"] = str(timestamp)
        
        return headers
    
    @property
    def markets(self):
        """Access market endpoints."""
        if self._markets is None:
            from .endpoints import MarketEndpoints
            self._markets = MarketEndpoints(self)
        return self._markets
    
    @property
    def trades(self):
        """Access trade endpoints."""
        if self._trades is None:
            from .endpoints import TradeEndpoints
            self._trades = TradeEndpoints(self)
        return self._trades
    
    @property
    def orderbook(self):
        """Access orderbook endpoints."""
        if self._orderbook is None:
            from .endpoints import OrderBookEndpoints
            self._orderbook = OrderBookEndpoints(self)
        return self._orderbook

    def get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[dict] = None) -> Any:
        """Make a POST request."""
        return self._request("POST", endpoint, data=data)

    def paginate(self, endpoint: str, params: Optional[dict] = None, limit: int = 200) -> list:
        """Paginate through all results from an endpoint."""
        results = []
        cursor = None
        params = params or {}
        params["limit"] = limit

        while True:
            if cursor:
                params["cursor"] = cursor

            response = self.get(endpoint, params)
            
            # Handle different response formats
            if "markets" in response:
                results.extend(response["markets"])
            elif "trades" in response:
                results.extend(response["trades"])
            elif "events" in response:
                results.extend(response["events"])
            else:
                # Single result or unknown format
                results.append(response)

            cursor = response.get("cursor")
            if not cursor:
                break

        return results


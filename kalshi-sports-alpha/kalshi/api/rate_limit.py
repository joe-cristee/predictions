"""Rate limiting for Kalshi API requests."""

import time
from collections import deque
from threading import Lock


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_second: float = 10.0, burst: int = 20):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Sustained request rate
            burst: Maximum burst size
        """
        self.rate = requests_per_second
        self.burst = burst
        self.tokens = burst
        self.last_update = time.monotonic()
        self.lock = Lock()

    def wait(self) -> None:
        """Wait until a request can be made."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                sleep_time = (1 - self.tokens) / self.rate
                time.sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for more precise control."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        """
        Initialize sliding window rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Window duration in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self.lock = Lock()

    def wait(self) -> None:
        """Wait until a request can be made."""
        with self.lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds

            # Remove old requests
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] - cutoff
                time.sleep(max(0, sleep_time))
                # Re-check after sleeping
                now = time.monotonic()
                cutoff = now - self.window_seconds
                while self.requests and self.requests[0] < cutoff:
                    self.requests.popleft()

            self.requests.append(now)


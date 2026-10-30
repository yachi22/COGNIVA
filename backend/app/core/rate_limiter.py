import asyncio
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Optional
from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """
    Zero-additional-cost in-memory sliding-window rate limiter.
    Maintains timestamp deques per client identifier and bounds request frequency.
    Periodically purges stale entries to prevent memory growth.
    """

    def __init__(self, max_requests: int, window_seconds: int, scope: str = "default"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope
        self._history: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    def _get_client_key(self, request: Request, user_id: Optional[str] = None) -> str:
        """Derives a safe key based on user ID or client IP address."""
        if user_id:
            return f"{self.scope}:user:{user_id}"

        # Resolve client IP (accounting for trusted reverse proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"{self.scope}:ip:{client_ip}"

    def _cleanup_stale(self, now: float) -> None:
        """Purges client records that have had no activity within the window."""
        cutoff = now - self.window_seconds
        stale_keys = []
        for key, dq in self._history.items():
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if not dq:
                stale_keys.append(key)
        for k in stale_keys:
            self._history.pop(k, None)

    async def check(self, request: Request, user_id: Optional[str] = None) -> None:
        """
        Evaluates rate limit for the incoming request.
        Raises HTTP 429 Too Many Requests with Retry-After header if limit exceeded.
        """
        now = time.monotonic()
        client_key = self._get_client_key(request, user_id)

        async with self._lock:
            # Run periodic cleanup every 60 seconds
            if now - self._last_cleanup > 60.0:
                self._cleanup_stale(now)
                self._last_cleanup = now

            dq = self._history[client_key]
            cutoff = now - self.window_seconds

            # Evict timestamps outside the active sliding window
            while dq and dq[0] <= cutoff:
                dq.popleft()

            if len(dq) >= self.max_requests:
                oldest = dq[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {self.scope}. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

            dq.append(now)

    def reset(self) -> None:
        """Clears all rate limit state (useful for test isolation)."""
        self._history.clear()


# Pre-configured instances for different sensitive operation scopes
auth_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60, scope="auth")
upload_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, scope="upload")
llm_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, scope="llm")


# FastAPI dependency helpers
async def rate_limit_auth(request: Request) -> None:
    await auth_limiter.check(request)


async def rate_limit_upload(request: Request) -> None:
    # Resolve user ID from state if available
    user = getattr(request.state, "user", None)
    user_id = str(user.id) if user and hasattr(user, "id") else None
    await upload_limiter.check(request, user_id=user_id)


async def rate_limit_llm(request: Request) -> None:
    user = getattr(request.state, "user", None)
    user_id = str(user.id) if user and hasattr(user, "id") else None
    await llm_limiter.check(request, user_id=user_id)


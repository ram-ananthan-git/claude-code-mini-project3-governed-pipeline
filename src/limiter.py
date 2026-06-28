import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

# REQ-SHORT-015, NFR-RL-001: 60 requests per 60-second sliding window
_LIMIT: int = 60
_WINDOW_SECONDS: int = 60


@dataclass
class _Bucket:
    request_count: int = 0
    window_start: float = field(default_factory=time.time)


# NFR-RL-003: keyed by client IP string
_buckets: dict[str, _Bucket] = {}


def _get_client_ip(request: Request) -> str:
    """
    # NFR-RL-003: honour X-Forwarded-For when behind a trusted reverse proxy.
    Falls back to the direct connection address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def check_rate_limit(request: Request) -> None:
    """
    # REQ-SHORT-015: enforce per-IP sliding window of _LIMIT req / _WINDOW_SECONDS.
    Raises HTTP 429 with a Retry-After header when the limit is exceeded.
    # NFR-RL-001: in-process counter — no external service required.
    # NFR-RL-002: Retry-After header set to remaining seconds in window.
    """
    ip = _get_client_ip(request)
    now = time.time()

    bucket = _buckets.get(ip)
    if bucket is None:
        _buckets[ip] = _Bucket(request_count=1, window_start=now)
        return

    elapsed = now - bucket.window_start
    if elapsed >= _WINDOW_SECONDS:
        # Window expired — start a fresh one
        bucket.request_count = 1
        bucket.window_start = now
        return

    if bucket.request_count >= _LIMIT:
        # REQ-SHORT-015, NFR-RL-002: include Retry-After
        retry_after = int(_WINDOW_SECONDS - elapsed) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    bucket.request_count += 1


def clear() -> None:
    """Reset all buckets — test isolation only."""
    _buckets.clear()

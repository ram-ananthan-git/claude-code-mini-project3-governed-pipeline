import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, HttpUrl, field_validator

# REQ-SHORT-013, NFR-SEC-001: only these schemes are permitted
_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# REQ-SHORT-MALICIOUS: static blocklist — extend from a threat-feed in production
_BLOCKED_DOMAINS: frozenset[str] = frozenset(
    {
        "malware.example",
        "phishing.example",
        "spam.example",
        "evil-redirect.example",
    }
)

# NFR-SEC: block private / loopback hostnames to prevent SSRF
_PRIVATE_HOST_RE = re.compile(
    r"^("
    r"localhost"
    r"|127(?:\.\d{1,3}){3}"
    r"|10(?:\.\d{1,3}){3}"
    r"|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
    r"|192\.168(?:\.\d{1,3}){2}"
    r"|0\.0\.0\.0"
    r"|::1"
    r"|0:0:0:0:0:0:0:1"
    r")$",
    re.IGNORECASE,
)


class ShortenRequest(BaseModel):
    # REQ-SHORT-001: accepts a single "url" field
    url: str
    # REQ-SHORT-EXPIRY: optional link expiration timestamp
    expires_at: Optional[datetime] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()

        # REQ-SHORT-014: reject URLs longer than 2048 characters
        if len(v) > 2048:
            raise ValueError("URL must not exceed 2048 characters")

        # REQ-SHORT-013, NFR-SEC-001: scheme allowlist check before any parse
        parsed = urlparse(v)
        if parsed.scheme not in _ALLOWED_SCHEMES:
            got = parsed.scheme or "(none)"
            raise ValueError(
                f"URL must use http or https scheme, got '{got}'"
            )

        # REQ-SHORT-012, NFR-VAL-002: structural URI validity via Pydantic
        try:
            HttpUrl(v)
        except Exception:
            raise ValueError("Invalid URL format")

        # REQ-SHORT-MALICIOUS: domain blocklist — static deny-list
        hostname = (parsed.hostname or "").lower()
        if hostname in _BLOCKED_DOMAINS:
            raise ValueError("URL domain is blocked")

        # NFR-SEC: SSRF prevention — reject private / loopback addresses
        if _PRIVATE_HOST_RE.match(hostname):
            raise ValueError(
                "URL must not point to a private or loopback address"
            )

        # NFR-SEC: reject null bytes and ASCII control characters
        if any(ord(c) < 0x20 for c in v):
            raise ValueError("URL contains invalid control characters")

        return v

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        # REQ-SHORT-EXPIRY: expiration must be strictly in the future
        if v is not None:
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v <= datetime.now(timezone.utc):
                raise ValueError("expires_at must be a future datetime")
        return v


class LinkRecord(BaseModel):
    # REQ-SHORT-001, REQ-SHORT-002
    short_code: str
    original_url: str
    short_url: str
    # REQ-SHORT-006: click counter, starts at zero
    clicks: int = 0
    # REQ-SHORT-TIMESTAMPS: creation and last-access instants
    created_at: datetime
    last_accessed_at: Optional[datetime] = None
    # REQ-SHORT-EXPIRY: optional expiry, None means never expires
    expires_at: Optional[datetime] = None


class AnalyticsResponse(BaseModel):
    # REQ-SHORT-ANALYTICS: full per-link statistics
    short_code: str
    original_url: str
    short_url: str
    clicks: int
    created_at: datetime
    last_accessed_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_expired: bool
    # REQ-SHORT-REFERRER: referrer → hit count, top 10
    top_referrers: dict[str, int]


class HealthResponse(BaseModel):
    # REQ-SHORT-011
    status: str = "ok"

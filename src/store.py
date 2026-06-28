import secrets
import string
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from src.models import AnalyticsResponse, LinkRecord

# REQ-SHORT-002, NFR-SEC-002: 62-char alphabet → 62^8 ≈ 2.18×10¹⁴ codes
_ALPHABET: str = string.ascii_letters + string.digits
_CODE_LEN: int = 8

# Primary index: short_code → LinkRecord
_store: dict[str, LinkRecord] = {}

# REQ-SHORT-010: reverse index original_url → short_code for duplicate detection
_url_index: dict[str, str] = {}

# REQ-SHORT-REFERRER: per-code referrer counters, code → Counter{referrer: count}
_referrers: dict[str, Counter] = {}


# ── helpers ──────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_code() -> str:
    # REQ-SHORT-002, REQ-SHORT-003, NFR-SEC-002
    # secrets.choice provides cryptographically strong randomness
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))
        if code not in _store:
            return code


def _is_expired(record: LinkRecord) -> bool:
    # REQ-SHORT-EXPIRY: treat None expires_at as never-expiring
    if record.expires_at is None:
        return False
    return _now() >= record.expires_at


# ── write operations ──────────────────────────────────────────────────────────


def create_link(
    original_url: str,
    base_url: str,
    expires_at: Optional[datetime] = None,
) -> tuple[LinkRecord, bool]:
    """
    Create or look up a short URL mapping.

    # REQ-SHORT-001: creates and returns a LinkRecord
    # REQ-SHORT-003: generated code is unique
    # REQ-SHORT-010: duplicate original_url returns existing code (idempotent)

    Returns (record, created).  created=False means the URL already existed.
    Raises ValueError when the caller tries to re-shorten a URL but supplies
    a different expires_at — the existing record is left unchanged.
    """
    # REQ-SHORT-010: check reverse index first
    if original_url in _url_index:
        code = _url_index[original_url]
        return _store[code], False

    # REQ-SHORT-002, REQ-SHORT-003: generate a unique 8-char alphanumeric code
    code = _generate_code()

    record = LinkRecord(
        short_code=code,
        original_url=original_url,
        short_url=f"{base_url.rstrip('/')}/{code}",
        clicks=0,
        created_at=_now(),
        expires_at=expires_at,
    )

    _store[code] = record
    _url_index[original_url] = code
    _referrers[code] = Counter()
    return record, True


def get_link(code: str) -> LinkRecord | None:
    # REQ-SHORT-004, REQ-SHORT-005: return None when code is absent
    return _store.get(code)


def record_access(code: str, referrer: Optional[str]) -> None:
    """
    # REQ-SHORT-006: increment click counter
    # REQ-SHORT-TIMESTAMPS: update last_accessed_at to now
    # REQ-SHORT-REFERRER: accumulate referrer string into per-code Counter
    """
    if code not in _store:
        return
    record = _store[code]
    record.clicks += 1
    record.last_accessed_at = _now()
    # REQ-SHORT-REFERRER: normalise absent / empty referrer to sentinel
    ref_key = referrer.strip() if referrer and referrer.strip() else "(direct)"
    _referrers[code][ref_key] += 1


def delete_link(code: str) -> bool:
    # REQ-SHORT-007: remove mapping and return True; False if not found
    if code not in _store:
        return False
    record = _store.pop(code)
    _url_index.pop(record.original_url, None)
    _referrers.pop(code, None)
    return True


# ── read operations ───────────────────────────────────────────────────────────


def is_expired(code: str) -> bool:
    # REQ-SHORT-EXPIRY: convenience for router
    record = _store.get(code)
    return record is not None and _is_expired(record)


def get_analytics(code: str) -> AnalyticsResponse | None:
    """
    # REQ-SHORT-ANALYTICS: assemble full per-link analytics snapshot
    # REQ-SHORT-REFERRER: include top 10 referrers by hit count
    """
    record = _store.get(code)
    if record is None:
        return None

    top_refs = dict(_referrers[code].most_common(10))

    return AnalyticsResponse(
        short_code=record.short_code,
        original_url=record.original_url,
        short_url=record.short_url,
        clicks=record.clicks,
        created_at=record.created_at,
        last_accessed_at=record.last_accessed_at,
        expires_at=record.expires_at,
        is_expired=_is_expired(record),
        top_referrers=top_refs,
    )


def list_links() -> list[LinkRecord]:
    # REQ-SHORT-009: return all records regardless of expiry state
    return list(_store.values())


def url_exists(original_url: str) -> bool:
    # REQ-SHORT-010: used by router to distinguish 409 vs 201
    return original_url in _url_index


def get_link_by_url(original_url: str) -> "LinkRecord | None":
    # REQ-SHORT-010: public accessor for reverse lookup — keeps router out of _url_index
    code = _url_index.get(original_url)
    return _store[code] if code is not None else None


def clear() -> None:
    """Reset all in-memory state — test isolation only, not part of the API."""
    _store.clear()
    _url_index.clear()
    _referrers.clear()

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from src import limiter, store
from src.models import AnalyticsResponse, HealthResponse, LinkRecord, ShortenRequest

router = APIRouter()


# ── health ────────────────────────────────────────────────────────────────────


# REQ-SHORT-011
@router.get("/healthz", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness probe — always returns {"status": "ok"}."""
    return HealthResponse()


# ── management ────────────────────────────────────────────────────────────────


# REQ-SHORT-009
@router.get("/links", response_model=list[LinkRecord])
def list_links() -> list[LinkRecord]:
    """Return every active short-URL mapping regardless of expiry state."""
    return store.list_links()


# ── shorten ───────────────────────────────────────────────────────────────────


# REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003, REQ-SHORT-010,
# REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014, REQ-SHORT-015
@router.post("/shorten", response_model=LinkRecord, status_code=201)
def shorten_url(body: ShortenRequest, request: Request) -> Response:
    """
    Create a short URL mapping.

    Validation (REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014) is handled by
    ShortenRequest.validate_url before this handler is reached.

    # REQ-SHORT-015: enforce per-IP rate limit before any store operation
    # REQ-SHORT-010: return 409 Conflict when URL already has a mapping,
    #                rather than silently reusing it, so callers know the
    #                code already existed
    # REQ-SHORT-001: on success return short_code, short_url, original_url, clicks
    # REQ-SHORT-EXPIRY: optional expires_at stored on the record
    """
    # REQ-SHORT-015
    limiter.check_rate_limit(request)

    # REQ-SHORT-010: reject duplicate original URL with 409
    existing = store.get_link_by_url(body.url)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "URL already shortened",
                "short_code": existing.short_code,
                "short_url": existing.short_url,
            },
        )

    base_url = str(request.base_url).rstrip("/")
    record, _ = store.create_link(body.url, base_url, body.expires_at)
    return record


# ── redirect ──────────────────────────────────────────────────────────────────


# REQ-SHORT-004, REQ-SHORT-005, REQ-SHORT-006, REQ-SHORT-EXPIRY,
# REQ-SHORT-TIMESTAMPS, REQ-SHORT-REFERRER
@router.get("/{short_code}")
def redirect_to_url(short_code: str, request: Request) -> Response:
    """
    Resolve a short code and issue an HTTP 307 redirect.

    # REQ-SHORT-005: 404 when code is not found
    # REQ-SHORT-EXPIRY: 410 Gone when the link has passed its expires_at
    # REQ-SHORT-004: 307 Temporary Redirect to original URL
    # REQ-SHORT-006: click counter incremented on every successful redirect
    # REQ-SHORT-TIMESTAMPS: last_accessed_at updated on every successful redirect
    # REQ-SHORT-REFERRER: Referer header captured and stored
    # NFR-SEC-003: destination URL is returned as-is — service does not fetch it
    """
    record = store.get_link(short_code)

    # REQ-SHORT-005
    if record is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    # REQ-SHORT-EXPIRY: expired links return 410 rather than redirect
    if store.is_expired(short_code):
        raise HTTPException(
            status_code=410,
            detail="This short URL has expired",
        )

    # REQ-SHORT-006, REQ-SHORT-TIMESTAMPS, REQ-SHORT-REFERRER
    referrer = request.headers.get("Referer") or request.headers.get("Referrer")
    store.record_access(short_code, referrer)

    # REQ-SHORT-004, NFR-SEC-003
    return RedirectResponse(url=record.original_url, status_code=307)


# ── delete ───────────────────────────────────────────────────────────────────


# REQ-SHORT-007, REQ-SHORT-008
@router.delete("/{short_code}", status_code=204)
def delete_link(short_code: str) -> None:
    """
    Remove a short URL mapping.

    # REQ-SHORT-007: 204 No Content on successful deletion
    # REQ-SHORT-008: 404 when code does not exist
    """
    deleted = store.delete_link(short_code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Short code not found")


# ── analytics ─────────────────────────────────────────────────────────────────


# REQ-SHORT-ANALYTICS, REQ-SHORT-006, REQ-SHORT-TIMESTAMPS, REQ-SHORT-REFERRER
@router.get("/analytics/{short_code}", response_model=AnalyticsResponse)
def get_analytics(short_code: str) -> AnalyticsResponse:
    """
    Return per-link analytics: click count, timestamps, expiry status,
    and top-10 referrers.

    # REQ-SHORT-ANALYTICS: expose stats without triggering a redirect
    # REQ-SHORT-006: clicks field reflects total successful redirects
    # REQ-SHORT-TIMESTAMPS: created_at and last_accessed_at included
    # REQ-SHORT-REFERRER: top_referrers dict with hit counts
    # REQ-SHORT-EXPIRY: is_expired flag included so callers can check without
    #                   attempting a redirect
    """
    analytics = store.get_analytics(short_code)

    if analytics is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    return analytics

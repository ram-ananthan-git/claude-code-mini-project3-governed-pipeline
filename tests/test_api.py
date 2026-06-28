"""
Integration tests for the URL Shortener Service.
One test function per Gherkin scenario; extra tests for new features.
All interaction is through the HTTP layer — no direct store access except
in the autouse fixture for test isolation.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src import store
from src.main import app

# reset_state fixture is provided by tests/conftest.py (autouse, function scope)

client = TestClient(app, raise_server_exceptions=True)


# ─────────────────────────────────────────────────────────────
# SCN-001 | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003
# ─────────────────────────────────────────────────────────────

def test_scn001_shorten_valid_url():
    resp = client.post("/shorten", json={"url": "https://example.com/some/long/path"})
    assert resp.status_code == 201
    body = resp.json()

    # REQ-SHORT-002: exactly 8 alphanumeric characters
    assert re.fullmatch(r"[a-zA-Z0-9]{8}", body["short_code"])
    assert len(body["short_code"]) == 8

    # REQ-SHORT-001: required fields present
    assert body["short_code"] in body["short_url"]
    assert body["original_url"] == "https://example.com/some/long/path"
    assert body["clicks"] == 0

    # REQ-SHORT-TIMESTAMPS: created_at present and parseable
    assert body["created_at"] is not None
    datetime.fromisoformat(body["created_at"])


# ─────────────────────────────────────────────────────────────
# SCN-002 | REQ-SHORT-004, REQ-SHORT-006, REQ-SHORT-TIMESTAMPS, REQ-SHORT-REFERRER
# ─────────────────────────────────────────────────────────────

def test_scn002_redirect_increments_clicks_and_records_access():
    create = client.post("/shorten", json={"url": "https://example.com"})
    code = create.json()["short_code"]

    # REQ-SHORT-004: 307 with correct Location header
    resp = client.get(f"/{code}", follow_redirects=False,
                      headers={"Referer": "https://referrer.example.com"})
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com"

    # REQ-SHORT-006: click count incremented
    links = client.get("/links").json()
    record = next(r for r in links if r["short_code"] == code)
    assert record["clicks"] == 1

    # REQ-SHORT-TIMESTAMPS: last_accessed_at is now set
    assert record["last_accessed_at"] is not None


# ─────────────────────────────────────────────────────────────
# SCN-003 | REQ-SHORT-005
# ─────────────────────────────────────────────────────────────

def test_scn003_resolve_unknown_code_returns_404():
    resp = client.get("/xxxxxxxx", follow_redirects=False)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Short code not found"


# ─────────────────────────────────────────────────────────────
# SCN-004 | REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_url", [
    "not-a-url",
    "ftp://example.com",
    "javascript:alert(1)",
    "data:text/html,hello",
    "",
    "http://",
    "file:///etc/passwd",
])
def test_scn004_invalid_url_returns_422(bad_url):
    # REQ-SHORT-012, REQ-SHORT-013: scheme allowlist + structural check
    resp = client.post("/shorten", json={"url": bad_url})
    assert resp.status_code == 422


def test_scn004_url_too_long_returns_422():
    # REQ-SHORT-014: max 2048 chars
    long_url = "https://example.com/" + "a" * 2029
    assert len(long_url) > 2048
    resp = client.post("/shorten", json={"url": long_url})
    assert resp.status_code == 422
    detail_str = str(resp.json())
    assert "2048" in detail_str


# ─────────────────────────────────────────────────────────────
# SCN-005 | REQ-SHORT-007
# ─────────────────────────────────────────────────────────────

def test_scn005_delete_existing_code():
    create = client.post("/shorten", json={"url": "https://delete-me.com"})
    code = create.json()["short_code"]

    resp = client.delete(f"/{code}")
    assert resp.status_code == 204

    # subsequent GET must 404
    follow = client.get(f"/{code}", follow_redirects=False)
    assert follow.status_code == 404


# ─────────────────────────────────────────────────────────────
# SCN-006 | REQ-SHORT-008
# ─────────────────────────────────────────────────────────────

def test_scn006_delete_nonexistent_code_returns_404():
    resp = client.delete("/missing1x")
    assert resp.status_code == 404
    assert "detail" in resp.json()


# ─────────────────────────────────────────────────────────────
# SCN-007 | REQ-SHORT-009
# ─────────────────────────────────────────────────────────────

def test_scn007_list_all_links():
    client.post("/shorten", json={"url": "https://a.com"})
    client.post("/shorten", json={"url": "https://b.com"})

    resp = client.get("/links")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    for entry in body:
        assert "short_code" in entry
        assert "original_url" in entry
        assert "short_url" in entry
        assert "clicks" in entry
        assert "created_at" in entry


# ─────────────────────────────────────────────────────────────
# SCN-008 | REQ-SHORT-010 — duplicate → 409 Conflict
# ─────────────────────────────────────────────────────────────

def test_scn008_duplicate_url_returns_409():
    # REQ-SHORT-010: second POST with same URL returns 409 with existing code
    first = client.post("/shorten", json={"url": "https://example.com"})
    assert first.status_code == 201
    code = first.json()["short_code"]

    second = client.post("/shorten", json={"url": "https://example.com"})
    assert second.status_code == 409
    body = second.json()["detail"]
    assert body["short_code"] == code
    assert "already shortened" in body["message"]

    # only one entry in store
    links = client.get("/links").json()
    assert len(links) == 1


# ─────────────────────────────────────────────────────────────
# SCN-009 | REQ-SHORT-011
# ─────────────────────────────────────────────────────────────

def test_scn009_health_check():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ─────────────────────────────────────────────────────────────
# SCN-010 | REQ-SHORT-014
# ─────────────────────────────────────────────────────────────

def test_scn010_url_too_long_returns_422():
    url = "https://example.com/" + "x" * 2029
    resp = client.post("/shorten", json={"url": url})
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# SCN-011 | REQ-SHORT-015 — rate limiting
# ─────────────────────────────────────────────────────────────

def test_scn011_rate_limit_returns_429():
    # REQ-SHORT-015: 60 requests succeed, 61st is rejected
    for i in range(60):
        resp = client.post("/shorten", json={"url": f"https://example{i}.com"})
        assert resp.status_code == 201, f"Request {i+1} should succeed"

    resp = client.post("/shorten", json={"url": "https://overflow.com"})
    assert resp.status_code == 429
    # NFR-RL-002: Retry-After header present with positive integer
    assert "retry-after" in resp.headers
    assert int(resp.headers["retry-after"]) > 0
    assert "Rate limit exceeded" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────
# REQ-SHORT-EXPIRY — link expiration
# ─────────────────────────────────────────────────────────────

def test_expiry_future_date_accepted():
    # REQ-SHORT-EXPIRY: future expires_at is stored
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    resp = client.post("/shorten", json={"url": "https://expiring.com", "expires_at": future})
    assert resp.status_code == 201
    assert resp.json()["expires_at"] is not None


def test_expiry_past_date_rejected():
    # REQ-SHORT-EXPIRY: past expires_at is rejected at validation time
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = client.post("/shorten", json={"url": "https://expired.com", "expires_at": past})
    assert resp.status_code == 422


def test_expired_link_returns_410():
    # REQ-SHORT-EXPIRY: accessing an expired link returns 410 Gone
    future = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    create = client.post("/shorten", json={"url": "https://will-expire.com", "expires_at": future})
    code = create.json()["short_code"]

    # Manually expire the record by manipulating it through the store
    # (the only place we touch internal state — needed to avoid a real sleep)
    record = store.get_link(code)
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    resp = client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 410
    assert "expired" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────
# REQ-SHORT-ANALYTICS — analytics endpoint
# ─────────────────────────────────────────────────────────────

def test_analytics_returns_full_stats():
    # REQ-SHORT-ANALYTICS: all fields present and correct
    create = client.post("/shorten", json={"url": "https://analytics-test.com"})
    code = create.json()["short_code"]

    # Generate 3 clicks with different referrers
    client.get(f"/{code}", follow_redirects=False,
               headers={"Referer": "https://google.com"})
    client.get(f"/{code}", follow_redirects=False,
               headers={"Referer": "https://google.com"})
    client.get(f"/{code}", follow_redirects=False,
               headers={"Referer": "https://twitter.com"})

    resp = client.get(f"/analytics/{code}")
    assert resp.status_code == 200
    body = resp.json()

    # REQ-SHORT-006: click count
    assert body["clicks"] == 3
    # REQ-SHORT-TIMESTAMPS
    assert body["created_at"] is not None
    assert body["last_accessed_at"] is not None
    # REQ-SHORT-REFERRER: top referrers aggregated correctly
    assert body["top_referrers"]["https://google.com"] == 2
    assert body["top_referrers"]["https://twitter.com"] == 1
    # REQ-SHORT-EXPIRY: is_expired flag
    assert body["is_expired"] is False


def test_analytics_unknown_code_returns_404():
    resp = client.get("/analytics/xxxxxxxx")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Short code not found"


def test_analytics_does_not_increment_clicks():
    # REQ-SHORT-ANALYTICS: reading analytics must not affect the click counter
    create = client.post("/shorten", json={"url": "https://no-click.com"})
    code = create.json()["short_code"]

    for _ in range(3):
        client.get(f"/analytics/{code}")

    resp = client.get(f"/analytics/{code}")
    assert resp.json()["clicks"] == 0


# ─────────────────────────────────────────────────────────────
# REQ-SHORT-REFERRER — referrer tracking
# ─────────────────────────────────────────────────────────────

def test_referrer_direct_traffic_recorded():
    # REQ-SHORT-REFERRER: absent Referer header stored as "(direct)"
    create = client.post("/shorten", json={"url": "https://direct.com"})
    code = create.json()["short_code"]

    client.get(f"/{code}", follow_redirects=False)

    analytics = client.get(f"/analytics/{code}").json()
    assert analytics["top_referrers"].get("(direct)") == 1


def test_referrer_multiple_sources_aggregated():
    # REQ-SHORT-REFERRER: counts are summed per referrer string
    create = client.post("/shorten", json={"url": "https://multi-ref.com"})
    code = create.json()["short_code"]

    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False,
                   headers={"Referer": "https://source-a.com"})
    for _ in range(2):
        client.get(f"/{code}", follow_redirects=False,
                   headers={"Referer": "https://source-b.com"})

    analytics = client.get(f"/analytics/{code}").json()
    assert analytics["top_referrers"]["https://source-a.com"] == 3
    assert analytics["top_referrers"]["https://source-b.com"] == 2


# ─────────────────────────────────────────────────────────────
# REQ-SHORT-MALICIOUS — malicious URL rejection
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("blocked_url", [
    "http://malware.example/payload",
    "https://phishing.example/login",
    "http://spam.example",
])
def test_blocked_domain_returns_422(blocked_url):
    # REQ-SHORT-MALICIOUS: known-bad domains rejected before store write
    resp = client.post("/shorten", json={"url": blocked_url})
    assert resp.status_code == 422
    assert "blocked" in str(resp.json()).lower()


@pytest.mark.parametrize("private_url", [
    "http://localhost/admin",
    "http://127.0.0.1:8080/secret",
    "http://192.168.1.1/router",
    "http://10.0.0.1/internal",
])
def test_private_address_returns_422(private_url):
    # NFR-SEC: SSRF prevention — private/loopback addresses rejected
    resp = client.post("/shorten", json={"url": private_url})
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# REQ-SHORT-006 — click count accumulates correctly
# ─────────────────────────────────────────────────────────────

def test_click_count_accumulates():
    # REQ-SHORT-006: click counter reflects total successful redirects
    create = client.post("/shorten", json={"url": "https://counter.com"})
    code = create.json()["short_code"]

    for _ in range(5):
        client.get(f"/{code}", follow_redirects=False)

    links = client.get("/links").json()
    record = next(r for r in links if r["short_code"] == code)
    assert record["clicks"] == 5


# ─────────────────────────────────────────────────────────────
# Route-ordering guard — /analytics/{code} and /links must not
# be captured by /{short_code} wildcard
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# ISSUE-007-FIX | REQ-SHORT-ANALYTICS, REQ-SHORT-EXPIRY
# ─────────────────────────────────────────────────────────────

def test_analytics_expired_link_shows_is_expired_true():
    # REQ-SHORT-ANALYTICS: is_expired flag reflects live expiry state
    future = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    create = client.post("/shorten", json={"url": "https://will-expire-analytics.com", "expires_at": future})
    code = create.json()["short_code"]

    record = store.get_link(code)
    assert record is not None
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    resp = client.get(f"/analytics/{code}")
    assert resp.status_code == 200
    assert resp.json()["is_expired"] is True


# ─────────────────────────────────────────────────────────────
# ISSUE-011-FIX | REQ-SHORT-ANALYTICS, REQ-SHORT-007
# ─────────────────────────────────────────────────────────────

def test_analytics_after_delete_returns_404():
    # REQ-SHORT-ANALYTICS: deleted link must return 404 from analytics endpoint
    create = client.post("/shorten", json={"url": "https://delete-then-analytics.com"})
    code = create.json()["short_code"]

    client.delete(f"/{code}")

    resp = client.get(f"/analytics/{code}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Short code not found"


# ─────────────────────────────────────────────────────────────
# Route-ordering guard — /analytics/{code} and /links must not
# be captured by /{short_code} wildcard
# ─────────────────────────────────────────────────────────────

def test_links_route_not_captured_by_wildcard():
    resp = client.get("/links")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_healthz_route_not_captured_by_wildcard():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

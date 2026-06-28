"""
Generated from : prompts/test-generator.yaml
Service        : URL Shortener Service
Spec           : specs/url-shortener.yaml  (SVC-URL-SHORTENER v1.0.0)
App import     : from src.main import app
Store reset    : from src import store, limiter  (via tests/conftest.py)
Base URL       : http://testserver

Template variables applied
--------------------------
output_file            : tests/test_scenarios.py
service_name           : URL Shortener Service
app_import             : from src.main import app
store_reset_import     : from src import store, limiter
base_url               : http://testserver
extra_test_behaviour   : click count accumulates correctly across multiple
                         redirects (template default)

Output schema manifest
----------------------
imports:
  - import re
  - import pytest
  - from datetime import datetime, timedelta, timezone
  - from fastapi.testclient import TestClient
  - from src.main import app
  - from src import store

fixtures:
  - name: reset_state
    scope: function
    autouse: true
    defined_in: tests/conftest.py

test_functions:
  - {name: test_scn001_shorten_valid_url,              scenario_id: SCN-001, parametrized: false}
  - {name: test_scn002_redirect_to_original_url,       scenario_id: SCN-002, parametrized: false}
  - {name: test_scn003_unknown_code_returns_404,        scenario_id: SCN-003, parametrized: false}
  - {name: test_scn004_invalid_url_returns_422,         scenario_id: SCN-004, parametrized: true}
  - {name: test_scn005_delete_existing_code,            scenario_id: SCN-005, parametrized: false}
  - {name: test_scn006_delete_nonexistent_returns_404,  scenario_id: SCN-006, parametrized: false}
  - {name: test_scn007_list_all_links,                  scenario_id: SCN-007, parametrized: false}
  - {name: test_scn008_duplicate_url_returns_409,       scenario_id: SCN-008, parametrized: false}
  - {name: test_scn009_health_check,                    scenario_id: SCN-009, parametrized: false}
  - {name: test_scn010_url_too_long_returns_422,        scenario_id: SCN-010, parametrized: false}
  - {name: test_scn011_rate_limit_returns_429,          scenario_id: SCN-011, parametrized: false}
  - {name: test_extra_click_count_accumulates,          scenario_id: EXTRA,   parametrized: false}
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app, raise_server_exceptions=True)


# ─────────────────────────────────────────────────────────────────────────────
# SCN-001 | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003
#
# Given the service has no existing mappings
# When I POST /shorten with body {"url": "https://example.com/some/very/long/path?q=1"}
# Then the response status is 201
# And the response body contains "short_code" of exactly 8 alphanumeric characters
# And the response body "short_url" contains the short_code as a path segment
# And the response body "original_url" equals the submitted URL
# And the response body "clicks" equals 0
# ─────────────────────────────────────────────────────────────────────────────

def test_scn001_shorten_valid_url():
    # SCN-001 | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003
    resp = client.post(
        "/shorten",
        json={"url": "https://example.com/some/very/long/path?q=1"},
    )

    assert resp.status_code == 201

    body = resp.json()
    # REQ-SHORT-002: exactly 8 URL-safe alphanumeric characters
    assert re.fullmatch(r"[a-zA-Z0-9]{8}", body["short_code"]), (
        f"short_code {body['short_code']!r} is not 8 alphanumeric chars"
    )

    # REQ-SHORT-001: mandatory response fields
    assert body["short_code"] in body["short_url"]
    assert body["original_url"] == "https://example.com/some/very/long/path?q=1"
    assert body["clicks"] == 0

    # REQ-SHORT-001: short_url must be a valid URI containing the code
    assert body["short_url"].startswith("http")

    # REQ-SHORT-003: code is unique — a second different URL gets a different code
    resp2 = client.post("/shorten", json={"url": "https://other.example.com"})
    assert resp2.json()["short_code"] != body["short_code"]


# ─────────────────────────────────────────────────────────────────────────────
# SCN-002 | REQ-SHORT-004, REQ-SHORT-006
#
# Given a mapping exists for code "abc12345" pointing to "https://example.com"
# When I GET /abc12345 without following redirects
# Then the response status is 307
# And the Location header equals "https://example.com"
# And a subsequent GET /links shows "clicks" is 1 for that code
# ─────────────────────────────────────────────────────────────────────────────

def test_scn002_redirect_to_original_url():
    # SCN-002 | REQ-SHORT-004, REQ-SHORT-006
    create = client.post("/shorten", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["short_code"]

    # REQ-SHORT-004: 307 Temporary Redirect — do NOT follow automatically
    resp = client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com"

    # REQ-SHORT-006: click counter incremented after redirect
    links = {r["short_code"]: r for r in client.get("/links").json()}
    assert links[code]["clicks"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# SCN-003 | REQ-SHORT-005
#
# Given the service store contains no mapping for code "xxxxxxxx"
# When I GET /xxxxxxxx
# Then the response status is 404
# And the response body equals {"detail": "Short code not found"}
# ─────────────────────────────────────────────────────────────────────────────

def test_scn003_unknown_code_returns_404():
    # SCN-003 | REQ-SHORT-005
    resp = client.get("/xxxxxxxx", follow_redirects=False)

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Short code not found"}


# ─────────────────────────────────────────────────────────────────────────────
# SCN-004 | REQ-SHORT-012, REQ-SHORT-013
#
# Given the service is running
# When I POST /shorten with each of the following urls:
#   | not-a-url | ftp://files.example.com | javascript:alert(1) |
#   | data:text/html,hello | http:// | (empty string) |
# Then every response status is 422
# And every response body contains a "detail" field describing the error
#
# Rule 3: parametrize when a scenario lists multiple example rows
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "bad_url, expected_fragment",
    [
        # plain string — no scheme at all
        ("not-a-url",            "http or https"),
        # disallowed scheme — ftp
        ("ftp://files.example.com", "http or https"),
        # disallowed scheme — javascript (XSS vector)
        ("javascript:alert(1)",  "http or https"),
        # disallowed scheme — data URI
        ("data:text/html,hello", "http or https"),
        # empty string — no scheme
        ("",                     "http or https"),
        # http scheme present but structurally invalid
        ("http://",              "Invalid URL"),
        # disallowed scheme — file (local path traversal)
        ("file:///etc/passwd",   "http or https"),
    ],
)
def test_scn004_invalid_url_returns_422(bad_url, expected_fragment):
    # SCN-004 | REQ-SHORT-012, REQ-SHORT-013
    resp = client.post("/shorten", json={"url": bad_url})

    assert resp.status_code == 422, (
        f"Expected 422 for {bad_url!r}, got {resp.status_code}"
    )
    # REQ-SHORT-012, REQ-SHORT-013: detail describes which validation failed
    detail_text = str(resp.json())
    assert expected_fragment.lower() in detail_text.lower(), (
        f"Expected fragment {expected_fragment!r} not found in: {detail_text}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCN-005 | REQ-SHORT-007
#
# Given a mapping exists for code "del12345" pointing to "https://delete-me.com"
# When I DELETE /del12345
# Then the response status is 204
# And a subsequent GET /del12345 returns status 404
# ─────────────────────────────────────────────────────────────────────────────

def test_scn005_delete_existing_code():
    # SCN-005 | REQ-SHORT-007
    create = client.post("/shorten", json={"url": "https://delete-me.com"})
    assert create.status_code == 201
    code = create.json()["short_code"]

    # REQ-SHORT-007: 204 No Content on successful deletion
    resp = client.delete(f"/{code}")
    assert resp.status_code == 204
    assert resp.content == b""  # no body on 204

    # Verify the mapping is gone
    follow = client.get(f"/{code}", follow_redirects=False)
    assert follow.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# SCN-006 | REQ-SHORT-008
#
# Given no mapping exists for code "missing1"
# When I DELETE /missing1
# Then the response status is 404
# And the response body contains {"detail": "Short code not found"}
# ─────────────────────────────────────────────────────────────────────────────

def test_scn006_delete_nonexistent_returns_404():
    # SCN-006 | REQ-SHORT-008
    resp = client.delete("/missing1x")  # 8-char code that was never created

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Short code not found"}


# ─────────────────────────────────────────────────────────────────────────────
# SCN-007 | REQ-SHORT-009
#
# Given mappings exist for "https://a.com" and "https://b.com"
# When I GET /links
# Then the response status is 200
# And the response body is a JSON array with exactly 2 entries
# And each entry contains short_code, original_url, short_url, and clicks
# ─────────────────────────────────────────────────────────────────────────────

def test_scn007_list_all_links():
    # SCN-007 | REQ-SHORT-009
    client.post("/shorten", json={"url": "https://a.com"})
    client.post("/shorten", json={"url": "https://b.com"})

    resp = client.get("/links")
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2

    required_fields = {"short_code", "original_url", "short_url", "clicks"}
    for entry in body:
        missing = required_fields - entry.keys()
        assert not missing, f"Entry missing fields: {missing}"
        assert re.fullmatch(r"[a-zA-Z0-9]{8}", entry["short_code"])
        assert entry["clicks"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# SCN-008 | REQ-SHORT-010
#
# Given a mapping already exists for "https://example.com" with code "exist123"
# When I POST /shorten with body {"url": "https://example.com"}
# Then the response status is 409
# And the response body detail contains the existing short_code
# And GET /links returns exactly 1 entry
# ─────────────────────────────────────────────────────────────────────────────

def test_scn008_duplicate_url_returns_409():
    # SCN-008 | REQ-SHORT-010
    first = client.post("/shorten", json={"url": "https://example.com"})
    assert first.status_code == 201
    original_code = first.json()["short_code"]

    # REQ-SHORT-010: duplicate → 409 Conflict, body carries existing code
    second = client.post("/shorten", json={"url": "https://example.com"})
    assert second.status_code == 409

    detail = second.json()["detail"]
    assert detail["short_code"] == original_code
    assert "already shortened" in detail["message"].lower()

    # No new entry must have been created
    links = client.get("/links").json()
    assert len(links) == 1


# ─────────────────────────────────────────────────────────────────────────────
# SCN-009 | REQ-SHORT-011
#
# Given the service is running
# When I GET /healthz
# Then the response status is 200
# And the response body equals {"status": "ok"}
# ─────────────────────────────────────────────────────────────────────────────

def test_scn009_health_check():
    # SCN-009 | REQ-SHORT-011
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# SCN-010 | REQ-SHORT-014
#
# Given the service is running
# When I POST /shorten with a "url" field that is 2049 characters long
# Then the response status is 422
# And the response body contains a detail mentioning URL length
# ─────────────────────────────────────────────────────────────────────────────

def test_scn010_url_too_long_returns_422():
    # SCN-010 | REQ-SHORT-014
    # 20 chars of valid prefix + 2029 padding = 2049 chars total
    url = "https://example.com/" + "x" * 2029
    assert len(url) == 2049

    resp = client.post("/shorten", json={"url": url})

    assert resp.status_code == 422
    detail_text = str(resp.json())
    assert "2048" in detail_text, (
        f"Expected '2048' in validation error, got: {detail_text}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCN-011 | REQ-SHORT-015
#
# Given a single IP address sends 60 POST /shorten requests within 60 seconds
# When that IP sends a 61st POST /shorten request
# Then the response status is 429
# And the response headers contain "Retry-After" with a positive integer value
# ─────────────────────────────────────────────────────────────────────────────

def test_scn011_rate_limit_returns_429():
    # SCN-011 | REQ-SHORT-015
    # Exhaust the window — 60 requests, each to a distinct URL
    for i in range(60):
        resp = client.post("/shorten", json={"url": f"https://burst-{i:04d}.example.com"})
        assert resp.status_code == 201, (
            f"Request {i + 1}/60 should succeed, got {resp.status_code}"
        )

    # 61st request from the same IP must be rate-limited
    resp = client.post("/shorten", json={"url": "https://overflow.example.com"})

    assert resp.status_code == 429

    # NFR-RL-002: Retry-After header must be a positive integer
    assert "retry-after" in resp.headers, "Retry-After header missing from 429 response"
    retry_after = int(resp.headers["retry-after"])
    assert retry_after > 0, f"Retry-After must be positive, got {retry_after}"

    # Descriptive error message in body
    assert "Rate limit exceeded" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# EXTRA | REQ-SHORT-006
# Template variable: extra_test_behaviour =
#   "click count accumulates correctly across multiple redirects"
#
# Verifies that clicking a link N times yields clicks == N, and that
# each individual redirect still returns the correct 307 + Location.
# ─────────────────────────────────────────────────────────────────────────────

def test_extra_click_count_accumulates():
    # EXTRA | REQ-SHORT-006
    create = client.post("/shorten", json={"url": "https://click-counter.example.com"})
    assert create.status_code == 201
    code = create.json()["short_code"]

    n = 7
    for i in range(n):
        resp = client.get(f"/{code}", follow_redirects=False)
        # Every redirect still returns 307 with the correct destination
        assert resp.status_code == 307, f"Redirect {i + 1} expected 307"
        assert resp.headers["location"] == "https://click-counter.example.com"

    # REQ-SHORT-006: final click count must equal n
    links = {r["short_code"]: r for r in client.get("/links").json()}
    assert links[code]["clicks"] == n, (
        f"Expected {n} clicks, got {links[code]['clicks']}"
    )

# Traceability Matrix — URL Shortener Service

**Spec:** `specs/url-shortener.yaml` (SVC-URL-SHORTENER v1.0.0)  
**Last test run:** 54 passed, 0 failed  
**Generated from live source:** `src/` + `tests/` as of 2026-06-27

---

## How to read this document

Each row maps a single requirement to:

| Column | Meaning |
|---|---|
| **REQ-ID** | Unique requirement identifier from the spec |
| **Priority** | MUST / SHOULD / MAY (from spec) |
| **Implementing symbol(s)** | `file.py : function_or_class` where the REQ-ID comment appears |
| **Test cases** | Every test function (and its file) that exercises this requirement |
| **Status** | ✅ PASS — all linked tests passed on last run |

A row with no test case is marked ⚠️ NO TEST. A row where a test failed is marked ❌ FAIL.

---

## Section 1 — Functional Requirements

### 1.1 Core URL Shortening

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-001** | MUST | POST /shorten accepts `url`, returns `short_code`, `short_url`, `original_url`, `clicks` | `models.py : ShortenRequest` (url field)<br>`models.py : LinkRecord` (response shape)<br>`router.py : shorten_url`<br>`store.py : create_link` | `test_api.py :: test_scn001_shorten_valid_url`<br>`test_scenarios.py :: test_scn001_shorten_valid_url` | ✅ PASS |
| **REQ-SHORT-002** | MUST | Short codes are exactly 8 URL-safe alphanumeric characters (a–z, A–Z, 0–9) | `store.py : _ALPHABET`<br>`store.py : _CODE_LEN`<br>`store.py : _generate_code`<br>`models.py : LinkRecord.short_code` | `test_api.py :: test_scn001_shorten_valid_url`<br>`test_scenarios.py :: test_scn001_shorten_valid_url`<br>`test_scenarios.py :: test_scn007_list_all_links` | ✅ PASS |
| **REQ-SHORT-003** | MUST | Short codes are unique; generation retries on collision | `store.py : _generate_code` (while-True dedup loop)<br>`store.py : create_link` | `test_scenarios.py :: test_scn001_shorten_valid_url` (asserts two URLs get different codes) | ✅ PASS |

### 1.2 Resolution / Redirect

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-004** | MUST | GET /{code} responds 307 Temporary Redirect; Location = original URL | `router.py : redirect_to_url`<br>`store.py : get_link` | `test_api.py :: test_scn002_redirect_increments_clicks_and_records_access`<br>`test_scenarios.py :: test_scn002_redirect_to_original_url`<br>`test_scenarios.py :: test_extra_click_count_accumulates` | ✅ PASS |
| **REQ-SHORT-005** | MUST | GET /{code} with unknown code → 404 `{"detail": "Short code not found"}` | `router.py : redirect_to_url` (HTTPException 404)<br>`store.py : get_link` (returns None) | `test_api.py :: test_scn003_resolve_unknown_code_returns_404`<br>`test_scenarios.py :: test_scn003_unknown_code_returns_404`<br>`test_api.py :: test_scn005_delete_existing_code` (follow-up 404) | ✅ PASS |

### 1.3 Click Analytics

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-006** | MUST | Click counter incremented on every successful redirect; returned in `clicks` field | `store.py : record_access` (clicks += 1)<br>`router.py : redirect_to_url` (calls record_access)<br>`models.py : LinkRecord.clicks` | `test_api.py :: test_scn002_redirect_increments_clicks_and_records_access`<br>`test_scenarios.py :: test_scn002_redirect_to_original_url`<br>`test_api.py :: test_click_count_accumulates`<br>`test_scenarios.py :: test_extra_click_count_accumulates`<br>`test_api.py :: test_analytics_returns_full_stats` | ✅ PASS |

### 1.4 Link Management

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-007** | MUST | DELETE /{code} removes mapping → 204 No Content | `router.py : delete_link`<br>`store.py : delete_link` (pops from `_store` + `_url_index` + `_referrers`) | `test_api.py :: test_scn005_delete_existing_code`<br>`test_scenarios.py :: test_scn005_delete_existing_code` | ✅ PASS |
| **REQ-SHORT-008** | MUST | DELETE /{code} with unknown code → 404 | `router.py : delete_link` (HTTPException 404)<br>`store.py : delete_link` (returns False) | `test_api.py :: test_scn006_delete_nonexistent_code_returns_404`<br>`test_scenarios.py :: test_scn006_delete_nonexistent_returns_404` | ✅ PASS |
| **REQ-SHORT-009** | MUST | GET /links → 200, JSON array with all active mappings; each entry has `short_code`, `original_url`, `short_url`, `clicks` | `router.py : list_links`<br>`store.py : list_links`<br>`test_api.py :: test_links_route_not_captured_by_wildcard` | `test_api.py :: test_scn007_list_all_links`<br>`test_scenarios.py :: test_scn007_list_all_links`<br>`test_api.py :: test_links_route_not_captured_by_wildcard` | ✅ PASS |

### 1.5 Duplicate Handling

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-010** | SHOULD | Duplicate URL on POST /shorten → 409 Conflict; body contains existing `short_code` | `router.py : shorten_url` (HTTPException 409)<br>`store.py : url_exists`<br>`store.py : _url_index` (reverse lookup) | `test_api.py :: test_scn008_duplicate_url_returns_409`<br>`test_scenarios.py :: test_scn008_duplicate_url_returns_409` | ✅ PASS |

### 1.6 Health Probe

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-011** | MUST | GET /healthz → 200 `{"status": "ok"}` | `router.py : health_check`<br>`models.py : HealthResponse` | `test_api.py :: test_scn009_health_check`<br>`test_scenarios.py :: test_scn009_health_check`<br>`test_api.py :: test_healthz_route_not_captured_by_wildcard` | ✅ PASS |

### 1.7 Input Validation

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-012** | MUST | POST /shorten with structurally invalid URI → 422 | `models.py : ShortenRequest.validate_url` (Pydantic `HttpUrl` parse) | `test_api.py :: test_scn004_invalid_url_returns_422[http://]`<br>`test_scenarios.py :: test_scn004_invalid_url_returns_422[http://-Invalid URL]` | ✅ PASS |
| **REQ-SHORT-013** | MUST | POST /shorten with non-http/https scheme → 422 identifying bad scheme | `models.py : _ALLOWED_SCHEMES`<br>`models.py : ShortenRequest.validate_url` (scheme allowlist check) | `test_api.py :: test_scn004_invalid_url_returns_422[ftp://example.com]`<br>`test_api.py :: test_scn004_invalid_url_returns_422[javascript:alert(1)]`<br>`test_api.py :: test_scn004_invalid_url_returns_422[data:text/html,hello]`<br>`test_api.py :: test_scn004_invalid_url_returns_422[file:///etc/passwd]`<br>`test_api.py :: test_scn004_invalid_url_returns_422[]`<br>`test_api.py :: test_scn004_invalid_url_returns_422[not-a-url]`<br>*(+ 6 matching cases in test_scenarios.py)* | ✅ PASS |
| **REQ-SHORT-014** | MUST | POST /shorten with url > 2048 chars → 422 | `models.py : ShortenRequest.validate_url` (len check, line 49) | `test_api.py :: test_scn010_url_too_long_returns_422`<br>`test_api.py :: test_scn004_url_too_long_returns_422`<br>`test_scenarios.py :: test_scn010_url_too_long_returns_422` | ✅ PASS |

### 1.8 Rate Limiting

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-015** | MUST | POST /shorten: max 60 req/IP/60 s; 61st → 429 with `Retry-After` header | `limiter.py : _LIMIT` (60)<br>`limiter.py : _WINDOW_SECONDS` (60)<br>`limiter.py : check_rate_limit`<br>`router.py : shorten_url` (calls `limiter.check_rate_limit`) | `test_api.py :: test_scn011_rate_limit_returns_429`<br>`test_scenarios.py :: test_scn011_rate_limit_returns_429` | ✅ PASS |

### 1.9 Extended Features (beyond base spec)

| REQ-ID | Priority | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **REQ-SHORT-EXPIRY** | MUST | Optional `expires_at`; past value → 422 at creation; expired link → 410 Gone | `models.py : ShortenRequest.expires_at`<br>`models.py : ShortenRequest.validate_expires_at`<br>`models.py : LinkRecord.expires_at`<br>`store.py : _is_expired`<br>`store.py : is_expired`<br>`store.py : create_link` (stores expires_at)<br>`router.py : redirect_to_url` (HTTPException 410)<br>`router.py : shorten_url` (passes expires_at) | `test_api.py :: test_expiry_future_date_accepted`<br>`test_api.py :: test_expiry_past_date_rejected`<br>`test_api.py :: test_expired_link_returns_410` | ✅ PASS |
| **REQ-SHORT-TIMESTAMPS** | MUST | `created_at` set on creation; `last_accessed_at` updated on each redirect | `models.py : LinkRecord.created_at`<br>`models.py : LinkRecord.last_accessed_at`<br>`store.py : create_link` (sets `created_at = _now()`)<br>`store.py : record_access` (sets `last_accessed_at = _now()`) | `test_api.py :: test_scn001_shorten_valid_url` (created_at present)<br>`test_api.py :: test_scn002_redirect_increments_clicks_and_records_access` (last_accessed_at set)<br>`test_api.py :: test_analytics_returns_full_stats` | ✅ PASS |
| **REQ-SHORT-REFERRER** | MUST | `Referer` header captured per redirect; aggregated per code; absent → `"(direct)"` | `store.py : _referrers` (Counter dict)<br>`store.py : record_access` (normalises + increments)<br>`store.py : get_analytics` (top-10 most_common)<br>`models.py : AnalyticsResponse.top_referrers`<br>`router.py : redirect_to_url` (extracts Referer header) | `test_api.py :: test_referrer_direct_traffic_recorded`<br>`test_api.py :: test_referrer_multiple_sources_aggregated`<br>`test_api.py :: test_analytics_returns_full_stats` | ✅ PASS |
| **REQ-SHORT-ANALYTICS** | MUST | GET /analytics/{code} → clicks, timestamps, is_expired, top_referrers (no click side-effect) | `router.py : get_analytics`<br>`store.py : get_analytics`<br>`models.py : AnalyticsResponse` | `test_api.py :: test_analytics_returns_full_stats`<br>`test_api.py :: test_analytics_unknown_code_returns_404`<br>`test_api.py :: test_analytics_does_not_increment_clicks` | ✅ PASS |
| **REQ-SHORT-MALICIOUS** | MUST | Blocked domains → 422; private/loopback addresses → 422 (SSRF prevention) | `models.py : _BLOCKED_DOMAINS`<br>`models.py : _PRIVATE_HOST_RE`<br>`models.py : ShortenRequest.validate_url` (blocklist + regex checks) | `test_api.py :: test_blocked_domain_returns_422[http://malware.example/payload]`<br>`test_api.py :: test_blocked_domain_returns_422[https://phishing.example/login]`<br>`test_api.py :: test_blocked_domain_returns_422[http://spam.example]`<br>`test_api.py :: test_private_address_returns_422[http://localhost/admin]`<br>`test_api.py :: test_private_address_returns_422[http://127.0.0.1:8080/secret]`<br>`test_api.py :: test_private_address_returns_422[http://192.168.1.1/router]`<br>`test_api.py :: test_private_address_returns_422[http://10.0.0.1/internal]` | ✅ PASS |

---

## Section 2 — Non-Functional Requirements

| NFR-ID | Category | Statement (short) | Implementing symbol(s) | Test cases | Status |
|---|---|---|---|---|---|
| **NFR-PERF-001** | Performance | POST /shorten < 50 ms p99 under 100 concurrent requests | In-memory dict O(1) write in `store.py : create_link`; no I/O in hot path | ⚠️ NO AUTOMATED TEST (load test required) | — |
| **NFR-PERF-002** | Performance | GET /{code} < 10 ms p99; in-memory lookup only, no I/O | `store.py : get_link` (dict lookup O(1)) | ⚠️ NO AUTOMATED TEST (load test required) | — |
| **NFR-PERF-003** | Performance | 1 000 active mappings with no latency degradation | Dict operations remain O(1) regardless of size | ⚠️ NO AUTOMATED TEST (load test required) | — |
| **NFR-SEC-001** | Security | Only http/https schemes accepted; all others rejected before store write | `models.py : _ALLOWED_SCHEMES`<br>`models.py : ShortenRequest.validate_url` (scheme check runs before HttpUrl parse) | Covered by REQ-SHORT-013 tests | ✅ PASS |
| **NFR-SEC-002** | Security | Code generation uses cryptographic entropy (62^8 ≈ 2.18×10¹⁴ codes) | `store.py : _generate_code` (`secrets.choice` — CSPRNG) | ⚠️ NO AUTOMATED TEST (statistical / audit) | — |
| **NFR-SEC-003** | Security | Service does not pre-fetch or validate destination URL | `router.py : redirect_to_url` (returns `RedirectResponse` without fetching) | `test_api.py :: test_scn002_redirect_increments_clicks_and_records_access` (redirect returns immediately) | ✅ PASS |
| **NFR-VAL-001** | Validation | Schema validation before any business logic; invalid body → structured 422 | `models.py : ShortenRequest` (Pydantic validates on construction, before `shorten_url` body executes) | Covered by REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014 tests | ✅ PASS |
| **NFR-VAL-002** | Validation | Both scheme-allowlist check AND URI-structural parse; each failure identifies which check failed | `models.py : ShortenRequest.validate_url` (distinct error messages per check: "http or https scheme" vs "Invalid URL format") | `test_scenarios.py :: test_scn004_invalid_url_returns_422` (asserts `expected_fragment` per case) | ✅ PASS |
| **NFR-VAL-003** | Validation | URL field rejected if > 2048 chars | `models.py : ShortenRequest.validate_url` (len check, line 49) | Covered by REQ-SHORT-014 tests | ✅ PASS |
| **NFR-RL-001** | Rate Limiting | In-process sliding-window counter, no external service | `limiter.py : _buckets` (plain dict)<br>`limiter.py : check_rate_limit` | Covered by REQ-SHORT-015 tests | ✅ PASS |
| **NFR-RL-002** | Rate Limiting | 429 response MUST include `Retry-After` header (positive integer seconds) | `limiter.py : check_rate_limit` (headers={"Retry-After": str(retry_after)}) | `test_api.py :: test_scn011_rate_limit_returns_429`<br>`test_scenarios.py :: test_scn011_rate_limit_returns_429` (both assert `int(retry_after) > 0`) | ✅ PASS |
| **NFR-RL-003** | Rate Limiting | Counters keyed by client IP; `X-Forwarded-For` respected behind trusted proxy | `limiter.py : _get_client_ip` (reads X-Forwarded-For first) | ⚠️ NO AUTOMATED TEST (proxy header not simulated in test suite) | — |

---

## Section 3 — Gherkin Scenario Coverage

| SCN-ID | Title | REQ-IDs | test_scenarios.py function | test_api.py function | Status |
|---|---|---|---|---|---|
| SCN-001 | Shorten a valid HTTPS URL | REQ-SHORT-001, -002, -003 | `test_scn001_shorten_valid_url` | `test_scn001_shorten_valid_url` | ✅ PASS |
| SCN-002 | Resolve existing code → 307 redirect | REQ-SHORT-004, -006 | `test_scn002_redirect_to_original_url` | `test_scn002_redirect_increments_clicks_and_records_access` | ✅ PASS |
| SCN-003 | Unknown code → 404 | REQ-SHORT-005 | `test_scn003_unknown_code_returns_404` | `test_scn003_resolve_unknown_code_returns_404` | ✅ PASS |
| SCN-004 | Invalid URL → 422 | REQ-SHORT-012, -013 | `test_scn004_invalid_url_returns_422` (×7 parametrized) | `test_scn004_invalid_url_returns_422` (×7 parametrized) | ✅ PASS |
| SCN-005 | Delete existing code → 204, then 404 | REQ-SHORT-007 | `test_scn005_delete_existing_code` | `test_scn005_delete_existing_code` | ✅ PASS |
| SCN-006 | Delete non-existent code → 404 | REQ-SHORT-008 | `test_scn006_delete_nonexistent_returns_404` | `test_scn006_delete_nonexistent_code_returns_404` | ✅ PASS |
| SCN-007 | GET /links returns all mappings | REQ-SHORT-009 | `test_scn007_list_all_links` | `test_scn007_list_all_links` | ✅ PASS |
| SCN-008 | Duplicate URL → 409 with existing code | REQ-SHORT-010 | `test_scn008_duplicate_url_returns_409` | `test_scn008_duplicate_url_returns_409` | ✅ PASS |
| SCN-009 | Health check → 200 `{"status":"ok"}` | REQ-SHORT-011 | `test_scn009_health_check` | `test_scn009_health_check` | ✅ PASS |
| SCN-010 | URL > 2048 chars → 422 | REQ-SHORT-014 | `test_scn010_url_too_long_returns_422` | `test_scn010_url_too_long_returns_422` | ✅ PASS |
| SCN-011 | Rate limit exceeded → 429 + Retry-After | REQ-SHORT-015 | `test_scn011_rate_limit_returns_429` | `test_scn011_rate_limit_returns_429` | ✅ PASS |

---

## Section 4 — Complete Test Inventory

All 54 test cases from the last run, grouped by file.

### `tests/test_api.py` — 36 cases

| Test function | REQ-IDs covered | Result |
|---|---|---|
| `test_scn001_shorten_valid_url` | REQ-SHORT-001, -002 | ✅ PASS |
| `test_scn002_redirect_increments_clicks_and_records_access` | REQ-SHORT-004, -006, TIMESTAMPS, REFERRER | ✅ PASS |
| `test_scn003_resolve_unknown_code_returns_404` | REQ-SHORT-005 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[not-a-url]` | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[ftp://example.com]` | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[javascript:alert(1)]` | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[data:text/html,hello]` | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[]` | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[http://]` | REQ-SHORT-012 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[file:///etc/passwd]` | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_url_too_long_returns_422` | REQ-SHORT-014 | ✅ PASS |
| `test_scn005_delete_existing_code` | REQ-SHORT-007 | ✅ PASS |
| `test_scn006_delete_nonexistent_code_returns_404` | REQ-SHORT-008 | ✅ PASS |
| `test_scn007_list_all_links` | REQ-SHORT-009 | ✅ PASS |
| `test_scn008_duplicate_url_returns_409` | REQ-SHORT-010 | ✅ PASS |
| `test_scn009_health_check` | REQ-SHORT-011 | ✅ PASS |
| `test_scn010_url_too_long_returns_422` | REQ-SHORT-014 | ✅ PASS |
| `test_scn011_rate_limit_returns_429` | REQ-SHORT-015, NFR-RL-002 | ✅ PASS |
| `test_expiry_future_date_accepted` | REQ-SHORT-EXPIRY | ✅ PASS |
| `test_expiry_past_date_rejected` | REQ-SHORT-EXPIRY | ✅ PASS |
| `test_expired_link_returns_410` | REQ-SHORT-EXPIRY | ✅ PASS |
| `test_analytics_returns_full_stats` | REQ-SHORT-ANALYTICS, -006, TIMESTAMPS, REFERRER, EXPIRY | ✅ PASS |
| `test_analytics_unknown_code_returns_404` | REQ-SHORT-ANALYTICS | ✅ PASS |
| `test_analytics_does_not_increment_clicks` | REQ-SHORT-ANALYTICS, -006 | ✅ PASS |
| `test_referrer_direct_traffic_recorded` | REQ-SHORT-REFERRER | ✅ PASS |
| `test_referrer_multiple_sources_aggregated` | REQ-SHORT-REFERRER | ✅ PASS |
| `test_blocked_domain_returns_422[http://malware.example/payload]` | REQ-SHORT-MALICIOUS | ✅ PASS |
| `test_blocked_domain_returns_422[https://phishing.example/login]` | REQ-SHORT-MALICIOUS | ✅ PASS |
| `test_blocked_domain_returns_422[http://spam.example]` | REQ-SHORT-MALICIOUS | ✅ PASS |
| `test_private_address_returns_422[http://localhost/admin]` | REQ-SHORT-MALICIOUS, NFR-SEC | ✅ PASS |
| `test_private_address_returns_422[http://127.0.0.1:8080/secret]` | REQ-SHORT-MALICIOUS, NFR-SEC | ✅ PASS |
| `test_private_address_returns_422[http://192.168.1.1/router]` | REQ-SHORT-MALICIOUS, NFR-SEC | ✅ PASS |
| `test_private_address_returns_422[http://10.0.0.1/internal]` | REQ-SHORT-MALICIOUS, NFR-SEC | ✅ PASS |
| `test_click_count_accumulates` | REQ-SHORT-006 | ✅ PASS |
| `test_links_route_not_captured_by_wildcard` | REQ-SHORT-009 | ✅ PASS |
| `test_healthz_route_not_captured_by_wildcard` | REQ-SHORT-011 | ✅ PASS |

### `tests/test_scenarios.py` — 18 cases

| Test function | SCN-ID | REQ-IDs covered | Result |
|---|---|---|---|
| `test_scn001_shorten_valid_url` | SCN-001 | REQ-SHORT-001, -002, -003 | ✅ PASS |
| `test_scn002_redirect_to_original_url` | SCN-002 | REQ-SHORT-004, -006 | ✅ PASS |
| `test_scn003_unknown_code_returns_404` | SCN-003 | REQ-SHORT-005 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[not-a-url-http or https]` | SCN-004 | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[ftp://files.example.com-http or https]` | SCN-004 | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[javascript:alert(1)-http or https]` | SCN-004 | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[data:text/html,hello-http or https]` | SCN-004 | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[-http or https]` | SCN-004 | REQ-SHORT-013 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[http://-Invalid URL]` | SCN-004 | REQ-SHORT-012 | ✅ PASS |
| `test_scn004_invalid_url_returns_422[file:///etc/passwd-http or https]` | SCN-004 | REQ-SHORT-013 | ✅ PASS |
| `test_scn005_delete_existing_code` | SCN-005 | REQ-SHORT-007 | ✅ PASS |
| `test_scn006_delete_nonexistent_returns_404` | SCN-006 | REQ-SHORT-008 | ✅ PASS |
| `test_scn007_list_all_links` | SCN-007 | REQ-SHORT-009 | ✅ PASS |
| `test_scn008_duplicate_url_returns_409` | SCN-008 | REQ-SHORT-010 | ✅ PASS |
| `test_scn009_health_check` | SCN-009 | REQ-SHORT-011 | ✅ PASS |
| `test_scn010_url_too_long_returns_422` | SCN-010 | REQ-SHORT-014 | ✅ PASS |
| `test_scn011_rate_limit_returns_429` | SCN-011 | REQ-SHORT-015, NFR-RL-002 | ✅ PASS |
| `test_extra_click_count_accumulates` | EXTRA | REQ-SHORT-006 | ✅ PASS |

---

## Section 5 — Coverage Summary

| Dimension | Count | Detail |
|---|---|---|
| Functional requirements (REQ-SHORT-NNN) | **15 / 15 implemented** | REQ-SHORT-001 through -015 |
| Extended requirements | **5 / 5 implemented** | EXPIRY, TIMESTAMPS, REFERRER, ANALYTICS, MALICIOUS |
| Gherkin scenarios (SCN-NNN) | **11 / 11 covered** | SCN-001 through SCN-011, each with 2 independent test functions |
| Functional NFRs with automated tests | **5 / 12** | NFR-SEC-001, -003; NFR-VAL-001, -002, -003; NFR-RL-001, -002 |
| NFRs requiring non-unit verification | **5** | NFR-PERF-001/002/003 (load test), NFR-SEC-002 (audit), NFR-RL-003 (proxy integration) |
| Total test cases | **54 passed / 0 failed** | 36 in `test_api.py`, 18 in `test_scenarios.py` |

### Requirements with no automated test (gap register)

| ID | Reason automated test is insufficient | Recommended verification method |
|---|---|---|
| NFR-PERF-001 | p99 latency under 100 concurrent requests cannot be measured with `TestClient` | `locust` or `pytest-benchmark` load test |
| NFR-PERF-002 | Same as above | Same |
| NFR-PERF-003 | Requires inserting 1 000 records and timing lookups under load | Benchmark fixture seeding 1 000 entries |
| NFR-SEC-002 | CSPRNG audit — verifying `secrets.choice` is used rather than `random` is a code-review concern, not a runtime assertion | Code review: `grep -n "random\." src/store.py` should return no results |
| NFR-RL-003 | `X-Forwarded-For` handling requires a test that simulates a proxy; `TestClient` uses a fixed client IP | Integration test with `headers={"X-Forwarded-For": "1.2.3.4"}` against a running uvicorn instance |

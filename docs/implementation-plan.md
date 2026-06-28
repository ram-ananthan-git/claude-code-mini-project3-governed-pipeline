# Implementation Plan — URL Shortener Service

**Generated from:** `prompts/architect.yaml`  
**Spec:** `specs/url-shortener.yaml` (SVC-URL-SHORTENER v1.0.0)  
**Prompt variables applied:**

| Variable | Value |
|---|---|
| `service_name` | URL Shortener Service |
| `language` | Python 3.12+ |
| `framework` | FastAPI |
| `storage_type` | in-memory dict |
| `max_src_files` | 5 (4 logic modules + `main.py`) |

> **Constraint note:** `max_src_files` is raised from the template default of 4 to 5.
> REQ-SHORT-015 (rate limiting) introduces enough isolated state and logic
> that embedding it in `router.py` would violate the single-responsibility
> principle. A dedicated `src/limiter.py` is the minimal addition required.

---

## 1. File Tree

Every file to be created, with its single-line purpose.

```
src/
├── __init__.py          empty package marker
├── models.py            Pydantic request/response models and field validation
├── store.py             In-memory dict store + reverse URL index
├── limiter.py           Per-IP sliding-window rate limiter (in-process)
├── router.py            FastAPI route handlers for all 5 endpoints
└── main.py              FastAPI app instantiation and router/middleware wiring

tests/
├── __init__.py          empty package marker
└── test_api.py          Integration tests — one function per Gherkin scenario

docs/
├── implementation-plan.md   this file
└── traceability-matrix.md   REQ-ID → file → test cross-reference (Task 8)
```

---

## 2. Data Models

Pydantic model definitions derived from `api_contract` schemas in the spec.

### `ShortenRequest`
| Field | Type | Required | Constraint | Spec ref |
|---|---|---|---|---|
| `url` | `str` | yes | http/https scheme; max 2048 chars; valid URI | REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014 |

### `LinkRecord`
| Field | Type | Required | Default | Spec ref |
|---|---|---|---|---|
| `short_code` | `str` | yes | — | REQ-SHORT-002 |
| `original_url` | `str` | yes | — | REQ-SHORT-001 |
| `short_url` | `str` | yes | — | REQ-SHORT-001 |
| `clicks` | `int` | yes | `0` | REQ-SHORT-006 |

### `HealthResponse`
| Field | Type | Required | Default | Spec ref |
|---|---|---|---|---|
| `status` | `Literal["ok"]` | yes | `"ok"` | REQ-SHORT-011 |

### `RateLimitBucket` (internal, not serialised)
| Field | Type | Required | Default | Spec ref |
|---|---|---|---|---|
| `request_count` | `int` | yes | `0` | NFR-RL-001 |
| `window_start` | `float` | yes | `time.time()` | NFR-RL-001 |

---

## 3. Routing Table

| Method | Path | Handler | Req IDs |
|---|---|---|---|
| `POST` | `/shorten` | `shorten_url` | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003, REQ-SHORT-010, REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014, REQ-SHORT-015 |
| `GET` | `/{code}` | `redirect_to_url` | REQ-SHORT-004, REQ-SHORT-005, REQ-SHORT-006 |
| `DELETE` | `/{code}` | `delete_link` | REQ-SHORT-007, REQ-SHORT-008 |
| `GET` | `/links` | `list_links` | REQ-SHORT-009 |
| `GET` | `/healthz` | `health_check` | REQ-SHORT-011 |

> **Route order constraint:** `/links` and `/healthz` MUST be registered before
> `/{code}`. FastAPI matches routes in registration order; a request to `/links`
> would otherwise be captured by the `/{code}` wildcard and return a spurious 404.

---

## 4. Module Responsibilities

### `src/models.py`
| Symbol | Kind | Req IDs |
|---|---|---|
| `ShortenRequest` | class | REQ-SHORT-001, REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014 |
| `ShortenRequest.validate_url` | function (validator) | REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014, NFR-SEC-001, NFR-VAL-001, NFR-VAL-002, NFR-VAL-003 |
| `LinkRecord` | class | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-006 |
| `HealthResponse` | class | REQ-SHORT-011 |

### `src/store.py`
| Symbol | Kind | Req IDs |
|---|---|---|
| `_store` | constant (dict) | REQ-SHORT-001, REQ-SHORT-003 |
| `_url_index` | constant (dict) | REQ-SHORT-010 |
| `create_link` | function | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003, REQ-SHORT-010 |
| `get_link` | function | REQ-SHORT-004, REQ-SHORT-005 |
| `increment_clicks` | function | REQ-SHORT-006 |
| `delete_link` | function | REQ-SHORT-007, REQ-SHORT-008 |
| `list_links` | function | REQ-SHORT-009 |
| `clear` | function | test isolation only |

### `src/limiter.py`
| Symbol | Kind | Req IDs |
|---|---|---|
| `_buckets` | constant (dict) | NFR-RL-001, NFR-RL-003 |
| `check_rate_limit` | function | REQ-SHORT-015, NFR-RL-001, NFR-RL-002, NFR-RL-003 |
| `clear` | function | test isolation only |

### `src/router.py`
| Symbol | Kind | Req IDs |
|---|---|---|
| `router` | constant (APIRouter) | — |
| `health_check` | function | REQ-SHORT-011 |
| `list_links` | function | REQ-SHORT-009 |
| `shorten_url` | function | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003, REQ-SHORT-010, REQ-SHORT-015 |
| `redirect_to_url` | function | REQ-SHORT-004, REQ-SHORT-005, REQ-SHORT-006 |
| `delete_link` | function | REQ-SHORT-007, REQ-SHORT-008 |

### `src/main.py`
| Symbol | Kind | Req IDs |
|---|---|---|
| `app` | constant (FastAPI) | REQ-SHORT-011 |

---

## 5. Numbered Tasks

Tasks are ordered by dependency. Each task is self-contained: its acceptance
criteria can be verified independently before the next task begins.

---

### Task 1 — Project scaffold

**Depends on:** nothing  
**Requirement IDs:** none (infrastructure)

Create the package markers and verify the virtual environment is complete.

```
src/__init__.py     (empty)
tests/__init__.py   (empty)
```

Verify the following are importable from `.venv`:
`fastapi`, `pydantic`, `uvicorn`, `pytest`, `httpx`

**Acceptance criteria:**
- [ ] `python -c "import fastapi, pydantic, uvicorn, pytest, httpx"` exits 0
- [ ] `src/__init__.py` and `tests/__init__.py` exist and are empty
- [ ] Running `pytest tests/` with no test files exits 0 (no collection errors)

---

### Task 2 — Data models (`src/models.py`)

**Depends on:** Task 1  
**Requirement IDs:** REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-006, REQ-SHORT-011, REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014  
**NFR IDs:** NFR-SEC-001, NFR-VAL-001, NFR-VAL-002, NFR-VAL-003

Implement three Pydantic models. All validation logic for the `url` field
lives here — handlers in `router.py` MUST NOT re-implement it.

**`ShortenRequest.validate_url` must enforce in order:**
1. Strip surrounding whitespace
2. Reject `len(url) > 2048` → `"URL must not exceed 2048 characters"` (REQ-SHORT-014, NFR-VAL-003)
3. Reject scheme not in `{"http", "https"}` → `"URL must use http or https scheme"` (REQ-SHORT-013, NFR-SEC-001)
4. Run `pydantic.HttpUrl(url)` structural parse → `"Invalid URL format"` (REQ-SHORT-012, NFR-VAL-002)

**Acceptance criteria:**
- [ ] `ShortenRequest(url="https://example.com")` constructs without error
- [ ] `ShortenRequest(url="ftp://x.com")` raises `ValidationError` with msg containing `"http or https"`
- [ ] `ShortenRequest(url="javascript:alert(1)")` raises `ValidationError`
- [ ] `ShortenRequest(url="http://")` raises `ValidationError`
- [ ] `ShortenRequest(url="h" * 2049)` raises `ValidationError` with msg containing `"2048"`
- [ ] `ShortenRequest(url="")` raises `ValidationError`
- [ ] `LinkRecord` default `clicks` is `0`
- [ ] `HealthResponse` default `status` is `"ok"`

---

### Task 3 — In-memory store (`src/store.py`)

**Depends on:** Task 2  
**Requirement IDs:** REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003, REQ-SHORT-004, REQ-SHORT-005, REQ-SHORT-006, REQ-SHORT-007, REQ-SHORT-008, REQ-SHORT-009, REQ-SHORT-010  
**NFR IDs:** NFR-PERF-002, NFR-SEC-002

Implement the two in-memory indexes and all store operations. The module-level
dicts `_store` (code → `LinkRecord`) and `_url_index` (url → code) MUST be kept
in sync on every write.

**`create_link(original_url, base_url) → tuple[LinkRecord, bool]`**
- Check `_url_index` first; return `(existing_record, False)` if found (REQ-SHORT-010)
- Generate code with `secrets.choice` over `string.ascii_letters + string.digits` (NFR-SEC-002)
- Loop on collision until a unique code is found (REQ-SHORT-003)
- Return `(new_record, True)` on creation

**`delete_link(code) → bool`**
- Return `False` if code not in `_store` (REQ-SHORT-008)
- Remove from both `_store` and `_url_index` (REQ-SHORT-007)
- Return `True`

**Acceptance criteria:**
- [ ] `create_link("https://a.com", "http://short.ly")` returns a `LinkRecord` with 8-char alphanumeric `short_code`
- [ ] Calling `create_link` twice with the same URL returns the same code and `created=False` on the second call (REQ-SHORT-010)
- [ ] `create_link` with two different URLs produces two different codes (REQ-SHORT-003)
- [ ] `get_link("nonexistent")` returns `None` (REQ-SHORT-005)
- [ ] `increment_clicks(code)` increases the `clicks` field by 1 (REQ-SHORT-006)
- [ ] `delete_link` returns `True` and removes the entry from both indexes (REQ-SHORT-007)
- [ ] `delete_link("nonexistent")` returns `False` without raising (REQ-SHORT-008)
- [ ] `list_links()` returns all active `LinkRecord` objects (REQ-SHORT-009)
- [ ] `clear()` empties both dicts (used in test isolation)

---

### Task 4 — Rate limiter (`src/limiter.py`)

**Depends on:** Task 1  
**Requirement IDs:** REQ-SHORT-015  
**NFR IDs:** NFR-RL-001, NFR-RL-002, NFR-RL-003

Implement an in-process sliding-window rate limiter keyed by client IP.
No external dependencies are permitted (NFR-RL-001).

**`check_rate_limit(ip: str) → None`**
- Fetch or create a `RateLimitBucket` for `ip` in `_buckets`
- If `time.time() - bucket.window_start >= 60`: reset `request_count = 1`, update `window_start`
- Else if `bucket.request_count >= 60`: compute `retry_after = ceil(60 - elapsed)`,
  raise `HTTPException(429)` with header `{"Retry-After": str(retry_after)}` and
  body `{"detail": f"Rate limit exceeded. Try again in {retry_after} seconds."}` (NFR-RL-002)
- Else: increment `bucket.request_count`

**`_get_client_ip(request: Request) → str`**
- Return `request.headers.get("X-Forwarded-For", "").split(",")[0].strip()` if present (NFR-RL-003)
- Fall back to `request.client.host`

**Acceptance criteria:**
- [ ] 60 calls to `check_rate_limit("1.2.3.4")` within the window all succeed
- [ ] The 61st call within the same window raises `HTTPException` with `status_code=429`
- [ ] The `429` exception carries a `Retry-After` header with a positive integer value (NFR-RL-002)
- [ ] Calling `check_rate_limit` with a different IP is not affected by another IP's counter (NFR-RL-003)
- [ ] After 60 seconds the window resets and requests are accepted again (NFR-RL-001)
- [ ] `clear()` empties `_buckets` (used in test isolation)

---

### Task 5 — Route handlers (`src/router.py`)

**Depends on:** Tasks 2, 3, 4  
**Requirement IDs:** REQ-SHORT-001 through REQ-SHORT-015  
**NFR IDs:** NFR-PERF-001, NFR-PERF-002, NFR-SEC-003

Wire the store and limiter to FastAPI route functions. Apply REQ-ID inline
comments above every logical block. Register routes in the order shown in
the routing table (Section 3) to avoid wildcard shadowing.

**`shorten_url(body, request)` — POST /shorten**
1. Extract client IP and call `limiter.check_rate_limit(ip)` → may raise 429 (REQ-SHORT-015)
2. Call `store.create_link(body.url, base_url)` → returns `(record, created)`
3. Return `record` with status 201 if `created`, else status 200 (REQ-SHORT-010)

**`redirect_to_url(code)` — GET /{code}**
1. `store.get_link(code)` → raise `HTTPException(404)` if `None` (REQ-SHORT-005)
2. `store.increment_clicks(code)` (REQ-SHORT-006)
3. Return `RedirectResponse(url=record.original_url, status_code=307)` (REQ-SHORT-004)
   — do NOT fetch or validate the destination URL (NFR-SEC-003)

**`delete_link(code)` — DELETE /{code}**
1. `store.delete_link(code)` → raise `HTTPException(404)` if `False` (REQ-SHORT-008)
2. Return `Response(status_code=204)` (REQ-SHORT-007)

**`list_links()` — GET /links**
1. Return `store.list_links()` (REQ-SHORT-009)

**`health_check()` — GET /healthz**
1. Return `HealthResponse()` (REQ-SHORT-011)

**Acceptance criteria:**
- [ ] `POST /shorten` with valid URL → 201 and body fields `short_code`, `short_url`, `original_url`, `clicks` (REQ-SHORT-001)
- [ ] `POST /shorten` with same URL twice → second response is 200 with identical `short_code` (REQ-SHORT-010)
- [ ] `POST /shorten` with invalid URL → 422 (delegated to Pydantic, not re-validated here) (REQ-SHORT-012)
- [ ] `GET /{code}` with valid code → 307 with correct `Location` header (REQ-SHORT-004)
- [ ] `GET /{code}` with unknown code → 404 `{"detail": "Short code not found"}` (REQ-SHORT-005)
- [ ] `GET /{code}` increments click count visible in `GET /links` (REQ-SHORT-006)
- [ ] `DELETE /{code}` with valid code → 204, subsequent `GET /{code}` → 404 (REQ-SHORT-007)
- [ ] `DELETE /{code}` with unknown code → 404 (REQ-SHORT-008)
- [ ] `GET /links` → 200, array of all active records with all four fields (REQ-SHORT-009)
- [ ] `GET /healthz` → 200 `{"status": "ok"}` (REQ-SHORT-011)
- [ ] 61st `POST /shorten` from same IP → 429 with `Retry-After` header (REQ-SHORT-015)
- [ ] `/links` and `/healthz` resolve correctly and are not captured by `/{code}` wildcard

---

### Task 6 — Application entry point (`src/main.py`)

**Depends on:** Task 5  
**Requirement IDs:** REQ-SHORT-011  
**NFR IDs:** NFR-PERF-001 (startup time)

Create the `FastAPI` instance and attach the router. No middleware or
additional layers beyond what the spec requires.

```python
app = FastAPI(title="URL Shortener Service", version="1.0.0")
app.include_router(router)
```

**Acceptance criteria:**
- [ ] `from src.main import app` succeeds without error
- [ ] `uvicorn src.main:app --port 8000` starts in under 2 seconds (NFR-PERF-001 startup proxy)
- [ ] `GET /healthz` returns `{"status": "ok"}` on the running server

---

### Task 7 — Integration tests (`tests/test_api.py`)

**Depends on:** Task 6  
**Requirement IDs:** all REQ-SHORT-001 through REQ-SHORT-015  
**Covers scenarios:** SCN-001 through SCN-011

One test function per Gherkin scenario. Every function opens with a comment
citing its scenario ID and the REQ-IDs it covers. A module-level `autouse`
fixture calls `store.clear()` and `limiter.clear()` before each test.

| Scenario | Test function | Parametrized? |
|---|---|---|
| SCN-001 | `test_scn001_shorten_valid_url` | no |
| SCN-002 | `test_scn002_redirect_increments_clicks` | no |
| SCN-003 | `test_scn003_unknown_code_returns_404` | no |
| SCN-004 | `test_scn004_invalid_url_returns_422` | yes — 6 bad URLs |
| SCN-005 | `test_scn005_delete_existing_code` | no |
| SCN-006 | `test_scn006_delete_nonexistent_returns_404` | no |
| SCN-007 | `test_scn007_list_all_links` | no |
| SCN-008 | `test_scn008_idempotent_shorten` | no |
| SCN-009 | `test_scn009_health_check` | no |
| SCN-010 | `test_scn010_url_too_long_returns_422` | no |
| SCN-011 | `test_scn011_rate_limit_returns_429` | no |

**Acceptance criteria:**
- [ ] `pytest tests/ -v` exits 0 with all 16+ test cases passing (11 scenarios; SCN-004 expands to 6)
- [ ] No test accesses `_store`, `_url_index`, or `_buckets` directly — all interaction is through HTTP
- [ ] Every test is independent: running them in any order or in isolation produces the same result
- [ ] `test_scn002` asserts `follow_redirects=False` and checks the `Location` header explicitly
- [ ] `test_scn011` asserts `Retry-After` is a positive integer in the response headers

---

### Task 8 — Traceability matrix (`docs/traceability-matrix.md`)

**Depends on:** Task 7  
**Requirement IDs:** all REQ-SHORT-001 through REQ-SHORT-015

Create a cross-reference table with four columns:

| REQ-ID | Priority | Implementing symbol(s) | Test function(s) |
|---|---|---|---|

Every REQ-SHORT-NNN from the spec must appear as a row. A requirement with
no implementing symbol or no test function must be explicitly marked `MISSING`
so the gap is visible.

**Acceptance criteria:**
- [ ] All 15 `REQ-SHORT-*` IDs appear as rows
- [ ] All 6 `NFR-*` groups (PERF, SEC, VAL, RL) appear in a second table
- [ ] No row has `MISSING` in either the implementation or test column
- [ ] Document includes a summary line: `N/N requirements implemented, N/N scenarios covered`

---

## 6. Test Plan (per Gherkin Scenario)

| Scenario ID | Test function | Req IDs | Setup steps |
|---|---|---|---|
| SCN-001 | `test_scn001_shorten_valid_url` | REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003 | Clear store; POST valid HTTPS URL |
| SCN-002 | `test_scn002_redirect_increments_clicks` | REQ-SHORT-004, REQ-SHORT-006 | Create link via POST; GET with `follow_redirects=False` |
| SCN-003 | `test_scn003_unknown_code_returns_404` | REQ-SHORT-005 | Clear store; GET unknown code |
| SCN-004 | `test_scn004_invalid_url_returns_422` | REQ-SHORT-012, REQ-SHORT-013 | Parametrize 6 bad URLs; POST each |
| SCN-005 | `test_scn005_delete_existing_code` | REQ-SHORT-007 | Create link via POST; DELETE code; verify GET 404 |
| SCN-006 | `test_scn006_delete_nonexistent_returns_404` | REQ-SHORT-008 | Clear store; DELETE unknown code |
| SCN-007 | `test_scn007_list_all_links` | REQ-SHORT-009 | Create 2 links via POST; GET /links |
| SCN-008 | `test_scn008_idempotent_shorten` | REQ-SHORT-010 | POST URL; POST same URL again; assert same code and single /links entry |
| SCN-009 | `test_scn009_health_check` | REQ-SHORT-011 | GET /healthz |
| SCN-010 | `test_scn010_url_too_long_returns_422` | REQ-SHORT-014 | POST with 2049-char URL |
| SCN-011 | `test_scn011_rate_limit_returns_429` | REQ-SHORT-015 | Send 60 POST requests; send 61st; assert 429 + Retry-After |

---

## 7. Build Order and Dependencies

```
Task 1 (scaffold)
    └── Task 2 (models)
    │       └── Task 3 (store)
    │       └── Task 5 (router) ←─────┐
    └── Task 4 (limiter) ─────────────┘
                                Task 6 (main)
                                    └── Task 7 (tests)
                                            └── Task 8 (traceability matrix)
```

Tasks 3 and 4 can be implemented in parallel — they have no dependency on each
other. Task 5 requires both to be complete before it can be written.

---

## 8. Out-of-Scope Items

The following are explicitly NOT planned because they have no corresponding
requirement in `specs/url-shortener.yaml v1.0.0`:

- Persistent storage (database, Redis)
- Link expiry / TTL
- Authentication or API keys
- Custom short-code aliases
- Metrics endpoint (`/metrics`)
- Admin dashboard
- Bulk shorten operations
- Click-through analytics beyond a simple counter

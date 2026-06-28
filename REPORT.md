# Week 2 Mini Project Report — Spec-Driven Feature Factory
## URL Shortener Service (SVC-URL-SHORTENER v1.0.0)

---

### Q1. What is spec-driven development and why does it matter?

Spec-driven development means writing a machine-readable, requirement-identified
specification *before* any code exists, then using that spec as the authoritative
reference at every downstream step — architecture, code, tests, and docs. Every
requirement gets a unique ID (`REQ-SHORT-001` through `REQ-SHORT-015`), every
implementing function carries an inline comment referencing those IDs, and every
test function opens with a comment citing both a scenario ID and the requirements
it covers.

It matters for three concrete reasons this project demonstrated:

1. **Gap prevention** — writing `REQ-SHORT-010` (idempotency) before
   implementation forced a reverse URL index into the data model from day one,
   preventing a design that would have been expensive to retrofit.
2. **Error contract clarity** — the `api_contract` section decided upfront that
   duplicates return 409, expired links return 410, and rate-limited requests
   return 429 with `Retry-After`, so no ambiguity existed during coding.
3. **Living traceability** — `docs/traceability-matrix.md` was generated
   mechanically by cross-referencing REQ-IDs in source, because those IDs were
   placed in both spec and code deliberately rather than added as an afterthought.

---

### Q2. Describe the structure of your YAML spec. What sections does it contain and why?

`specs/url-shortener.yaml` (SVC-URL-SHORTENER v1.0.0) contains five top-level keys:

| Section | Purpose |
|---|---|
| `metadata` | `id: SVC-URL-SHORTENER`, `title`, `version: "1.0.0"`, `status: approved`, `owner` — uniquely identifies the spec for governance and downstream tooling |
| `requirements` | 15 entries (REQ-SHORT-001 through REQ-SHORT-015), each with `id`, `priority` (MUST/SHOULD/MAY), and `statement` in SHALL language — the authoritative *what* |
| `gherkin_scenarios` | 11 entries (SCN-001 through SCN-011), each with `id`, `title`, `req_ids` list, and `scenario` block (Given/When/Then) — the observable behaviour contract |
| `api_contract` | 5 endpoints with OpenAPI-style `method`, `path`, `request_body`, `responses` (including error shapes for 404, 422, 429) — the HTTP contract |
| `non_functional` | 12 NFRs across 4 categories: `performance` (latency targets), `security` (scheme allowlist, entropy), `validation` (schema-first, 2048 char cap), `rate_limiting` (60/60 s, Retry-After, X-Forwarded-For) |

Separating requirements from `api_contract` was deliberate: requirements describe
*what* must be true; the api_contract describes *how* it is expressed over HTTP. A
requirement can be satisfied by multiple endpoints, and an endpoint satisfies
multiple requirements — the `req_ids` arrays on both sides make that mapping explicit.

---

### Q3. What are the 4 prompt templates and which is the best? Show its JSON schema.

| Template | Role |
|---|---|
| `prompts/spec-writer.yaml` | Generates a complete YAML spec from a service description; variables: `service_name`, `service_description`, `tech_stack`, `storage_type`, `actors`, `min_scenarios` |
| `prompts/architect.yaml` | Translates a spec into a file tree, module interfaces, data models, routing table, and test plan; variables: `service_name`, `spec_yaml`, `language`, `framework`, `storage_type`, `max_src_files` |
| `prompts/code-reviewer.yaml` | Reviews source across four axes (spec_compliance, correctness, code_quality, test_coverage); output includes `findings` with severity enum and `summary` with `overall_verdict` and `pass_rate` |
| `prompts/test-generator.yaml` | Generates pytest integration tests from Gherkin scenarios; 8 explicit rules; variables: `output_file`, `service_name`, `scenarios_yaml`, `api_contract_yaml`, `app_import`, `extra_test_behaviour` |

**Best template: `prompts/test-generator.yaml`**

It is the strongest because its 8 rules are mechanically verifiable (naming
convention, opening comment format, `follow_redirects=False`, isolation
requirement), and it produced `tests/test_scenarios.py` — a directly executable
file requiring zero modifications. Its `output_schema.test_functions` array is a
machine-readable manifest of every function the template must generate:

```yaml
output_schema:
  type: object
  properties:
    imports:
      type: array
      items: {type: string}
    fixtures:
      type: array
      items:
        type: object
        required: [name, scope, autouse]
        properties:
          name:    {type: string}
          scope:   {type: string, enum: [function, module, session]}
          autouse: {type: boolean}
    test_functions:
      type: array
      items:
        type: object
        required: [name, scenario_id, req_ids, parametrized]
        properties:
          name:         {type: string, pattern: "^test_"}
          scenario_id:  {type: string, pattern: "^SCN-[0-9]{3}$"}
          req_ids:      {type: array, items: {type: string}}
          parametrized: {type: boolean}
```

The `pattern` constraints on both `name` and `scenario_id` mean a validator can
automatically check that every Gherkin scenario in the spec has a corresponding
test function in the output. No other template has this level of checkable output
structure.

---

### Q4. How did you use the spec to drive implementation? Give 2 concrete examples.

**Example 1 — REQ-SHORT-010 drove the reverse URL index.**

REQ-SHORT-010 (SHOULD): *"If POST /shorten is called with a URL that already has
an active mapping, the service SHOULD return the existing short code."* Without
this requirement, the natural default implementation would create a new code on
every POST. The spec made idempotency explicit before any code was written, which
forced `_url_index: dict[str, str]` into `src/store.py` as a first-class data
structure — a reverse mapping from `original_url` to `short_code`. That index also
powered the `get_link_by_url()` function used for duplicate detection. A
self-critique pass later found the router was accessing `_url_index` directly
(private), prompting addition of `get_link_by_url()` as a public accessor. The
spec requirement drove both the initial design and a code-quality fix.

**Example 2 — REQ-SHORT-015 drove a dedicated `src/limiter.py` module.**

REQ-SHORT-015 (MUST): *"The service SHALL enforce a rate limit of at most 60 POST
/shorten requests per IP address per 60-second sliding window."* The implementation
plan (`docs/implementation-plan.md`) noted that this requirement has completely
isolated state (`_buckets: dict[str, _Bucket]`) that belongs neither in the router
nor the store. Without the spec, rate limiting would likely have been added as a
middleware or a few lines in the router. With the spec, the architecture plan
produced `src/limiter.py` as a first-class module with its own
`check_rate_limit(request)` function and `clear()` for test isolation — before a
single line of code was written.

---

### Q5. Explain the REQ-ID comment strategy used in your code.

Every logical block that implements a requirement carries a `# REQ-SHORT-NNN`
comment on the line immediately above the function signature or the specific block
of logic. The rules applied:

1. **One comment per logical unit** — a whole function that satisfies one
   requirement gets one comment; annotating every line would be noise.
2. **Multiple IDs when a function satisfies several requirements** — `redirect_to_url`
   carries six:

```python
# REQ-SHORT-004, REQ-SHORT-005, REQ-SHORT-006, REQ-SHORT-EXPIRY,
# REQ-SHORT-TIMESTAMPS, REQ-SHORT-REFERRER
@router.get("/{short_code}")
def redirect_to_url(short_code: str, request: Request) -> Response:
```

3. **Inner comments for sub-steps** — inside the function body, each discrete
   logical step adds its own inline reference:

```python
    # REQ-SHORT-005
    if record is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    # REQ-SHORT-EXPIRY: expired links return 410 rather than redirect
    if store.is_expired(short_code):
        raise HTTPException(status_code=410, detail="This short URL has expired")
```

4. **Tests mirror the same IDs** — every test function opens with
   `# SCN-NNN | REQ-SHORT-NNN, ...` so grep can cross-reference from requirement
   to test in either direction.

---

### Q6. What are the 3 Mermaid diagram types and what does each capture?

| Diagram | File | What it captures |
|---|---|---|
| **Sequence** | `specs/diagrams/sequence-url-shortening.md` | Temporal message flows between 5 participants (Client, RateLimiter, Validator, Router, Store). 9 diagrams cover every distinct flow: POST new URL, POST duplicate, POST invalid scheme/length, POST rate-limited, GET redirect success, GET 404, DELETE 204/404, GET /links, GET /healthz. Shows which participant handles each REQ-ID and at what step validation fires. |
| **ER** | `specs/diagrams/er-diagram.md` | Logical data model: `LINK_RECORD` fields (short_code PK, original_url, short_url, clicks, created_at, last_accessed_at, expires_at), `URL_INDEX` for reverse lookup, `RATE_LIMIT_BUCKET` for per-IP counters. A second diagram shows the three in-memory dicts (`_store`, `_url_index`, `_referrers`) and how they relate at runtime. Every field is annotated with its spec reference. |
| **State** | `specs/diagrams/url-lifecycle-state.md` | Lifecycle of a short URL from `NonExistent → Active → NonExistent`. Three diagrams: top-level lifecycle with all transitions and HTTP outcomes; click-count sub-states inside `Active` (Clicks_0 → Clicks_1 → Clicks_N); per-IP rate limiter state (Window_Open ↔ Window_Reset). A transition table lists every (from-state, event, guard, to-state, HTTP response) combination. |

---

### Q7. Describe your testing strategy. Show one Gherkin scenario and its matching test function.

Tests are integration-style: all interaction goes through the HTTP layer via
FastAPI's `TestClient`. The `reset_state` fixture in `tests/conftest.py` (autouse,
function scope) calls `store.clear()` and `limiter.clear()` before and after every
test — no state leaks between functions. State is created via API calls inside the
test body, never by direct store manipulation (with one documented exception:
`test_expired_link_returns_410` backdates `record.expires_at` to avoid
`time.sleep`).

`tests/test_scenarios.py` was generated from `prompts/test-generator.yaml`: one
function per Gherkin scenario, SCN-004 parametrized over 7 `(bad_url,
expected_fragment)` pairs. `tests/test_api.py` provides a second independent
function for every scenario plus extended feature tests (expiry, analytics,
referrer, SSRF, malicious URLs). Total: 56 test cases, dual coverage of all 11
scenarios.

**SCN-002 from `specs/url-shortener.yaml`:**

```yaml
- id: SCN-002
  title: Resolve an existing short code redirects to original URL
  req_ids: [REQ-SHORT-004, REQ-SHORT-006]
  scenario: |
    Given a mapping exists for code "abc12345" pointing to "https://example.com"
    When I GET /abc12345 without following redirects
    Then the response status is 307
    And the Location header equals "https://example.com"
    And a subsequent GET /links shows "clicks" is 1 for code "abc12345"
```

**Matching test in `tests/test_scenarios.py`:**

```python
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
```

---

### Q8. What trade-offs did you make? Reference the self-critique log.

Four significant trade-offs are documented in `docs/self-critique-log.md`:

**ISSUE-004 (MINOR / Accepted) — `Retry-After` off-by-one.**
`limiter.py` uses `int(_WINDOW_SECONDS - elapsed) + 1` which can return 61 seconds
at elapsed ≈ 0. The spec (NFR-RL-002) only requires a positive integer, so the
overshoot is within contract. The correct fix is `math.ceil(...)`, but changing it
would alter no test outcome. Deferred.

**ISSUE-005 (MAJOR / Accepted for demo scope) — Hard-coded domain blocklist.**
`_BLOCKED_DOMAINS` in `models.py` contains four `*.example` test domains. In
production, adding a blocked domain requires a code change and redeploy. The spec
comment acknowledges "extend from a threat-feed in production" but provides no
mechanism. Acceptable for a demo; the gap is explicitly registered.

**ISSUE-003 (MINOR / Accepted with documentation) — `test_expired_link_returns_410`
mutates a `LinkRecord` directly.**
Template rule 5 says tests must not access implementation internals except in the
reset fixture. This test is the single deliberate exception — the alternative is a
real `time.sleep(2)` which makes the test suite 2 seconds slower for no benefit.
The mutation is safe because `LinkRecord` is a Pydantic model returned as a live
reference from `_store.get(code)`.

**ISSUE-002 (MAJOR / Fixed) — Router accessed `store._url_index` directly.**
`shorten_url` in the original `router.py` read `store._url_index[body.url]` after
calling `store.url_exists()`. This coupled the router to an internal data structure.
Fixed by adding `store.get_link_by_url(original_url) -> LinkRecord | None` and
updating the router to use it exclusively.

---

### Q9. How would you extend this service for production use?

Six extensions, each grounded in a gap identified during this build:

1. **Persistent storage** — replace `_store` dict with Redis (O(1) get/set, built-in
   TTL for link expiry matching REQ-SHORT-EXPIRY, pub/sub for cache invalidation
   across workers). The interface of `src/store.py` is already clean enough to swap
   without touching the router.
2. **Cryptographic rate limiter** — the current `_buckets` dict is process-local and
   lost on restart. Redis with atomic `INCR` + `EXPIRE` gives a shared, persistent,
   crash-safe sliding window satisfying NFR-RL-001 across multiple processes.
3. **Dynamic blocklist** — replace `_BLOCKED_DOMAINS: frozenset` with a configurable
   source (environment variable pointing to a file, or a periodic fetch from a
   threat-feed URL). `models.py` already isolates the check in one place; only the
   data source changes.
4. **Metrics endpoint** — add `GET /metrics` (Prometheus format) tracking request
   counts by endpoint and status code, redirect latency histograms, and top-clicked
   links. NFR-PERF-001 and NFR-PERF-002 have no automated test today; a Prometheus
   scrape makes them observable.
5. **X-Forwarded-For integration test** — NFR-RL-003 is implemented in
   `limiter.py:_get_client_ip` but never tested (ISSUE-006, deferred). An
   integration test that sends `X-Forwarded-For: 10.0.0.1` vs `10.0.0.2` and
   verifies independent buckets should be added.
6. **Link TTL via background task** — a FastAPI `BackgroundTask` or APScheduler job
   that prunes `_store` entries whose `expires_at` has passed, preventing unbounded
   memory growth as links expire without being accessed.

---

### Q10. What did spec-driven development force you to think about earlier?

**Idempotency.** Without REQ-SHORT-010, the first implementation would have created
a new code on every POST. The spec made this decision explicit and placed it before
a single line of business logic, so the reverse URL index was a planned data
structure, not a retrofit.

**Error contracts.** Having an `api_contract` section with explicit per-status-code
response shapes meant the 409 body (`{"message": "URL already shortened",
"short_code": "...", "short_url": "..."}`), the 410 detail text, the 422 structure,
the 429 `Retry-After` header, and the 204 no-body contract were all decided before
`router.py` was opened. No ambiguity existed during implementation.

**Route ordering.** The architecture plan's routing table listed `/links`, `/healthz`,
and `/analytics/{short_code}` before `/{short_code}` — a constraint discovered by
writing the table, not by hitting a 404 in a browser. A
`test_links_route_not_captured_by_wildcard` test was written alongside the code
rather than discovered as a regression.

---

### Q11. What is a traceability matrix and what value does it provide?

A traceability matrix is a table that links every requirement to the code that
implements it and the tests that verify it. In `docs/traceability-matrix.md` each
row maps one REQ-SHORT-NNN to specific `file.py : function` symbols and specific
`test_file.py :: test_function` names, with a live pass/fail status drawn from the
`pytest -v` output.

Value it provided on this project:

- **Completeness check** — writing the matrix revealed that `is_expired: True` was
  never asserted in any analytics test (ISSUE-007). The gap only became visible when
  every requirement was forced into a row.
- **Impact analysis** — self-critique ISSUE-002 (router accessing `store._url_index`)
  was easier to assess because the matrix showed exactly which test covered
  REQ-SHORT-010 and what the router function did.
- **Gap register** — five NFRs (NFR-PERF-001/002/003, NFR-SEC-002, NFR-RL-003) are
  marked `⚠️ NO AUTOMATED TEST` with the specific reason and recommended
  verification method. Silent coverage gaps are worse than explicit documented ones.
- **Stakeholder communication** — the summary row gives a product owner a one-line
  status without reading source code.

---

### Q12. Traceability matrix summary and what you'd do differently next time.

**Summary (from `docs/traceability-matrix.md`):**

| Dimension | Count |
|---|---|
| Functional requirements (REQ-SHORT-NNN) | 15 / 15 implemented |
| Extended requirements (EXPIRY, TIMESTAMPS, REFERRER, ANALYTICS, MALICIOUS) | 5 / 5 implemented |
| Gherkin scenarios covered | 11 / 11 (each with 2 independent test functions) |
| NFRs with automated tests | 7 / 12 |
| NFRs requiring load/audit/integration verification | 5 (documented in gap register) |
| Total test cases | **56 passed, 0 failed** |

**First-run test pass percentage:** After the full feature set (analytics, expiry,
referrer, rate limiting), the first run was **34/36 = 94.4%** — two `DELETE /{code}`
endpoints returned 405 because the handler was accidentally omitted when rewriting
`router.py`. Fixed in a single edit. After self-critique additions
(ISSUE-007-FIX + ISSUE-011-FIX), final count: 56/56 = 100%.

**Time breakdown (estimated across 4 parts):**

- Part 1 — Spec + Prompt templates + Diagrams: **~35%** — most time ensuring REQ-IDs
  were consistent across all three outputs and that diagrams reflected the actual
  `api_contract`.
- Part 2 — Architecture plan + Implementation: **~30%** — core store/router logic was
  fast; rate limiter sliding-window edge case and expiry/410 flow took the most time.
- Part 3 — Test generation: **~20%** — parametrized SCN-004 scenarios straightforward;
  debugging the two 405 DELETE failures took a few minutes; adding `conftest.py` and
  removing duplicate fixtures was mechanical.
- Part 4 — Traceability matrix + Self-critique + Report: **~15%** — traceability
  matrix was mostly cross-referencing; self-critique found 11 real issues that took
  time to reason about and fix.

**What I would do differently:**

1. **Validate the spec YAML with a JSON Schema validator from day one.** The REQ-ID
   format drifted between the first and second generation (REQ-001 vs REQ-SHORT-001),
   producing stale diagram files caught only in self-critique. A `jsonschema`
   pre-commit check against the spec's own `output_schema` would catch this
   immediately.

2. **Write NFR tests alongside functional tests.** NFR-PERF-001 and NFR-PERF-002
   (latency targets) were documented but have no automated test. A `pytest-benchmark`
   fixture seeding 1 000 links and timing a `GET /{code}` lookup would take 10
   minutes to write and permanently close that gap.

3. **Add the `X-Forwarded-For` isolation test at the same time as `limiter.py`.**
   NFR-RL-003 was implemented in `_get_client_ip` but never tested (ISSUE-006,
   deferred). The fix is two lines in a parametrized test; skipping it creates a
   documented gap that accumulates.

4. **Archive superseded artifacts explicitly.** Two sets of prompt templates
   accumulated in `prompts/` (`01-spec-generation.yaml` et al. alongside the richer
   named set). Moving the first set to `prompts/archive/` on creation of the second
   set would have prevented ISSUE-009 entirely.

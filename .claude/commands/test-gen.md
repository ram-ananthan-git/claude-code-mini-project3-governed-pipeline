# /test-gen — Generate Tests for Changed Files

## Purpose

Inspect the files that changed, identify behaviours that lack test coverage,
generate pytest functions that match the project's conventions, append them to
the right test file, and confirm the full suite stays green.

## When to use

- After implementing a new feature or endpoint
- After adding a new scenario to `specs/url-shortener.yaml`
- After `/review` reports a MAJOR "Test Coverage" finding
- Any time `git diff HEAD --name-only` shows `src/` files with no corresponding
  new tests in `tests/`

---

## Steps Claude should execute

### 1. Identify changed source files and their current test footprint

```bash
# What changed
git diff HEAD --name-only

# What tests already exist
grep -n "^def test_" tests/test_api.py tests/test_scenarios.py
```

For each changed `src/` file, note:
- Which functions/methods were added or modified
- Which REQ-IDs those functions reference
- Whether an existing test already covers the changed path

### 2. Find untested scenarios in the spec

```bash
python3 - <<'EOF'
import yaml, pathlib, re

spec = yaml.safe_load(pathlib.Path("specs/url-shortener.yaml").read_text())

# Scenarios declared in spec
declared_scn = {s["id"]: s["name"] for s in spec.get("scenarios", [])}

# REQ-IDs declared in spec
declared_req = {r["id"]: r["description"] for r in spec.get("requirements", [])}

# What's already referenced in tests
tested_scn, tested_req = set(), set()
for f in pathlib.Path("tests").rglob("*.py"):
    text = f.read_text()
    tested_scn |= set(re.findall(r"SCN-\d+", text))
    tested_req |= set(re.findall(r"REQ-SHORT-\d+", text))

print("=== Untested scenarios ===")
for sid, name in sorted(declared_scn.items()):
    status = "OK" if sid in tested_scn else "MISSING"
    print(f"  [{status}] {sid}: {name}")

print("\n=== REQ-IDs with no test reference ===")
missing_req = sorted(declared_req.keys() - tested_req)
print(missing_req if missing_req else "  none")
EOF
```

### 3. Read the testing conventions

```bash
cat CLAUDE.md | grep -A 20 "Testing conventions"
cat tests/conftest.py
```

Read the conventions from CLAUDE.md and the existing conftest carefully.
Key rules to follow when generating:
- Fixture: use `client` (TestClient) — never instantiate it yourself
- State isolation: `reset_state` is autouse — do not call `store.clear()` manually
- Naming: `test_<scn_id_lower>_<behaviour_slug>` for scenario tests;
  `test_<endpoint>_<case>` for API unit tests
- Trace comment: first line of each function body is `# SCN-XXX: <name>` or
  `# REQ-SHORT-XXX: <description>`
- No `import requests` — only `TestClient`
- Assert exact HTTP status codes and response field names from the spec

### 4. Read the spec for assertion values

```bash
cat specs/url-shortener.yaml
```

For each test to generate, extract from the spec:
- Expected HTTP status code for success and each error path
- Required response body fields and their types
- Rate limit values (for 429 tests)
- Expiry behaviour (for 410 tests)

### 5. Generate test functions

For each untested scenario or uncovered behaviour, produce a pytest function.
Append to `tests/test_scenarios.py` for scenario-mapped tests, or
`tests/test_api.py` for endpoint unit tests.

**Template:**
```python
def test_<scn_id_lower>_<slug>(client):
    # SCN-XXX: <scenario name from spec>
    # REQ-SHORT-XXX: <requirement being exercised>

    # Given
    <setup — use client.post / client.get, no direct store access>

    # When
    response = client.<method>("<path>", ...)

    # Then
    assert response.status_code == <exact code from spec>
    data = response.json()
    assert "<required_field>" in data
    assert data["<field>"] == <expected_value>
```

Do **not** modify any existing test function. Only append.

### 6. Run the suite and report coverage

```bash
# Run new tests in isolation first
pytest tests/test_scenarios.py -v --tb=short

# Then confirm full suite still green
pytest -q --tb=short
```

---

## Expected output

```
## /test-gen results

### Coverage gap analysis
- Untested scenarios: [SCN-XXX, ...]  (or "none")
- REQ-IDs with no test:  [REQ-SHORT-XXX, ...]  (or "none")

### Generated
- N new test functions appended to tests/test_scenarios.py
  - test_scn_xxx_<slug>  →  SCN-XXX
  - ...

### Test suite
- Before: N passed
- After:  N+M passed, 0 failed
- Coverage change: +M tests
```

If no gaps are found: report "All scenarios and REQ-IDs have test coverage —
nothing to generate." and stop without modifying any file.

---

## Safety checks

| Check | On failure |
|-------|-----------|
| New test fails immediately after generation | Debug and fix before reporting complete |
| Existing test broken by appended code | Revert the append and investigate |
| Generated test uses `requests` or direct `store` access | Rewrite to use `TestClient` |
| Generated test missing REQ-ID or SCN-ID trace comment | Add trace comment before appending |
| Test function name collides with existing function | Choose a more specific slug |

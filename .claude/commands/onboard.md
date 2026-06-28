# /onboard — Architecture Summary for New Team Members

## Purpose

Generate a complete orientation package for someone joining this project:
architecture summary, key file map, data flow walkthrough, conventions
cheatsheet, and a verified green baseline. Everything a new developer needs
to make a confident first contribution.

## When to use

- First day working on this codebase
- Returning to the project after a long break
- Onboarding a new team member asynchronously
- Any time you want a current, auto-generated picture of the project

---

## Steps Claude should execute

### 1. Read the authoritative sources

```bash
cat CLAUDE.md
cat specs/url-shortener.yaml
cat docs/implementation-plan.md
```

These three files are the ground truth. Read them fully before generating
anything — the onboarding summary must accurately reflect what they say, not
general FastAPI knowledge.

### 2. Generate the architecture summary

Inspect the source files and produce a prose description of the system:

```bash
# Read every src/ file in full
cat src/main.py
cat src/models.py
cat src/router.py
cat src/store.py
cat src/limiter.py
```

From this, produce a written summary covering:

- **What the service does** (one paragraph, plain English)
- **Request lifecycle** — trace a `POST /shorten` request from entry point
  through validation → store write → response, naming the exact functions
  and files involved at each step
- **Data model** — describe `_store`, `_url_index`, and `_referrers` and
  explain why three separate dicts are used instead of one
- **In-memory storage trade-offs** — what restarting the process means,
  why this was the right choice for the spec, what would need to change
  to make it persistent

### 3. Print the key file map

```bash
find . -type f -name "*.py" | grep -v ".git\|__pycache__\|.venv" | sort
find . -name "*.yaml" -o -name "*.md" | grep -v ".git\|__pycache__\|.venv" | sort
```

Produce a table with three columns: **File**, **Purpose**, **Read first if you
want to understand...**

| File | Purpose | Read when you want to understand... |
|------|---------|-------------------------------------|
| `specs/url-shortener.yaml` | Authoritative requirements + Gherkin | What the service is *supposed* to do |
| `src/main.py` | FastAPI app wiring | How the app starts and which router is mounted |
| `src/models.py` | Pydantic request/response models | Validation rules, SSRF prevention, field shapes |
| `src/router.py` | HTTP endpoints (5 routes) | What each endpoint does and which errors it raises |
| `src/store.py` | In-memory link store | Where data lives and how idempotency works |
| `src/limiter.py` | Per-IP rate limiter | How the 60 req/60s window is enforced |
| `tests/conftest.py` | Shared test fixtures | Why state resets between tests |
| `tests/test_scenarios.py` | Gherkin scenario tests | How requirements map to running assertions |
| `tests/test_api.py` | Endpoint integration tests | Fine-grained HTTP contract tests |
| `CLAUDE.md` | Contribution rules + conventions | How to contribute correctly |
| `docs/traceability-matrix.md` | REQ-ID → code → test mapping | Whether a requirement is fully covered |

### 4. Show the conventions cheatsheet

Extract the rules from CLAUDE.md and format them as a quick-reference card:

```bash
cat CLAUDE.md | grep -A 5 "Contribution rules" -A 5 "Testing conventions"
```

Produce this summary (do not just paste CLAUDE.md verbatim — synthesise it):

```
## Conventions cheatsheet

Source code
  - Every function in src/ that implements a requirement must have a
    # REQ-SHORT-XXX comment on or above it
  - No direct database/store imports in tests — use TestClient only

Tests
  - Fixture: use `client` (TestClient); `reset_state` resets state automatically
  - Naming: test_<scn_id_lower>_<slug>  or  test_<endpoint>_<case>
  - Trace: first body line is # SCN-XXX or # REQ-SHORT-XXX
  - Never import `requests` — always use FastAPI TestClient

Commits
  - Format: <type>(<scope>): <description>
  - Types: feat | fix | test | refactor | docs | chore
  - Body: one bullet per REQ-ID addressed

Workflow
  - /review before every PR
  - /test-gen after every new scenario
  - /commit instead of git commit directly
  - /ship to go from staged → PR in one command
```

### 5. Run the test suite to establish a verified baseline

```bash
pytest -v --tb=short
```

Report the result. If the suite is green, include this in the output:

> "The test suite is green on a clean checkout. This is your baseline.
> If tests fail after your changes, you introduced a regression."

If the suite is red on a clean checkout, report which tests fail and note that
this must be fixed before any contribution work begins.

### 6. Show how the service runs

```bash
# Show the endpoints
python3 - <<'EOF'
import yaml, pathlib
spec = yaml.safe_load(pathlib.Path("specs/url-shortener.yaml").read_text())
print("Endpoints defined in spec:")
for e in spec.get("api_endpoints", []):
    print(f"  {e['method']:<8} {e['path']}")
print()
print("Requirements (summary):")
for r in spec.get("requirements", []):
    print(f"  {r['id']}: {r['description'][:70]}")
EOF
```

Then print the startup command and three example curl calls a new developer
can run immediately to see the service in action.

### 7. Explain the governance pipeline

Read the current state of hooks and commands:

```bash
ls -1 .claude/hooks/
ls -1 .claude/commands/
cat .claude/settings.json
```

Produce a two-part summary:

**Hooks (automatic — fire on every relevant tool call):**

| Hook | Fires on | What it prevents |
|------|----------|-----------------|
| `validate-bash.py` | Every Bash call | Destructive shell commands |
| `check-secrets.py` | Every Write/Edit | Credentials written to files |
| `scope-guard.sh` | Every Write/Edit | Writes outside project root |
| `audit-log.sh` | Every tool call | Nothing — records for audit trail |

**Commands (on-demand — type `/name` to invoke):**

| Command | What it does | When to use it |
|---------|-------------|----------------|
| `/review` | AI review of staged changes vs CLAUDE.md | Before every PR |
| `/test-gen` | Generate tests for untested scenarios | After new REQ-ID or scenario |
| `/commit` | Smart commit message from diff + safety checks | Instead of `git commit` |
| `/ship` | review → test-gen → commit → PR in one command | When feature is complete |
| `/onboard` | This document | First day or after long break |

---

## Expected output

A single self-contained Markdown document structured as:

```
# Project Onboarding — URL Shortener Service
Generated: <date>

## 1. What this service does
...

## 2. Architecture summary
...

## 3. Request lifecycle: POST /shorten
...

## 4. Key file map
<table>

## 5. Conventions cheatsheet
...

## 6. Baseline test suite
N tests passing. (or: X failures — see below)

## 7. Running the service
...

## 8. Governance pipeline
...

## 9. Your first contribution
Step-by-step walkthrough for making and shipping a small change.
```

---

## Safety checks

| Check | On failure |
|-------|-----------|
| `specs/url-shortener.yaml` not found | Stop — ask user to confirm working directory |
| `CLAUDE.md` not found | Generate from source files but warn that CLAUDE.md is missing |
| Test suite red on clean checkout | Report failures prominently; continue generating onboarding doc but mark baseline as broken |
| `src/` directory empty | Stop — codebase is not in expected state |

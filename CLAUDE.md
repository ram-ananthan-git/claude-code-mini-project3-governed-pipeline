# CLAUDE.md — URL Shortener Service

This file is the authoritative guide for contributing to this project using
Claude Code. Read it before making any changes. Every rule here is enforced
by a hook, a command gate, or a code review check.

---

## Quick start

```bash
pip install fastapi uvicorn httpx pyyaml pytest
uvicorn src.main:app --reload --port 8000   # dev server → http://localhost:8000/docs
pytest -q                                   # must be green before any commit
```

**Stack:** Python 3.12 · FastAPI · Pydantic v2 · pytest · httpx  
**Storage:** in-memory dicts (no database)  
**Test suite:** 56 tests · 100% REQ-ID coverage · < 3 s runtime

---

## Repository layout

```
specs/
  url-shortener.yaml        authoritative spec — REQ-IDs, Gherkin scenarios, API contracts
src/
  main.py                   FastAPI app entry point; mounts router
  models.py                 Pydantic request/response models + SSRF/validation rules
  router.py                 5 HTTP endpoints; raises only errors defined in spec
  store.py                  in-memory link store (_store, _url_index, _referrers)
  limiter.py                per-IP sliding-window rate limiter (60 req / 60 s)
tests/
  conftest.py               autouse reset_state fixture — clears store + limiter
  test_api.py               endpoint integration tests
  test_scenarios.py         Gherkin scenario tests (SCN-001 → SCN-011)
prompts/                    LLM prompt templates: spec-writer, architect, code-reviewer, test-generator
docs/
  implementation-plan.md    architecture decisions derived from spec
  traceability-matrix.md    REQ-ID → source file → test function map
  workflow-map.md           development workflow with timing and pain points
  leverage-analysis.md      automation ROI scoring for each workflow step
  roi-report.md             before/after time and error-rate measurements
  governance-playbook.md    hook reference, incident response, anti-patterns
.claude/
  settings.json             permissions allow/deny list + all hook configuration
  commands/                 slash commands invoked with /name
  hooks/                    hook scripts referenced by settings.json
  audit/                    append-only logs: audit.jsonl, prompts.jsonl, sessions.jsonl
CLAUDE.md                   this file — ground truth for contributions
```

---

## Team workflow rules

Every change follows this sequence. Do not skip steps.

```
1. Read the relevant REQ-IDs in specs/url-shortener.yaml
2. Implement in src/ — annotate every changed function with # REQ-SHORT-XXX
3. Run /test-gen if a new scenario or requirement was added
4. Run pytest -q — must be green before proceeding
5. Run /review — address all BLOCKER and MAJOR findings before continuing
6. Run /commit — runs safety checks and generates the commit message
7. Run /ship when ready to tag a release or open a PR
```

**Non-negotiable rules:**

- Never commit directly to `main`. Work on a feature branch.
- Never use `git commit` directly. Use `/commit` — it runs the secret scan and
  REQ-ID check before writing the commit.
- Never skip `/review` before opening a PR. A clean `/review` output is the
  minimum bar for requesting peer review.
- Never approve a PR that has a BLOCKER finding from `/review`.
- Never push `--force` to any branch that has an open PR.
- Do not leave `TODO` or `FIXME` comments in code that is being committed.

---

## Architecture conventions

### Spec is the source of truth

`specs/url-shortener.yaml` is the authoritative contract. Before changing any
behaviour in `src/`, check whether a REQ-ID covers it. If it does not, update
the spec first.

Changes to the spec require:
1. Adding or updating the REQ-ID entry under `requirements:`
2. Adding or updating the Gherkin scenario under `scenarios:`
3. Running `/test-gen` to generate the corresponding test
4. Updating `docs/traceability-matrix.md`

### Source file responsibilities

| File | Owns | Must not |
|------|------|---------|
| `main.py` | App wiring, lifespan | Contain business logic |
| `models.py` | Pydantic shapes, input validation, SSRF prevention | Reach into store or router |
| `router.py` | HTTP verbs, status codes, request/response mapping | Contain data-access logic |
| `store.py` | All state mutation and reads | Import from router |
| `limiter.py` | Rate-limit state and enforcement | Import from store or router |

Any import that crosses these boundaries is an architecture violation and will
be flagged as a MAJOR finding by `/review`.

### In-memory storage model

Three module-level dicts in `store.py`:

- `_store` — `short_code → LinkRecord` (primary index)
- `_url_index` — `original_url → short_code` (duplicate detection)
- `_referrers` — `short_code → Counter` (analytics)

Tests must not access these dicts directly. Use the HTTP API via `TestClient`.
State is reset between tests by the autouse `reset_state` fixture in `conftest.py`.

### Error contracts

Every error response must match exactly what the spec defines. Do not invent
new status codes or error shapes.

| Code | Meaning |
|------|---------|
| 201 | Link created |
| 204 | Link deleted |
| 307 | Redirect to original URL |
| 400 | Validation failure |
| 404 | Short code not found |
| 409 | Duplicate URL (idempotency conflict) |
| 410 | Link expired |
| 422 | Unprocessable entity (Pydantic) |
| 429 | Rate limit exceeded — must include `Retry-After` header |

---

## Testing standards

### Coverage requirements

- Every REQ-ID in `specs/url-shortener.yaml` must appear in at least one test
- Every Gherkin scenario (SCN-XXX) must have a corresponding test function
- Every error status code (404, 409, 410, 422, 429) must be exercised
- Happy path and at least one failure path per endpoint

### Test file conventions

**Fixtures**
- Use the `client` fixture (FastAPI `TestClient`) for all HTTP calls
- `reset_state` is autouse — do not call `store.clear()` or `limiter.clear()` manually
- Do not import `store`, `limiter`, or any `src/` module directly in test bodies

**Naming**
- Scenario tests: `test_scn_<id_lower>_<behaviour_slug>`
  — e.g. `test_scn_001_shorten_valid_url`
- API unit tests: `test_<endpoint>_<case>`
  — e.g. `test_shorten_duplicate_returns_409`

**Trace comments**
- First line of every test body: `# SCN-XXX: <scenario name>` or
  `# REQ-SHORT-XXX: <requirement description>`
- This is what populates `docs/traceability-matrix.md`

**HTTP client**
- Always use `TestClient` from `fastapi.testclient`
- Never import `requests` in test files — flagged as a MAJOR finding by `/review`

**Assertions**
- Assert exact HTTP status codes — `assert response.status_code == 307`, not `>= 300`
- Assert required response fields by name — `assert "short_code" in data`
- Assert error shapes match the spec — `assert "detail" in data` on all 4xx responses

### Running tests

```bash
pytest -q                          # full suite, quiet output
pytest -v --tb=short               # verbose with short tracebacks
pytest tests/test_scenarios.py -v  # scenario tests only
pytest -k "scn_003" -v             # single scenario by name fragment
```

The full suite must pass in under 10 seconds on any machine with the
dependencies installed.

---

## Security rules

These are hard requirements. Each is enforced by a hook or deny-list entry.

### No real credentials in the repository

The `check-secrets.py` PreToolUse hook scans every `Write` and `Edit` call
before the file is saved. It blocks writes containing:

- Cloud provider keys (AWS, GCP, Azure formats)
- AI provider keys (Anthropic, OpenAI, and equivalents)
- Source control tokens (GitHub, GitLab, Bitbucket)
- Communication tokens (Slack bot/user/webhook tokens)
- Payment tokens (Stripe live and test secret keys)
- Private key PEM blocks (RSA, EC, OPENSSH)
- JWT tokens (three-segment base64url strings)
- Database URLs with embedded username:password credentials
- Assignments of the form `password = "..."` with any non-trivial value

If you need to show a credential format in documentation, use a placeholder
that is clearly not a real value — something like `YOUR-KEY-HERE` or a
repeated character string with no vendor prefix.

### SSRF prevention

`src/models.py` blocks URLs that target private address ranges (RFC 1918,
loopback, link-local). Do not remove or loosen the SSRF validation in
`ShortenRequest`. Do not add bypass flags.

### Input validation location

All input validation belongs in `models.py`. Never validate in `router.py`.
Pydantic raises 422 automatically for schema violations; custom validators
are only for domain rules (SSRF, scheme allowlist, max length).

### Allowed URL schemes

Only `http` and `https` are accepted. Do not add new schemes without a
corresponding spec change (REQ-SHORT-XXX + scenario).

### Rate limiting

The limiter enforces 60 requests per 60-second window per IP, with a
`Retry-After` header on 429 responses. Do not raise or remove this limit
without a spec change.

### Dependency hygiene

Before adding a dependency: verify it is actively maintained, has no known
critical CVEs, and cannot be replaced with stdlib. Pin versions in
`requirements.txt`.

---

## Commit and PR standards

### Commit format

All commits must follow [Conventional Commits](https://www.conventionalcommits.org):

```
<type>(<scope>): <imperative description — 72 chars max>

- REQ-SHORT-XXX: what this commit addresses
- REQ-SHORT-YYY: what this commit addresses

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**Types:**

| Type | When to use |
|------|-------------|
| `feat` | New behaviour visible to a caller |
| `fix` | Corrects wrong behaviour traced to a failing test or REQ-ID |
| `test` | Test additions or changes only |
| `refactor` | Internal restructure, no behaviour change, same tests pass |
| `docs` | Documentation, specs, prompts only |
| `chore` | Hooks, settings, dependencies, CI |

**Scopes:** `router` · `store` · `models` · `limiter` · `tests` · `hooks` · `spec` · `docs` · `*`

Use `/commit` instead of writing messages by hand. It reads the diff, extracts
REQ-IDs from changed files, and generates a conformant message.

### What makes a good commit

- One logical change per commit — not "fix everything"
- REQ-ID in body for every `src/` change
- Tests included in the same commit as the implementation
- No `TODO` or `FIXME` left in committed code
- `git show --stat HEAD` shows only files related to the stated change

### PR standards

Every PR must include:
- Title following `type(scope): description` format
- Body listing which REQ-IDs are addressed
- A test plan checklist (which `pytest` commands to run)
- A passing `/review` output (zero BLOCKERs, zero MAJORs)

Use `/ship` to automate the full flow — it generates the PR body and runs
`gh pr create`.

**Reviewer checklist:**
- [ ] Changes match `specs/url-shortener.yaml`
- [ ] REQ-ID trace comments present in all changed `src/` files
- [ ] No `requests` import in test files
- [ ] No undeclared status codes or error shapes
- [ ] `pytest -q` passes locally
- [ ] No credentials in diff (verify `check-secrets.py` didn't warn)

---

## Hook and audit expectations

### Active hooks

Six scripts run automatically — they cannot be disabled for a session.

| Script | Event | Fires on | Effect |
|--------|-------|----------|--------|
| `validate-bash.py` | PreToolUse | Bash | Blocks 21+ dangerous command patterns |
| `check-secrets.py` | PreToolUse | Write, Edit | Blocks 25+ credential patterns |
| `scope-guard.sh` | PreToolUse | Write, Edit | Blocks writes to protected dirs and outside project root |
| `audit-log.sh` | PostToolUse | every tool | Appends JSON record to `audit.jsonl` |
| `log-prompt.sh` | UserPromptSubmit | every message | Appends prompt to `prompts.jsonl` |
| `session-summary.sh` | Stop | session end | Writes tally to `sessions.jsonl`, prints to terminal |

### What is logged

**`audit.jsonl`** — one record per tool call:
```
timestamp, session_id, tool, file_path, input_summary, outcome, hook_decision
```

**`prompts.jsonl`** — one record per Bash command and per user prompt:
```
timestamp, session_id, type ("bash_command" | "user_prompt"), command/prompt, outcome
```

**`sessions.jsonl`** — one record per session end:
```
timestamp, session_id, total_tool_calls, blocked_calls, bash_commands,
files_written, unique_files, stop_reason
```

Audit files are append-only and excluded from secret scanning. Do not delete,
truncate, or commit them to the repository (add them to `.gitignore` if not
already present).

### Responding to a hook block

| Block source | What to do |
|---|---|
| `check-secrets.py` | Stop. Find and remove the real credential. Use a clearly-fake placeholder. |
| `validate-bash.py` | Read the block reason. If the pattern is too broad, narrow the regex — do not rephrase the command to evade the pattern. |
| `scope-guard.sh` | Confirm you are targeting the right file. To allow a new directory, add it to `ALLOWED_PREFIXES` in `scope-guard.sh` with a comment. |

### Reading the audit log

```bash
# Last 10 tool calls
tail -10 .claude/audit/audit.jsonl | python3 -m json.tool

# All blocked operations
grep '"hook_decision": "blocked"' .claude/audit/audit.jsonl

# Session summaries
cat .claude/audit/sessions.jsonl | python3 -m json.tool

# Recent Bash commands
grep '"type": "bash_command"' .claude/audit/prompts.jsonl | tail -20
```

---

## Slash command usage

Five commands live in `.claude/commands/`. Invoke with `/name` in the Claude
Code prompt. Each is a Markdown file that Claude reads and executes step by step.

### `/review` — run before every PR

Loads `CLAUDE.md` as the review standard, captures the staged diff, runs
mechanical checks (secrets, REQ-ID traces, `requests` import), executes the
test suite, then reasons about spec compliance, correctness, quality, and
test coverage.

**When:** after staging changes, before `/commit` or opening a PR.  
**Output:** BLOCKER / MAJOR / MINOR findings + verdict (APPROVE / REQUEST CHANGES / BLOCKED).  
**Rule:** do not open a PR with a REQUEST CHANGES or BLOCKED verdict outstanding.

### `/test-gen` — run after every new scenario or REQ-ID

Reads the spec, diffs against existing test coverage, generates conformant
pytest functions for every untested scenario, appends them to
`tests/test_scenarios.py`, and runs the full suite.

**When:** after adding a Gherkin scenario, or when `/review` flags a MAJOR
test-coverage finding.  
**Output:** "N new tests added, all N passed" — or "no gaps found."  
**Rule:** never merge a new REQ-ID without a corresponding test.

### `/commit` — use instead of `git commit`

Reads the staged diff, scans for secrets, checks REQ-ID traces in changed
`src/` files, requires a green test suite, generates a conventional-commit
message with REQ-ID references, then executes the commit.

**When:** whenever you want to commit staged changes.  
**Output:** proposed message printed before execution, then `git show --stat HEAD`.  
**Rule:** never use `git commit` directly on `src/` changes.

### `/ship` — staged changes to open PR in one command

Runs four sequential gates: review → test-gen → commit → `gh pr create`.
Fails at the first gate that does not pass and reports which gate and why.

**When:** feature is complete and ready for review or merge.  
**Output:** four gate results (PASS / FAIL), commit SHA, PR URL.  
**Rule:** all four gates must pass — do not manually skip a failing gate.

### `/onboard` — orientation for new contributors

Reads `CLAUDE.md`, the spec, and all `src/` files, then generates an
orientation document: architecture summary, request lifecycle, key file map,
conventions cheatsheet, and a verified baseline test run.

**When:** first session on the project, or after a long break.  
**Output:** self-contained Markdown document covering architecture, data model,
governance pipeline, and first-contribution walkthrough.

---

## Common one-liners

```bash
# Check which REQ-IDs lack test coverage
python3 -c "
import yaml, pathlib, re
spec = yaml.safe_load(pathlib.Path('specs/url-shortener.yaml').read_text())
declared = {r['id'] for r in spec.get('requirements', [])}
tested = set()
for f in pathlib.Path('tests').rglob('*.py'):
    tested |= set(re.findall(r'REQ-SHORT-\d+', f.read_text()))
print('Missing:', sorted(declared - tested) or 'none')
"

# Run scenario tests only
pytest tests/test_scenarios.py -v

# Tail the audit log
tail -10 .claude/audit/audit.jsonl | python3 -m json.tool

# Verify the spec parses cleanly
python3 -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('specs/url-shortener.yaml').read_text()); print('spec OK')"
```

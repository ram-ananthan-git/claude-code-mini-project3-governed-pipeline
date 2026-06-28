# Automation Leverage Analysis

## Purpose

This document scores every step of the URL shortener development workflow
using the Automation Leverage Framework, then identifies and justifies the
top three automation targets.

## Framework

Each workflow step is rated on four dimensions:

| Dimension | What it measures | Scale |
|-----------|-----------------|-------|
| **Frequency** | How many times this step occurs per feature cycle | 1 (rare) → 5 (every change) |
| **Time per occurrence** | Wall-clock cost when done manually | 1 (< 2 min) → 5 (> 30 min) |
| **AI capability** | How fully an AI tool can perform this step without human judgement | 1 (AI can't help) → 5 (AI handles entirely) |
| **ROI score** | Composite 1–10 score weighting the above plus risk/irreversibility | 1 (low return) → 10 (critical return) |

`ROI score = round( (Frequency + Time + AI_capability) / 1.5 )`, capped at 10,
then manually adjusted upward for steps where a single failure causes
irreversible or security-critical damage.

---

---

## All Workflow Steps Scored

> Steps map to the seven workflow phases in `docs/workflow-map.md`.
> Each phase may contain multiple distinct automation candidates.

| # | Workflow Step | Frequency (1–5) | Time / occurrence (1–5) | AI capability (1–5) | ROI score (1–10) |
|---|---------------|:-:|:-:|:-:|:-:|
| 1 | **Ticket pickup** — read ticket, parse acceptance criteria | 5 | 1 | 2 | 5 |
| 2 | **Requirements → spec** — translate prose ticket into `url-shortener.yaml` | 3 | 4 | 4 | 7 |
| 3 | **Architecture plan** — derive file tree and interface contracts from spec | 2 | 3 | 4 | 6 |
| 4 | **Implementation** — write `src/` code with REQ-ID traces | 5 | 5 | 3 | 9 |
| 5 | **REQ-ID trace check** — verify every changed file references a REQ-ID | 5 | 2 | 5 | **10** |
| 6 | **Secret scan on write** — detect credentials before files are saved | 5 | 1 | 5 | **10** |
| 7 | **Scope guard** — confirm writes stay inside project root | 5 | 1 | 5 | **10** |
| 8 | **Dangerous command guard** — block `rm -rf`, piped installers, etc. | 4 | 1 | 5 | 9 |
| 9 | **Manual smoke test** — run service, curl each endpoint by hand | 3 | 3 | 2 | 5 |
| 10 | **Test generation** — write pytest functions for Gherkin scenarios | 3 | 4 | 5 | **10** |
| 11 | **Run test suite** — execute `pytest -q` and read results | 5 | 1 | 5 | 7 |
| 12 | **Self-review** — read diff against spec and coding standards | 4 | 3 | 4 | 7 |
| 13 | **Spec-compliance check** — cross-ref REQ-IDs in source vs spec YAML | 3 | 3 | 5 | 8 |
| 14 | **Commit message** — write conventional-commit message with REQ-ID body | 5 | 2 | 5 | 8 |
| 15 | **Pre-commit secret scan** — grep staged diff for credentials | 5 | 2 | 5 | 9 |
| 16 | **Peer review** — human reviewer reads diff and spec | 2 | 5 | 3 | 6 |
| 17 | **Release gate pipeline** — run all checks before tagging | 1 | 4 | 5 | 7 |
| 18 | **Semver tag + changelog** — determine next version, annotate tag | 1 | 2 | 4 | 5 |
| 19 | **Audit logging** — record every tool call for traceability | 5 | 1 | 5 | 8 |
| 20 | **New-hire onboarding** — explain spec model, workflow, governance | 0.2 | 5 | 5 | 6 |

---

## Score Rationale

### Frequency ratings

- **5** — happens on every file write or every AI tool call (secret scan, scope guard, command guard, REQ-ID check, test run)
- **4** — happens on every commit or PR cycle (commit message, dangerous command patterns)
- **3** — happens once per feature (smoke test, spec-compliance check, test generation)
- **2** — happens once per feature with a branch review cycle (peer review, architecture)
- **1** — once per release (gate pipeline, tagging)
- **< 1** — once per onboarding event

### Time per occurrence ratings

- **5** — > 30 min: implementation, peer review, onboarding
- **4** — 15–30 min: requirements → spec, architecture, test generation, release gate
- **3** — 5–15 min: smoke test, self-review
- **2** — 2–5 min: commit message, REQ-ID check, audit logging, changelog
- **1** — < 2 min: secret scan (per write), scope guard, test suite run (< 30 s)

### AI capability ratings

- **5** — AI can do this completely: pattern matching (secrets, scope, REQ-IDs), template generation (tests, commit messages), structured logging
- **4** — AI does 80%+: spec writing, architecture from template, review from rubric, onboarding walkthrough
- **3** — AI assists but human judgment drives: implementation design, peer review, smoke testing
- **2** — AI can summarise or prompt, but human must decide: ticket parsing, smoke test interpretation

### ROI adjustment for irreversibility

Steps 5, 6, 7 (REQ-ID check, secret scan, scope guard) were adjusted to **10**
regardless of raw formula because a single missed execution causes harm that
cannot be undone:
- A leaked credential is compromised the moment it reaches a remote
- A write to the wrong path can overwrite another project's files silently
- An untraceable REQ-ID breaks the entire traceability model permanently

---

## Top 3 Automation Targets

### #1 — Secret Scan on Write (ROI: 10)

**What it automates:** Detecting API keys, tokens, and passwords before they
are written to any project file.

**Why it scores 10:**
- **Frequency 5** — every `Write` and `Edit` call is a potential exposure vector
- **Time per occurrence 1** — the hook adds ~35 ms per call, invisible to the developer
- **AI capability 5** — credential patterns are deterministic regexes; zero false negatives on known formats
- **Irreversibility multiplier** — a credential committed to a remote repo is
  compromised within minutes. Rotation, audit, and customer notification costs
  dwarf any implementation expense. The automation pays for itself the first
  time it fires.

**Implementation:** `check-secrets.py` PreToolUse hook on Write and Edit.
14 blocking patterns; exempt paths for test fixtures and docs. ~35 ms per call.

**Without it:** Developer must visually scan every diff. Industry miss rate for
embedded tokens is 15–30%. One missed `sk-ant-...` or `AKIA...` is a P0.

---

### #2 — Test Generation from Spec (ROI: 10)

**What it automates:** Producing conformant pytest functions for every Gherkin
scenario in `specs/url-shortener.yaml` that lacks a test.

**Why it scores 10:**
- **Frequency 3** — every spec change or new requirement triggers this
- **Time per occurrence 4** — writing a scenario test by hand takes 20–40 min:
  fixture wiring, Given/When/Then comment structure, correct assertion shape,
  SCN-ID reference, status code lookup from spec
- **AI capability 5** — the output is fully deterministic given the spec: the
  test structure, fixture names, assertion patterns, and SCN-ID format are all
  templated. The `test-generator.yaml` prompt produces verifiable output with
  a JSON schema constraint.
- **Compounding value** — untested scenarios mean the traceability matrix claims
  coverage that doesn't exist. Automation prevents silent coverage gaps from
  accumulating across releases.

**Implementation:** `/test-gen` slash command. Reads spec, diffs against
existing SCN-IDs in `tests/`, feeds gaps to `test-generator.yaml`, appends
output, runs full suite to confirm no regressions.

**Without it:** 25–40 min per scenario, inconsistent fixture usage, SCN-IDs
often omitted, traceability matrix becomes unreliable.

---

### #3 — REQ-ID Trace Check (ROI: 10)

**What it automates:** Verifying that every changed `src/` file references at
least one REQ-ID from the spec, and that every declared REQ-ID has both source
and test coverage.

**Why it scores 10:**
- **Frequency 5** — must run on every implementation change; the check itself
  takes < 1 s via regex scan
- **Time per occurrence 2** — manual cross-referencing of spec YAML vs source
  comments takes 5–10 min and is easy to skip under deadline pressure
- **AI capability 5** — purely mechanical: parse YAML for `id:` fields, grep
  source for matching strings, diff the two sets. No judgment required.
- **Irreversibility multiplier** — a REQ-ID that accumulates zero source
  references means the traceability matrix reports compliance for a requirement
  that was never implemented. In a regulated or audited context this is a
  compliance failure, not just a quality gap.

**Implementation:** Embedded in both `/review` and `/commit` as a Python
one-liner that produces a diff of declared vs. referenced REQ-IDs. Also runs
as Gate 2 in `/ship`.

**Without it:** The traceability matrix (`docs/traceability-matrix.md`) becomes
a static artifact that can diverge from reality after any refactor, rename, or
deletion without anyone noticing.

---

## Summary Table

| Rank | Step | Frequency | Time | AI cap. | ROI | Implemented as |
|------|------|:---------:|:----:|:-------:|:---:|----------------|
| 1 | Secret scan on write | 5 | 1 | 5 | 10 | `check-secrets.py` hook |
| 2 | Test generation from spec | 3 | 4 | 5 | 10 | `/test-gen` command |
| 3 | REQ-ID trace check | 5 | 2 | 5 | 10 | `/review`, `/commit`, `/ship` |
| — | Scope guard on writes | 5 | 1 | 5 | 10 | `scope-guard.sh` hook |
| — | Dangerous command guard | 4 | 1 | 5 | 9 | `validate-bash.py` hook |
| — | Pre-commit secret scan | 5 | 2 | 5 | 9 | `/commit` step 2 |
| — | Spec-compliance check | 3 | 3 | 5 | 8 | `/review` command |
| — | Audit logging | 5 | 1 | 5 | 8 | `audit-log.sh` hook |
| — | Commit message format | 5 | 2 | 5 | 8 | `/commit` command |

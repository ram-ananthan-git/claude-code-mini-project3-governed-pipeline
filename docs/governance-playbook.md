# Governance Playbook — Governed AI Pipeline

## Purpose

This playbook defines how the governed Claude Code pipeline is adopted,
operated, and extended. It covers the six-week rollout sequence, risk
controls, ownership assignments, success metrics, and ongoing maintenance
procedures.

---

## 6-Week Rollout Plan

### Week 1 — Pilot Setup

**Goal:** Get one developer running the full pipeline end-to-end in a clean
environment. Validate that all hooks fire, commands execute, and audit logs
are written before the team is involved.

**Deliverables**

| # | Task | Owner | Done when |
|---|------|-------|-----------|
| 1.1 | Install dependencies: `pip install fastapi uvicorn httpx pyyaml pytest` | Pipeline lead | `pytest -q` passes |
| 1.2 | Create `.claude/settings.json` with allow/deny list and 6 hook entries | Pipeline lead | `python3 -m json.tool settings.json` clean |
| 1.3 | Implement all 6 hooks (`validate-bash.py`, `check-secrets.py`, `scope-guard.sh`, `audit-log.sh`, `log-prompt.sh`, `session-summary.sh`) | Pipeline lead | `bash -n` and `python3 -m py_compile` pass for each |
| 1.4 | Create all 5 slash commands under `.claude/commands/` | Pipeline lead | Each file non-empty and referenced in `CLAUDE.md` |
| 1.5 | Bootstrap `.claude/audit/` directory with empty `audit.jsonl` and `prompts.jsonl` | Pipeline lead | Files exist; `audit-log.sh` appends on first tool call |
| 1.6 | Write or update `CLAUDE.md` to cover all 7 required sections | Pipeline lead | Document reviewed and checked in |
| 1.7 | Run one complete feature cycle (small change → `/review` → `/commit`) and verify audit log populated | Pipeline lead | Audit log shows ≥ 5 entries with correct schema |

**Risks in Week 1**

- Hook bootstrap deadlock: `settings.json` references hook files that do not
  yet exist. Mitigation: create empty placeholder files (`touch`) before
  writing `settings.json`, then replace placeholders with real implementations.
- `check-secrets.py` may block writes to its own hook file if the file
  contains credential-like test strings. Mitigation: use non-vendor placeholder
  strings in all hook source and documentation.

**Exit criteria:** Pipeline lead can demonstrate a blocked `rm -rf /` command,
a blocked secret write, and a clean `/commit` output on a real diff.

---

### Week 2 — Workflow Mapping

**Goal:** Document the team's actual development workflow before automation
changes it. Establish the before-state baseline that ROI measurements will
compare against.

**Deliverables**

| # | Task | Owner | Done when |
|---|------|-------|-----------|
| 2.1 | Create `docs/workflow-map.md` with Mermaid flowchart covering ticket pickup → deploy | Pipeline lead | 13+ steps mapped; time, tools, pain points per step |
| 2.2 | Conduct 30-min observation sessions with 2–3 developers doing live feature work | Pipeline lead | Notes captured; per-step timing recorded |
| 2.3 | Create `docs/leverage-analysis.md` scoring every step on Frequency, Time, AI capability, ROI | Pipeline lead | 20-row scoring table complete; top 3 targets justified |
| 2.4 | Identify which workflow steps the pipeline already automates (from Week 1) | Pipeline lead | Gap list produced: automated vs. not-yet-automated |
| 2.5 | Establish time-tracking baseline: log actual minutes spent on each step for 3 features this week | All pilot participants | Baseline spreadsheet with ≥ 3 data points per step |
| 2.6 | Circulate workflow map to the team; collect feedback on missing steps or incorrect timings | Pipeline lead | ≥ 2 team members confirm the map is accurate |

**Risks in Week 2**

- Developers underestimate time spent on mechanical tasks (review, commit
  message). Mitigation: use screen-recording review rather than self-report.
- Workflow map becomes stale immediately after automation ships. Mitigation:
  mark the map with a "baseline date" header and re-survey after Week 6.

**Exit criteria:** `docs/workflow-map.md` and `docs/leverage-analysis.md` are
checked in. Baseline time measurements exist for ≥ 3 features.

---

### Week 3 — Slash Command Rollout

**Goal:** Get the full team using the five slash commands. Each developer
runs at least one complete `/review` → `/commit` cycle and one `/ship`.

**Deliverables**

| # | Task | Owner | Done when |
|---|------|-------|-----------|
| 3.1 | Run `/onboard` with each new team member in a 20-min pairing session | Pipeline lead | Each developer can describe the three-dict storage model and five endpoint contracts |
| 3.2 | Each developer uses `/test-gen` on their current branch | Individual developers | At least one new test generated per developer |
| 3.3 | Each developer uses `/review` before opening their next PR | Individual developers | Zero PRs merged this week without a `/review` run |
| 3.4 | Each developer uses `/commit` for every commit this week | Individual developers | All commits this week are conventional-commit-format |
| 3.5 | One developer runs `/ship` end-to-end and demos the four-gate output to the team | Volunteer | Demo completed; questions captured in a shared doc |
| 3.6 | Collect friction reports: which commands were slow, unclear, or produced wrong output | All developers | Written report with ≥ 3 concrete improvement suggestions |
| 3.7 | Update command files in `.claude/commands/` based on friction reports | Pipeline lead | Updated commands checked in; changes noted in `CLAUDE.md` |

**Risks in Week 3**

- `/test-gen` generates tests that fail because the spec has errors. Mitigation:
  validate `specs/url-shortener.yaml` with a YAML linter before test-gen runs.
- `/review` is slow (> 60 s) because it reads all changed files. Mitigation:
  limit context to `git diff --staged` output rather than full file contents
  for large files.
- Developers skip `/commit` under deadline pressure. Mitigation: add a
  pre-push check (Week 4 hook) that warns if the last commit message is not
  conventional-commit format.

**Exit criteria:** All five commands used by ≥ 80% of the team at least once.
Friction report captured.

---

### Week 4 — Hooks and Audit Logging

**Goal:** Verify that all six hooks are active for every team member, that
blocked operations are handled correctly, and that the audit trail is
populated and queryable.

**Deliverables**

| # | Task | Owner | Done when |
|---|------|-------|-----------|
| 4.1 | Confirm each team member's Claude Code session loads `settings.json` (hooks fire on their machine) | Each developer + pipeline lead | Every developer can show a blocked command or blocked write from their own `audit.jsonl` |
| 4.2 | Run hook validation suite: echo test payloads to each hook and confirm correct output | Pipeline lead | All 6 hooks pass syntax check and produce expected `{"decision": ...}` output |
| 4.3 | Review `audit.jsonl` for the week: count blocked operations by hook and by developer | Pipeline lead | Weekly blocked-ops summary produced |
| 4.4 | Identify any false positives (legitimate commands blocked by `validate-bash.py` or `check-secrets.py`) | All developers | False-positive list captured; hook rules tuned |
| 4.5 | Tune hooks based on false positives: narrow regex patterns, add exempt paths where appropriate | Pipeline lead | Tuned hooks checked in; no regressions on the test suite |
| 4.6 | Document the audit log schema and query recipes in `CLAUDE.md` | Pipeline lead | Section 6 of `CLAUDE.md` covers `audit.jsonl`, `prompts.jsonl`, `sessions.jsonl` |
| 4.7 | Set up log rotation schedule (weekly archive of `audit.jsonl`) | Pipeline lead | `audit-YYYYMMDD.jsonl` archive created; documented in playbook |

**Risks in Week 4**

- `audit-log.sh` fails silently on some machines due to `jq` version
  differences or missing `python3` in PATH. Mitigation: `audit-log.sh` uses
  only stdlib Python; verify `python3 --version` ≥ 3.9 on every machine.
- Hook stdin consumption bug: Python heredoc inside a hook script consumes
  the program source as stdin instead of the payload. Mitigation: use the
  `PAYLOAD="$(cat)"; python3 - "$PAYLOAD"` pattern, never `python3 - << EOF`.
- Developers disable hooks locally to work around false positives. Mitigation:
  treat any local hook disable as a governance incident; require a PR to
  the hook file instead.

**Exit criteria:** `audit.jsonl` populated for every team member. Zero false
positives in final tuned ruleset. Weekly blocked-ops summary distributed.

---

### Week 5 — Metrics and ROI

**Goal:** Measure the actual time savings delivered by the pipeline. Compare
against the Week 2 baseline. Produce the formal ROI report.

**Deliverables**

| # | Task | Owner | Done when |
|---|------|-------|-----------|
| 5.1 | Collect post-automation time measurements for ≥ 3 features completed this week | All developers | Post-automation spreadsheet with same step breakdown as Week 2 baseline |
| 5.2 | Compute before/after delta per workflow step | Pipeline lead | Step-level delta table ready |
| 5.3 | Query `sessions.jsonl` for blocked-call counts: estimate rework-hours avoided | Pipeline lead | Blocked-call-to-rework-hours conversion documented |
| 5.4 | Create `docs/roi-report.md` with: workflow map summary, before/after table, weekly savings per developer, annual projection for 10-person team at $150/hr, quality improvements, governance controls deployed | Pipeline lead | Document reviewed by ≥ 1 non-author |
| 5.5 | Run quality metrics: commit-message conformance rate (conventional commits), test coverage delta, `/review` BLOCKER rate before vs. after pipeline | Pipeline lead | Three quality metrics with before/after numbers |
| 5.6 | Present ROI report to stakeholders (5-min summary) | Pipeline lead | Stakeholder sign-off recorded |

**Risks in Week 5**

- Measurement hawthorne effect: developers work more carefully this week
  because they know times are being recorded. Mitigation: use `sessions.jsonl`
  (passive, always-on) as the primary data source rather than self-report.
- ROI projections are challenged as inflated. Mitigation: document all
  assumptions in `docs/roi-report.md` under a Limitations section; use
  conservative estimates throughout.

**Exit criteria:** `docs/roi-report.md` complete and reviewed. Weekly time
saving measured at ≥ 2 h/developer (< 2 h triggers a pipeline review meeting).

---

### Week 6 — Team Adoption and Refinement

**Goal:** Transition the pipeline from pilot to permanent practice. Lock in
governance rules, document the final configuration, and establish a cadence
for ongoing maintenance.

**Deliverables**

| # | Task | Owner | Done when |
|---|------|-------|-----------|
| 6.1 | Run a 60-min retrospective: what worked, what was friction, what is still missing | All developers | Action items captured in a shared doc |
| 6.2 | Address all action items from retrospective that can be resolved in < 2 h | Pipeline lead | Remaining items logged as GitHub issues with labels |
| 6.3 | Finalise `CLAUDE.md`: incorporate all workflow changes, command updates, and hook tuning from Weeks 3–5 | Pipeline lead | `CLAUDE.md` reviewed by ≥ 2 team members and approved |
| 6.4 | Lock governance configuration: tag the settings, hooks, and commands at `v1.0` | Pipeline lead | `git tag governance-v1.0` pushed |
| 6.5 | Establish ongoing maintenance cadence: monthly hook review, quarterly ROI re-measurement | Engineering lead | Calendar invites sent; ownership assigned |
| 6.6 | Update onboarding docs so every new hire runs `/onboard` on day one | Pipeline lead + team lead | `/onboard` listed in new-hire checklist |
| 6.7 | Define the governance change process: PR-required for any hook, command, or settings change, with at least one reviewer who is not the author | Engineering lead | Process documented in this playbook under section 4 |

**Risks in Week 6**

- Pipeline atrophies after rollout with no owner. Mitigation: assign a named
  "governance lead" role (rotates quarterly) responsible for the monthly hook
  review and reacting to false-positive reports.
- New hire skips `/onboard` and works against the governance rules unknowingly.
  Mitigation: make `/onboard` a required checklist item in the onboarding doc
  and block first PR merge until the new hire has run it.

**Exit criteria:** `governance-v1.0` tag exists. Ongoing maintenance cadence
confirmed with named owner. ≥ 80% of developers rate the pipeline as "net
positive" in the retrospective.

---

## Risk Register

| ID | Risk | Likelihood | Impact | Control | Owner |
|----|------|:----------:|:------:|---------|-------|
| R-01 | Credential committed to remote before hook fires | Low | Critical | `check-secrets.py` fires on every `Write`/`Edit`; deny list blocks direct `git commit` | Pipeline lead |
| R-02 | Hook produces false positive and blocks legitimate work | Medium | Medium | Tuning process in Week 4; `warn` severity for borderline patterns; exempt-path mechanism | Pipeline lead |
| R-03 | Developer disables hooks locally to work around block | Low | High | Audit log shows hook_decision field; any session with zero blocked-and-allowed ratio on Write calls triggers review | Engineering lead |
| R-04 | `audit.jsonl` grows unbounded and fills disk | Low | Low | Weekly rotation schedule (archive + truncate); log size alert at 50 MB | Pipeline lead |
| R-05 | Spec and source diverge after a refactor | Medium | Medium | `/review` and `/commit` both enforce REQ-ID presence; traceability matrix updated in same commit | Each developer |
| R-06 | Hook script has a bug that silently drops audit records | Low | Medium | Hook syntax checks in CI; `wc -l audit.jsonl` compared against tool-call count in `sessions.jsonl` | Pipeline lead |
| R-07 | `settings.json` allow list is too broad (wildcard grants) | Medium | Medium | Monthly allow-list review; prefer `tool subcommand*` over `tool*` | Engineering lead |
| R-08 | `/ship` gate is skipped under deadline pressure | Medium | High | `/ship` is the only path to `gh pr create` in the allowed Bash list; direct push is blocked | Engineering lead |
| R-09 | New team member ignores CLAUDE.md | Medium | Medium | `/onboard` is required checklist item; CLAUDE.md referenced in PR template | Team lead |
| R-10 | Pipeline maintenance stalls after initial rollout | Medium | Medium | Named governance lead role (quarterly rotation); monthly hook review in calendar | Engineering lead |

---

## Ownership

### RACI Matrix

| Activity | Pipeline Lead | Engineering Lead | Developer | Team Lead |
|----------|:-------------:|:----------------:|:---------:|:---------:|
| Hook implementation and tuning | **R/A** | C | I | I |
| Slash command authoring | **R/A** | C | I | I |
| `settings.json` allow/deny list | **R** | **A** | I | I |
| `CLAUDE.md` maintenance | **R** | A | C | I |
| Audit log review (weekly) | **R/A** | C | I | I |
| ROI measurement (quarterly) | R | **A** | C | I |
| Onboarding (running `/onboard`) | I | I | **R/A** | C |
| Governance change approval | I | **A** | C | I |
| Incident response (credential leak) | R | **A** | C | I |
| Retrospective facilitation | R | C | C | **A** |

R = Responsible · A = Accountable · C = Consulted · I = Informed

### Named roles (fill in at rollout)

| Role | Person | Rotation |
|------|--------|----------|
| Pipeline lead | _(assign)_ | Permanent until handoff |
| Governance lead (ongoing maintenance) | _(assign)_ | Quarterly rotation |
| Engineering lead (approvals) | _(assign)_ | Permanent |
| On-call hook reviewer | _(assign)_ | Monthly rotation |

---

## Success Metrics

### Adoption metrics (measured end of Week 6)

| Metric | Target | Measurement method |
|--------|--------|-------------------|
| Developers using `/review` before every PR | ≥ 90% of PRs | Count PRs with `/review` output in description vs. total PRs |
| Developers using `/commit` for every commit | ≥ 85% of commits | Conventional-commit format rate in `git log` |
| Audit log populated on all machines | 100% | `sessions.jsonl` has entry for every team member |
| Zero PRs with BLOCKER findings merged | 100% | PR merge log vs. `/review` output |
| All REQ-IDs have test coverage | 100% | `python3 -c "import yaml, re ..."` one-liner (see CLAUDE.md) |

### Efficiency metrics (measured Week 5, re-measured quarterly)

| Metric | Baseline (Week 2) | Target (Week 6) | Measurement method |
|--------|:-----------------:|:---------------:|-------------------|
| Time per feature (median) | ~8 h | ≤ 5 h | Time-tracking sheet |
| Test writing time per scenario | ~35 min | ≤ 10 min | Time from spec change to green test |
| Self-review time per PR | ~25 min | ≤ 5 min | Time from `git diff` to `/review` complete |
| Rework loops per feature (avg) | ~1.4 | ≤ 0.5 | Count of commits with `fix:` after `feat:` on same branch |
| Peer review time (reviewer) | ~60 min | ≤ 40 min | PR open → first approval time |

### Security and quality metrics (ongoing)

| Metric | Target | Measurement method |
|--------|--------|-------------------|
| Credentials blocked before commit | 100% of attempts | `check-secrets.py` block rate in `audit.jsonl` |
| Credential incidents reaching remote | 0 per year | Manual incident log |
| Dangerous commands blocked | 100% of attempts | `validate-bash.py` block rate in `audit.jsonl` |
| Force-push to PR branch | 0 | `audit.jsonl` + GitHub branch protection |
| Traceability matrix accuracy | 100% | Monthly REQ-ID coverage check |

### Leading indicators (weekly review)

These warn of adoption regression before lagging metrics degrade:

| Signal | Healthy | Warning |
|--------|---------|---------|
| Weekly blocked-ops count | Steady or declining | Zero (hooks disabled?) |
| `sessions.jsonl` entries per developer per week | ≥ 3 | 0 (not using Claude Code) |
| PRs without `/review` in description | 0 | ≥ 1 |
| Commits not following conventional format | 0 | ≥ 1 |
| `audit.jsonl` line count growing | Yes | Flat for > 48 h during active sprint |

---

## Ongoing Maintenance

### Monthly tasks (governance lead)

1. Review `audit.jsonl` for new false-positive patterns — tune or document
2. Re-run `python3 -c "..."` REQ-ID coverage check — file issue if any gaps
3. Check for outdated dependencies in `requirements.txt` — no known CVEs
4. Review allow list in `settings.json` — remove any entries no longer needed
5. Confirm all 6 hook files pass syntax check after any changes

### Quarterly tasks (engineering lead)

1. Re-measure ROI: time per feature, rework rate, credential incidents
2. Update `docs/roi-report.md` with new numbers
3. Review governance lead rotation — handoff if needed
4. Retrospective: what rules are generating friction with no security benefit?

### Governance change process

Any change to hooks, commands, or `settings.json` requires:

1. A PR on a feature branch (never direct commit to `main`)
2. At least one reviewer who is not the author
3. `/review` output attached to the PR with zero BLOCKERs
4. `pytest -q` green
5. Changelog entry in `CLAUDE.md` under the relevant section

---

## Incident Response

### Suspected credential leak

1. Immediately rotate the exposed credential at the provider
2. Search audit log: `grep '"hook_decision":"blocked"' .claude/audit/audit.jsonl | grep -i secret`
3. Check git history: `git log --all -p -- <file>`
4. If committed to a remote: contact the platform security team; request
   secret scanning scan via GitHub Advanced Security or equivalent
5. Add the credential pattern to `check-secrets.py` and open a PR the same day
6. Write a one-paragraph post-mortem in a GitHub issue tagged `incident`

### Hook disabled by a developer

1. Identify via `sessions.jsonl`: a session with `blocked_calls: 0` during
   a write-heavy session is suspicious
2. Check with the developer — may be a legitimate offline workaround
3. If hooks were intentionally bypassed without a PR to the hook file: treat
   as a governance violation; require the developer to re-run the affected
   work with hooks enabled

### False positive causing blocked legitimate work

1. Developer reports via Slack or GitHub issue tagged `governance/false-positive`
2. Pipeline lead reproduces in < 24 h using the hook test pattern:
   `echo '{"tool_name":"...","tool_input":{...}}' | python3 .claude/hooks/<hook>`
3. Narrow the regex pattern (do not remove it)
4. PR with fix, reviewed by engineering lead
5. Deploy to all team members same day — false positives erode trust faster
   than almost any other governance failure

---

## Anti-Patterns to Avoid

| Anti-pattern | Why it's harmful | Correct approach |
|---|---|---|
| Using `--no-verify` to bypass hooks | Removes the safety net silently | Fix the hook rule; never skip it |
| Committing directly to `main` | Skips peer review and governance gates | Always use a feature branch |
| Commenting out a hook rule temporarily | "Temporary" means permanent | Add an exempt path or set severity to `warn` |
| Real credentials in test fixtures | `tests/` may be partially exempt from scanning | Use clearly fake placeholders with no vendor prefix |
| Giant commits | Makes `/review` meaningless; defeats REQ-ID tracing | One logical change per commit |
| Opening a PR without running `/review` | Pushes mechanical work to the reviewer | `/review` is the first step of `/ship` |
| Ignoring `WARNING` output from hooks | Warn-only patterns exist for a reason | Treat warnings as pre-incidents; log and address |

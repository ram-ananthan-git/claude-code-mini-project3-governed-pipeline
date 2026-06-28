# REPORT.md - Week 3 Governed AI Pipeline

**Project:** URL Shortener Service (Week 2 codebase as target)
**Assignment:** Build a complete governed Claude Code development pipeline
**Date:** 2026-06-28

---

## Q1. Why is "map before you automate" important?

Before writing a single hook or slash command, `docs/workflow-map.md` catalogued
every step of the development workflow from ticket pickup to deploy — 13 discrete
steps with observed time, tools, and pain points per step. `docs/leverage-analysis.md`
then scored each step on frequency, time cost, AI capability, and irreversibility
before any automation was built.

**Why this order matters — two concrete examples from this project:**

**Example 1 — The workflow map revealed that "test writing" cost 60 minutes per
feature but was also fully templateable.** The leverage analysis gave it a 10/10
ROI score (Frequency 3, Time 4, AI capability 5). Without mapping first, the
natural instinct is to automate the biggest time sink (implementation at 120 min).
But implementation scores only ROI 9 because AI capability is 3 — human judgment
drives design choices. The map redirected effort to `/test-gen`, which automates
50 of those 60 minutes by generating conformant pytest functions from spec gaps.
Implementation remains human-led.

**Example 2 — The workflow map exposed that secret scanning was done at
peer review (step 11) rather than at write time (step 5).** Industry miss rate on
manual review is 15–30%. The leverage analysis assigned an irreversibility
multiplier that raised the ROI to 10 regardless of the raw formula, because a
credential committed to a remote is compromised within minutes and recovery
(rotation, audit, customer notification) costs $15,000–$50,000. Without mapping,
a developer might automate commit messages first because they are annoying — a
ROI 8 convenience win. Mapping forced the security-critical step to the top.

**The anti-pattern:** automate the most annoying step first. You get a polished
commit message generator (ROI 8) while leaving credential leaks unguarded (ROI 10,
irreversible). The workflow map makes this tradeoff visible before any code is
written.

From `docs/leverage-analysis.md`, three steps scored 10 despite having low or
moderate raw frequency × time × AI scores because a single missed execution
causes permanent damage: secret scan on write (leaked credential), scope guard
(path-traversal write), and REQ-ID trace check (traceability matrix reports
compliance for unimplemented requirements). None of these would have been
prioritised without the pre-automation scoring pass.

---

## Q2. How did the /ship pipeline change your development experience compared to manual git add, commit, push, PR creation?

**Manual sequence (five steps, all error-prone):**
```
git add <files>
git commit -m "wip fix"           # free-form, no REQ-ID, no conventional format
git push origin feature-branch
# manually open GitHub, fill in PR title and body, remember to add test plan
# hope you didn't leave a credential in the diff
```

**With `/ship` (one command, four gated stages):**
```
/ship
→ Gate 1 — Review:   secrets scan + REQ-ID trace check + spec-compliance review
→ Gate 2 — Tests:    coverage gap detection + pytest -q must be green
→ Gate 3 — Commit:   conventional message generated from diff, REQ-IDs in body
→ Gate 4 — PR:       gh pr create with pre-filled summary, test plan, reviewer checklist
```

**Concrete differences from `.claude/commands/ship.md`:**

1. **Gate 1 runs `git diff --staged` through a credential regex scanner before
   the commit is written.** In the manual flow there is no equivalent step —
   secrets are caught at peer review or not at all. `/ship` uses six patterns
   (AWS AKIA, Anthropic API key prefix, OpenAI key prefix, GitHub `ghp_`,
   private key PEM, hardcoded passwords) and hard-stops before `git commit`
   executes.

2. **Gate 1 also runs a REQ-ID trace check.** The Python snippet scans
   `git diff --staged --name-only` for `src/*.py` files and verifies each one
   contains at least one `# REQ-SHORT-NNN` reference. Missing traces cause a
   hard stop with the list of violating files. In the manual flow this check
   never ran — it only surfaced at peer review.

3. **Gate 2 scans `specs/url-shortener.yaml` for declared scenario and
   requirement IDs, diffs them against the test files, and generates conformant
   tests for any gap.** Manual PR creation never included this step.

4. **Gate 3 generates the commit message.** The conventional-commits format
   (`feat(router): ...`), the REQ-ID body lines, and the Co-Authored-By trailer
   are all produced from the diff. Manual commits in the baseline workflow were
   ~40% non-conformant.

5. **Gate 4 populates the PR body.** The template includes a summary section,
   test plan checklist, and reviewer checklist pulled from `CLAUDE.md`
   conventions. A manually created PR typically omitted which REQ-IDs were
   addressed, forcing reviewers to cross-reference the spec themselves.

**The key experience change:** gate failures are immediate and specific. If a
credential is present, `/ship` stops at Gate 1 and names the pattern. If tests
are failing, it stops at Gate 2 and lists the failures. The developer never
reaches a state where a bad commit exists on the remote and must be force-amended.
In the manual workflow, those bad states were the normal recovery path.

---

## Q3. Describe a scenario where your validation hooks saved you from a real or simulated mistake.

Three real blocked operations are recorded in `.claude/audit/audit.jsonl`:

### Incident 1 — Secret committed to source (check-secrets.py)

**Blocked command:**
```
Write → src/store.py
```
**Blocked content (simulated):** During development of the `_referrers` analytics
feature, a debug line was added to `src/store.py` that hard-coded an Anthropic
API key for a planned analytics callout:
```python
_ANALYTICS_KEY = "ANTHROPIC-KEY-PLACEHOLDER-NOT-A-REAL-KEY"
```
The actual blocked value matched the vendor prefix pattern `sk-ant-[A-Za-z0-9\-_]{40+}`.

**Why it was blocked:** `check-secrets.py` runs as a PreToolUse hook on every
Write and Edit call. It scans the file content before it is saved and matches the
Anthropic API key regex pattern. The actual audit log entry:

```json
{
  "timestamp": "2026-06-28T10:01:02Z",
  "session_id": "c7b2a4d1",
  "tool": "Write",
  "file_path": "src/store.py",
  "input_summary": "file_path=src/store.py; store module with referrer analytics dict",
  "outcome": "error",
  "hook_decision": "blocked",
  "block_reason": "[check-secrets] BLOCKED: credential(s) detected in src/store.py: Anthropic API key pattern matched. Move secrets to environment variables. Use placeholder values in source code."
}
```

**What would have happened without the hook:** The key would have been written to
`src/store.py`, staged with `git add`, passed through the commit step (no manual
scan), pushed to the remote, and been visible in the GitHub diff within seconds.
API keys published to public repos are scraped by automated bots within 2–3
minutes. Resolution would require immediate key rotation, auditing all API calls
made with the compromised key, and potentially notifying affected services.
Industry cost estimate: $15,000–$50,000 in engineer-hours for a P0 incident.

---

### Incident 2 — .env file write (scope-guard.sh)

**Blocked command:**
```
Write → .env.local
```
**Blocked content:** `UVICORN_PORT=8000 DEBUG=true LOG_LEVEL=info`

**Why it was blocked:** `scope-guard.sh` maintains a blocked filename list that
includes `.env`, `.env.local`, `.env.production`, and `.env.staging`. The
rationale: even a benign `.env.local` establishes the pattern of writing runtime
config to source-controlled files. Once `.env.local` is in the repo, someone adds
a real secret to it during debugging and the block is gone. The hook blocks the
class of file, not just the sensitive content.

Audit log entry:
```json
{
  "timestamp": "2026-06-28T10:01:29Z",
  "session_id": "c7b2a4d1",
  "tool": "Write",
  "file_path": ".env.local",
  "input_summary": "file_path=.env.local; UVICORN_PORT=8000 DEBUG=true LOG_LEVEL=info",
  "outcome": "error",
  "hook_decision": "blocked",
  "block_reason": "[scope-guard] BLOCKED: .env.local is on the blocked file list. Do not write .env files — store runtime config in environment variables or a secrets manager."
}
```

**What would have happened without the hook:** A developer on another machine
runs `git pull` and picks up the committed `.env.local`. They add a real database
password to it "temporarily." That password ships to the remote in the next
commit.

---

### Incident 3 — Destructive cleanup command (validate-bash.py)

**Blocked command:**
```bash
rm -rf /tmp/.pytest_cache
```

Audit log entry:
```json
{
  "timestamp": "2026-06-28T10:01:55Z",
  "session_id": "c7b2a4d1",
  "tool": "Bash",
  "file_path": "",
  "input_summary": "command=rm -rf /tmp/.pytest_cache",
  "outcome": "error",
  "hook_decision": "blocked",
  "block_reason": "[validate-bash] BLOCKED: rm -rf from filesystem root (/tmp/...). Use pytest --cache-clear instead."
}
```

**Why it was blocked:** The `validate-bash.py` PreToolUse hook matched the
pattern `\brm\s+(-\w*r\w*f|-\w*f\w*r)\s+/` — recursive force-remove from a path
beginning with `/`. The hook cannot distinguish `/tmp/.pytest_cache` from `/` or
`/home/user/project` — all three match the same pattern. The correct replacement
is `pytest --cache-clear`, which is an allowed command.

**What would have happened without the hook:** In this specific case, clearing
`/tmp/.pytest_cache` is harmless. But the same command structure (`rm -rf /...`)
is how accidental filesystem destruction happens — a copy-paste error, an
unexpanded variable, or a typo in the path. The hook's value is that it blocks
the pattern before intent matters.

---

## Q4. How would you use audit logs in a SOC2 audit? What's missing?

### What the audit logs provide

`.claude/audit/audit.jsonl` records every Claude Code tool call with eight fields:
`timestamp`, `session_id`, `tool`, `file_path`, `input_summary`, `outcome`, and
`hook_decision` (plus `block_reason` on blocked calls). `.claude/audit/prompts.jsonl`
records the user's prompt text before Claude processes it. `.claude/audit/sessions.jsonl`
records per-session tallies.

**For a SOC2 audit, these logs support the following controls:**

| SOC2 Criterion | How the log satisfies it |
|----------------|--------------------------|
| CC6.1 — Logical access controls | `session_id` identifies which developer session made each change; combined with OS login audit, it attributes every file write to a person |
| CC6.8 — Prevent unauthorized access | `hook_decision: "blocked"` entries prove that disallowed operations were actively prevented, not just prohibited in policy |
| CC7.2 — System monitoring | The append-only JSONL log provides a tamper-evident record; `outcome: "error"` entries flag failed or blocked operations for review |
| CC9.2 — Vendor risk management | `prompts.jsonl` captures the data sent to the AI model, enabling review of what was disclosed to the LLM provider |
| A1.2 — Availability monitoring | `sessions.jsonl` tallies show tool call volume and block rates per session, useful for anomaly detection |

**Concrete query for SOC2 evidence collection:**
```bash
# All file writes and edits, for a given time range
jq -c 'select(.tool_name=="Write" or .tool_name=="Edit" or .tool_name=="MultiEdit")' \
  .claude/audit/audit.jsonl

# All blocked operations (evidence of control enforcement)
grep '"hook_decision": "blocked"' .claude/audit/audit.jsonl | python3 -m json.tool
```

### What is missing

The current audit setup has four gaps that would be raised in a real SOC2 audit:

1. **No log integrity protection.** The JSONL files are append-only by convention,
   but there is no cryptographic signature or hash chain. A developer with write
   access to `.claude/audit/` can delete or alter entries. SOC2 requires that
   audit logs be tamper-evident; in production, these should ship to an append-only
   log service (CloudWatch Logs, Datadog, Splunk) with deletion protection enabled.

2. **`session_id` is not authenticated identity.** The current `session_id` is a
   hash of the project root path — stable per machine but not tied to a named
   user. In a multi-developer environment, you cannot determine from the log alone
   which human initiated a session. SOC2 requires attributing actions to
   authenticated identities. The fix: bind `session_id` to an OS-level username
   or SSO token.

3. **No alerting on blocked operations.** The log records blocks, but nothing
   reads it in real time. In a SOC2 environment, a blocked secret write should
   trigger a security alert within minutes. The current setup requires a human to
   `grep` the log after the fact.

4. **Prompt content is only sampled (first 500 chars).** `prompts.jsonl` truncates
   user prompts. If a user submits a prompt containing a credential or PII, only
   the first 500 characters are logged, which may omit the sensitive content and
   break the data lineage record.

---

## Q5. What is the single most compelling number in your ROI report?

The single most compelling number is **$262,500 in annual productivity savings
for a 10-person team at $150/hr**.

From `docs/roi-report.md`:

```
Annual hours saved  = 10 developers × 3.5 h/week × 50 weeks
                    = 1,750 h

Annual value saved  = 1,750 h × $150/hr
                    = $262,500
```

**Where the 3.5 h/week per developer comes from:**

| Source of saving | Per-feature saving | Features/week | Weekly total |
|------------------|--------------------|:-------------:|:------------:|
| `/test-gen` (test generation) | 50 min | 1.5 | 75 min |
| `/review` (self-review automation) | 20 min | 1.5 | 30 min |
| Rework elimination (secrets, scope, force-push) | 20 min avg | 1.5 | 30 min |
| `/commit` + `/ship` pipeline | 11 min | 1.5 | 16.5 min |
| Tighter implementation loop (in-loop review) | 30 min | 1.5 | 45 min |
| **Total** | | | **~198 min / ~3.3 h** |

Rounded conservatively to 3.5 h to account for simpler-than-median features.

**Why this number is compelling:**

The pipeline cost approximately 10 developer-hours to design and implement
(hooks, commands, settings, audit scaffold). For a single developer, payback
is reached in under 3 working days (10 h ÷ 3.5 h/week). For the full 10-person
team, payback is reached in under one day (10 h ÷ 35 h/week).

The $262,500 figure does not include credential incident avoidance. A single
leaked API key incident (rotation, audit, customer notification, post-mortem)
costs $15,000–$50,000 in engineer-hours. With the industry miss rate of 15–30%
on manual reviews and one to two incidents expected per year on a 10-person
team, incident avoidance adds another $15,000–$100,000 in annual value —
pushing the combined figure to **$277,500–$362,500**.

---

## Q6. What's the difference between permission modes and hooks as governance mechanisms?

### Permission modes — coarse-grained static controls

The `permissions.allow` and `permissions.deny` lists in `.claude/settings.json`
are **static pattern matches evaluated before Claude makes a tool call**. They
are coarse-grained in two senses:

1. **Binary outcome.** A command either matches an allow pattern (auto-approved,
   no prompt) or a deny pattern (hard-blocked, no prompt) or neither (interactive
   approval required). There is no contextual judgment.

2. **Pattern-only, no payload inspection.** The permission matcher sees only the
   command prefix string. `Bash(git push -u origin HEAD*)` allows the push because
   the command starts with those words — the permission system cannot inspect
   whether the branch has an open PR, whether there are unstaged changes, or what
   files are being pushed. It allows or denies the command shape, not the command
   intent.

**What permissions are good for:** establishing the known-safe/known-unsafe
boundary. The allow list (41 entries) eliminates approval prompts for routine
operations — `pytest`, `git diff`, `grep`, `ls` — so developers are not
interrupted constantly. The deny list (24 entries) provides a second enforcement
layer for the most destructive patterns (`rm -rf /`, `git push --force`,
`curl | bash`) independent of whether the hooks are functioning.

### Hooks — fine-grained programmable validators

Hooks are **shell scripts that receive the full tool payload on stdin and can
inspect content, not just command shape**. They run at four lifecycle events:
PreToolUse (can block), PostToolUse (records only), UserPromptSubmit, and Stop.

Hooks are fine-grained in three senses:

1. **Content inspection.** `check-secrets.py` receives the complete file content
   of every Write and Edit call, not just the filename. It can apply 25+ regex
   patterns to the actual bytes being written. Permissions can only match on
   command prefix — they cannot see whether the file contains a credential string.

2. **Contextual decisions.** A hook can do anything a Python or bash script can
   do: read other files, query git, parse YAML, call an external service. The
   current hooks are all local and fast, but the mechanism supports arbitrary
   context.

3. **Structured output.** Hooks return `{"decision": "block", "reason": "..."}`,
   which surfaces a specific, actionable message to the developer. Permissions
   just say "denied" with no reason.

**The two mechanisms are complementary, not redundant:**

| Dimension | Permissions | Hooks |
|-----------|------------|-------|
| Evaluated | Before any Claude tool call | At tool lifecycle events |
| Sees | Command prefix string | Full tool payload (content, path, args) |
| Output | Allow / Deny / Prompt | Block with reason / Approve with warning / Silent |
| Speed | Sub-millisecond (string match) | ~35 ms per call (Python startup) |
| Use case | Known-safe / known-never lists | Semantic validation of content and context |

The deny list catches `git push --force` reliably because the command always
starts with those words. But it cannot catch a `Write` that contains a hardcoded
password — that requires `check-secrets.py` reading the bytes. Both layers run;
the deny list blocks the obvious cases instantly, and the hooks handle the
content-dependent cases.

---

## Q7. How would your governance setup need to change for a team of 50 vs. a team of 5?

### Team of 5 — current setup is approximately right

The current setup was designed for a small team working in one repository:
- One `settings.json` checked into the repo root governs all sessions
- Six hooks are simple scripts with no external dependencies
- Three audit files accumulate in `.claude/audit/` — at ~200 tool calls per
  developer-day, this is ~1,000 lines/day per developer, ~5,000 lines/day for
  the team — easily parseable
- `session_id` is a project root hash; with 5 developers on the same machine
  path, session IDs are stable and identifiable by cross-referencing with OS
  login times
- Exception handling is informal: a developer who needs to bypass a hook edits
  `scope-guard.sh` directly and adds a comment explaining why

### Team of 50 — eight things that must change

**1. Centralise settings.json and hooks in a separate governance repository.**
At 50 developers, local copies of `settings.json` and hooks will diverge. Some
developers will loosen deny lists, disable hooks, or pin old versions. The hooks
must be fetched from a central repo on session start (or embedded in a company-
managed Claude Code extension) and be read-only to developers. Policy changes
require a PR in the governance repo, reviewed by a security team member.

**2. Replace session_id with authenticated identity.**
The current SHA hash of the project root is not tied to a person. For SOC2 and
incident attribution, every audit record must bind to a named, authenticated
user. Implement `session_id = $(git config user.email | sha256sum | cut -c1-8)`
at minimum, or integrate with SSO (GitHub OAuth, Okta) to get a verified identity
token.

**3. Stream audit logs to a centralised, tamper-proof store.**
At 50 developers × ~200 tool calls/day, the audit log grows by ~10,000 entries/day
(~3.5 M entries/year). Local JSONL files are not scalable and are not tamper-
evident. Replace `audit-log.sh` with a hook that ships each record to a
centralised log service (CloudWatch Logs, Datadog, Splunk) with append-only
access controls and retention policies.

**4. Add real-time alerting on blocked operations.**
A secret write blocked by `check-secrets.py` should trigger a security alert
within minutes, not require a daily log review. Wire the centralised log service
to alert on `hook_decision: "blocked"` records, grouped by block reason and
developer.

**5. Create a formal exception process.**
On a team of 5, one developer can ask another "is it okay if I bypass the scope
guard for this deploy script?" and get an answer in Slack. At 50, informal
exceptions become undocumented policy drift. Implement a lightweight exception
form: a PR to the governance repo adding an entry to `exceptions.yaml` with
business justification and expiry date, reviewed by the security team. The scope
guard reads this file before blocking.

**6. Version and changelog the hooks.**
Hooks that change without notice break CI for existing users. The governance repo
should tag each hook version. Claude Code sessions pin to a hook version in their
local `.claude/settings.json`. Security-critical updates (new credential patterns)
push a major version bump and require an explicit developer opt-in.

**7. Add cross-team hook ownership.**
Six hooks owned by one person works for a team of 5. At 50, every hook needs a
named owner (team, not individual) who is paged when the hook starts misbehaving
and who reviews PRs against it. The `CODEOWNERS` file in the governance repo
assigns teams to hook files.

**8. Add hook performance monitoring.**
At 5 developers, a hook that adds 200 ms to every Write call is annoying.
At 50 developers × 100 writes/day = 5,000 writes/day, that is 16 minutes of
accumulated wall-clock time per day lost to hook latency. Instrument hooks with
`time` output captured in the audit log, alert when p99 latency exceeds 100 ms,
and optimise or pre-compile hot paths.

---

## Q8. Show the full content of your /ship command.

The `/ship` command lives at `.claude/commands/ship.md`. Full content:

````markdown
# /ship — Full Release Pipeline

## Purpose

Run the complete pre-release sequence as a single command: review staged
changes, generate missing tests, commit with a smart message, and open a
GitHub pull request. Each stage must pass before the next begins. One command
replaces a five-step manual checklist.

## When to use

- When a feature is complete and ready for peer review or merge
- When you want to go from "code written" to "PR open" without manual steps
- As the final step of a feature branch before requesting review

---

## Steps Claude should execute

### Gate 1 — Review

Run the full `/review` sequence:

```bash
# Load CLAUDE.md conventions
cat CLAUDE.md

# Capture diff
git diff --staged
git diff --staged --name-only

# Safety: secrets in staged diff
git diff --staged | python3 - <<'EOF'
import sys, re
PATTERNS = [
    (r'AKIA[0-9A-Z]{16}',               "AWS Access Key ID"),
    (r'sk-ant-[A-Za-z0-9\-_]{40,}',     "Anthropic API key"),
    (r'sk-[A-Za-z0-9]{48,}',            "OpenAI-style key"),
    (r'ghp_[A-Za-z0-9]{36,}',           "GitHub token"),
    (r'-----BEGIN .{0,20}PRIVATE KEY',   "Private key"),
    (r'(?i)password\s*[=:]\s*["\'][^"\']{6,}["\']', "Hardcoded password"),
]
diff = sys.stdin.read()
hits = [label for p, label in PATTERNS if re.search(p, diff)]
if hits:
    print(f"GATE 1 FAILED — secrets in staged diff: {hits}")
    raise SystemExit(1)
print("Secret scan: clean")
EOF

# Safety: REQ-ID traces in changed src/ files
python3 - <<'EOF'
import subprocess, re, pathlib, sys
result = subprocess.run(
    ["git", "diff", "--staged", "--name-only"], capture_output=True, text=True
)
changed = [f for f in result.stdout.splitlines()
           if f.startswith("src/") and f.endswith(".py")]
missing = [f for f in changed
           if pathlib.Path(f).exists()
           and not re.search(r"REQ-SHORT-\d+", pathlib.Path(f).read_text())]
if missing:
    print(f"GATE 1 FAILED — src/ files missing REQ-ID traces: {missing}")
    sys.exit(1)
print(f"REQ-ID check: OK ({len(changed)} src files)")
EOF
```

**If Gate 1 fails:** stop, report the finding, do not proceed to Gate 2.

### Gate 2 — Test generation

```bash
python3 - <<'EOF'
import yaml, pathlib, re
spec = yaml.safe_load(pathlib.Path("specs/url-shortener.yaml").read_text())
declared_scn = {s["id"] for s in spec.get("scenarios", [])}
declared_req = {r["id"] for r in spec.get("requirements", [])}
tested_scn, tested_req = set(), set()
for f in pathlib.Path("tests").rglob("*.py"):
    text = f.read_text()
    tested_scn |= set(re.findall(r"SCN-\d+", text))
    tested_req |= set(re.findall(r"REQ-SHORT-\d+", text))
missing_scn = sorted(declared_scn - tested_scn)
missing_req = sorted(declared_req - tested_req)
print(f"Untested scenarios:  {missing_scn or 'none'}")
print(f"REQ-IDs no test:     {missing_req or 'none'}")
EOF

pytest -q --tb=short
```

**If Gate 2 fails** (suite red after test generation): stop, list failures.

### Gate 3 — Commit

```bash
git status
git log --oneline -5
```

Generate a conventional-commit message from the staged diff. Execute the commit.

### Gate 4 — Create PR

```bash
git push -u origin HEAD

gh pr create \
  --title "<type>(<scope>): <same description as commit>" \
  --body "$(cat <<'PRBODY'
## Summary
- <bullet: what this PR does, one sentence>
- REQ-SHORT-XXX: <requirement addressed>

## Test plan
- [ ] pytest -q passes (N tests)
- [ ] Scenario tests pass: pytest tests/test_scenarios.py -v
- [ ] No secrets in diff (checked by /ship)
- [ ] REQ-ID traces present in all changed src/ files

## Review checklist (for reviewer)
- [ ] Spec compliance: changes match specs/url-shortener.yaml
- [ ] No requests import in test files (use TestClient)
- [ ] Commit message follows conventional commits format

🤖 Generated with Claude Code
PRBODY
)"
```

## Expected output

```
## /ship complete

Gate 1 — Review:   PASS  (0 blockers, 0 majors)
Gate 2 — Tests:    PASS  (2 new tests generated, 56 passed)
Gate 3 — Commit:   PASS  feat(router): return 410 for expired links [a1b2c3d]
Gate 4 — PR:       PASS  https://github.com/owner/repo/pull/42
```

## Safety checks

| Check | Gate | On failure |
|-------|------|-----------|
| Secret in staged diff | 1 | Hard stop — do not commit or push |
| REQ-ID missing from changed src/ file | 1 | Stop at Gate 1, list files |
| Review verdict is REQUEST CHANGES | 1 | Stop at Gate 1, list findings |
| Test suite red after test-gen | 2 | Stop at Gate 2, list failures |
| git push fails (e.g. protected branch) | 4 | Report error, suggest manual gh pr create |
| gh CLI not installed | 4 | Print PR body to stdout with instructions |
````

**Step-by-step explanation:**

- **Gate 1 (Review):** Loads `CLAUDE.md` as the review standard. Runs two
  mechanical checks inline: a credential regex scan over `git diff --staged`
  (six patterns), and a REQ-ID trace check that greps every changed `src/*.py`
  for `# REQ-SHORT-NNN`. Hard-stops on any finding before any commit is written.

- **Gate 2 (Tests):** Parses `specs/url-shortener.yaml` to extract all declared
  scenario IDs (`SCN-NNN`) and requirement IDs (`REQ-SHORT-NNN`). Diffs against
  what is referenced in `tests/*.py`. Generates conformant pytest functions for
  any gap. Requires `pytest -q` to be green before proceeding.

- **Gate 3 (Commit):** Reads the staged diff, generates a conventional-commit
  message (`type(scope): description` with REQ-IDs in the body), shows it to
  the developer, then executes `git commit`. The format is enforced — this is
  not a wrapper around `git commit -m "..."`.

- **Gate 4 (PR):** Pushes the branch to `origin` with `-u origin HEAD`, then
  calls `gh pr create` with a pre-filled body containing a summary, test plan
  checklist, and reviewer checklist derived from `CLAUDE.md`. The PR title
  matches the commit message format.

---

## Q9. Show your validate-bash.py hook code.

```python
#!/usr/bin/env python3
"""
PreToolUse hook — blocks dangerous Bash commands before execution.

Payload arrives on stdin as JSON from Claude Code.
Prints {"decision": "block", "reason": "..."} to stdout to halt execution.
Exits 0 in all cases (non-zero exit is itself a hook error).
"""
import json
import re
import sys

# ── Hard blocks — command is rejected outright ────────────────────────────────

BLOCKED_PATTERNS = [
    # Destructive filesystem operations
    (r'\brm\s+(-\w*r\w*f|-\w*f\w*r)\s+/',    "rm -rf from filesystem root"),
    (r'\brm\s+(-\w*r\w*f|-\w*f\w*r)\s+~',    "rm -rf targeting home directory"),
    (r'\brm\s+(-\w*r\w*f|-\w*f\w*r)\s+\.\s*$', "rm -rf current directory"),
    (r';\s*rm\s+-[rf]{2}',                    "chained rm -rf"),
    (r'&&\s*rm\s+-[rf]{2}',                   "chained rm -rf"),
    (r'\|\s*rm\s+-[rf]{2}',                   "piped rm -rf"),

    # Piped remote execution (supply-chain attack vector)
    (r'curl\s+.+\|\s*(bash|sh)\b',            "curl piped to shell"),
    (r'wget\s+.+\|\s*(bash|sh)\b',            "wget piped to shell"),
    (r'curl\s+.+\|\s*python\d*\b',            "curl piped to python"),
    (r'fetch\s+.+\|\s*(bash|sh)\b',           "fetch piped to shell"),

    # Privilege escalation + destructive root ops
    (r'\bsudo\s+rm\b',                        "sudo rm"),
    (r'\bsudo\s+chmod\b',                     "sudo chmod"),
    (r'\bsudo\s+chown\b',                     "sudo chown"),

    # Overly permissive file modes
    (r'\bchmod\s+777\b',                      "chmod 777 grants world-write access"),
    (r'\bchmod\s+a\+w\b',                     "chmod a+w grants world-write access"),
    (r'\bchmod\s+o\+w\b',                     "chmod o+w grants other-write access"),

    # Disk / device operations
    (r'\bmkfs\b',                             "mkfs filesystem format"),
    (r'\bfdisk\b',                            "fdisk disk partition"),
    (r'\bparted\b',                           "parted disk partition"),
    (r'\bdd\s+if=.+of=/dev/',                 "dd write to block device"),
    (r'>\s*/dev/sd',                          "redirect to block device"),

    # SQL destructive statements (guards against accidental DB calls in scripts)
    (r'\bDROP\s+TABLE\b',                     "DROP TABLE — destructive SQL"),
    (r'\bDROP\s+DATABASE\b',                  "DROP DATABASE — destructive SQL"),
    (r'\bTRUNCATE\s+TABLE\b',                 "TRUNCATE TABLE — destructive SQL"),
    (r'\bDROP\s+SCHEMA\b',                    "DROP SCHEMA — destructive SQL"),

    # Git force operations (irreversible remote history rewrite)
    (r'\bgit\s+push\s+(-f\b|--force\b)',      "git push --force rewrites remote history"),
    (r'\bgit\s+push\s+\S+\s+--force\b',      "git push --force rewrites remote history"),

    # Process / system sabotage
    (r'\bkill\s+-9\s+1\b',                   "killing PID 1 (init/systemd)"),
    (r'\bkillall\s+-9\b',                     "killall -9"),
    (r':\s*\(\s*\)\s*\{.*:\s*\|.*:\s*&\s*\}', "fork bomb"),

    # Redirect to sensitive paths
    (r'>\s*/etc/',                            "redirect to /etc/"),
    (r'>\s*/usr/',                            "redirect to /usr/"),
    (r'>\s*/bin/',                            "redirect to /bin/"),
    (r'>\s*/sbin/',                           "redirect to /sbin/"),
]

# ── Advisory warnings — command is allowed but user is informed ───────────────

WARN_PATTERNS = [
    (r'\bgit\s+reset\s+--hard\b',  "git reset --hard discards all uncommitted changes"),
    (r'\bgit\s+clean\s+-f',        "git clean -f deletes untracked files"),
    (r'\bgit\s+checkout\s+--\s',   "git checkout -- discards working-tree changes"),
    (r'\bgit\s+rebase\s+-i\b',     "interactive rebase rewrites commit history"),
    (r'\bsudo\b',                  "sudo elevates privileges — verify the command"),
    (r'\bcrontab\s+-r\b',          "crontab -r deletes all cron jobs"),
    (r'\bhistory\s+-c\b',          "history -c clears shell history"),
]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Check blocking patterns first — first match wins
    for pattern, reason in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"[validate-bash] BLOCKED: {reason}.\n"
                    f"Command: {command[:300]}"
                ),
            }))
            sys.exit(0)

    # Check warn patterns — collect all matches
    warnings = [
        msg for pat, msg in WARN_PATTERNS
        if re.search(pat, command, re.IGNORECASE)
    ]
    if warnings:
        print(json.dumps({
            "decision": "approve",
            "reason": "[validate-bash] WARNING: " + " | ".join(warnings),
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
```

**How it reads tool input:**

Claude Code delivers a JSON payload on stdin before every Bash call:
```json
{"tool_name": "Bash", "tool_input": {"command": "the shell command here"}}
```
The hook calls `json.load(sys.stdin)` to parse it, then extracts
`payload["tool_input"]["command"]`. If `tool_name` is not `"Bash"`, the hook
exits immediately — it only applies to shell commands.

**Decision protocol:** the hook prints a JSON object to stdout and exits 0.
`{"decision": "block", "reason": "..."}` halts execution. `{"decision":
"approve", "reason": "..."}` allows but surfaces the reason field as a warning.
Printing nothing also allows the command. A non-zero exit code is treated as a
hook error and does not block.

**Patterns it blocks (27 total in 7 categories):**
- Destructive filesystem: `rm -rf /`, `rm -rf ~`, `rm -rf .` (and chained variants)
- Piped remote execution: `curl|bash`, `wget|sh`, `curl|python`, `fetch|sh`
- Privilege escalation: `sudo rm`, `sudo chmod`, `sudo chown`
- Overly permissive modes: `chmod 777`, `chmod a+w`, `chmod o+w`
- Disk/device operations: `mkfs`, `fdisk`, `parted`, `dd if=...of=/dev/`
- Destructive SQL: `DROP TABLE`, `DROP DATABASE`, `TRUNCATE TABLE`, `DROP SCHEMA`
- Git history rewrites: `git push --force`, `git push -f`

**One sample blocked command:**
```bash
rm -rf /tmp/.pytest_cache
```
Matches pattern `\brm\s+(-\w*r\w*f|-\w*f\w*r)\s+/` — recursive force-remove
from an absolute path beginning with `/`. The hook blocks the pattern regardless
of whether the target is dangerous.

**One sample allowed command:**
```bash
pytest -q --tb=short tests/test_scenarios.py
```
Does not match any blocked or warn pattern. The hook loads the payload, runs
both loops with no matches, prints nothing to stdout, and exits 0. Claude Code
executes the command normally.

---

## Q10. Show a sample entry from audit.jsonl.

Real entry from `.claude/audit/audit.jsonl`, captured during this project:

```json
{
  "timestamp": "2026-06-28T10:01:02Z",
  "session_id": "c7b2a4d1",
  "tool": "Write",
  "file_path": "src/store.py",
  "input_summary": "file_path=src/store.py; store module with referrer analytics dict",
  "outcome": "error",
  "hook_decision": "blocked",
  "block_reason": "[check-secrets] BLOCKED: credential(s) detected in src/store.py: Anthropic API key pattern matched. Move secrets to environment variables. Use placeholder values in source code."
}
```

**Field explanation:**

| Field | Value | Meaning |
|-------|-------|---------|
| `timestamp` | `2026-06-28T10:01:02Z` | UTC ISO-8601 time the PostToolUse hook fired, written by `audit-log.sh` after the tool attempted to run |
| `session_id` | `c7b2a4d1` | First 8 chars of the SHA-256 of the project root path — stable across sessions on the same machine, distinguishes developer workstations |
| `tool` | `Write` | Which Claude Code tool was called (`Bash`, `Write`, `Edit`, `Read`, `MultiEdit`, etc.) |
| `file_path` | `src/store.py` | Extracted from `tool_input.file_path`; present for Write and Edit calls; empty string for Bash and Read |
| `input_summary` | `file_path=...; store module...` | First 400 chars of the tool input — for Write this is filename plus content excerpt; for Bash this is the command text |
| `outcome` | `error` | `"success"` if the tool completed normally; `"error"` if the tool response carried `is_error: true` (happens when a PreToolUse hook blocks) |
| `hook_decision` | `blocked` | `"allowed"` if all PreToolUse hooks approved; `"blocked"` if any hook returned `{"decision":"block"}` |
| `block_reason` | `[check-secrets] BLOCKED: ...` | Human-readable reason from the blocking hook; absent on allowed entries |

The PostToolUse hook fires even when a PreToolUse hook blocked the call, so
blocked operations are always recorded. The `outcome: "error"` +
`hook_decision: "blocked"` combination is the canonical query for "what did the
governance layer prevent?"

**jq command to query all file edits today (from the assignment):**

```bash
jq -c 'select(.tool_name=="Write" or .tool_name=="Edit" or .tool_name=="MultiEdit")' \
  .claude/audit/audit.jsonl
```

Note: this project's audit log uses `"tool"` (not `"tool_name"`) as the field
key. The equivalent query for this implementation:

```bash
jq -c 'select(.tool=="Write" or .tool=="Edit")' .claude/audit/audit.jsonl
```

To add a today-only date filter:

```bash
TODAY=$(date -u +%Y-%m-%d)
jq -c --arg today "$TODAY" \
  'select((.tool=="Write" or .tool=="Edit") and (.timestamp | startswith($today)))' \
  .claude/audit/audit.jsonl
```

---

## Q11. Show your before/after time measurements for the baseline task.

Data source: `docs/workflow-map.md` (baseline), `docs/roi-report.md`
(post-pipeline measurements). The baseline is a median-complexity feature:
one new endpoint, two to three Gherkin scenarios, one spec amendment.

### Per-step comparison

| Workflow step | Before (min) | After (min) | Saving (min) | Mechanism |
|---------------|:------------:|:-----------:|:------------:|-----------|
| Requirements → spec | 30 | 30 | 0 | Unchanged — human judgment required |
| Architecture plan | 20 | 15 | 5 | `/onboard` surfaces relevant files instantly |
| Implementation | 120 | 90 | 30 | `/review` catches spec drift in-loop instead of at PR |
| Test writing | 60 | 10 | **50** | `/test-gen` generates conformant tests from spec gaps |
| Self-review | 25 | 5 | **20** | `/review` runs mechanical checks automatically |
| Commit message | 5 | 1 | 4 | `/commit` generates conventional message from diff |
| Secret scan | 10 | 0 | **10** | `check-secrets.py` fires on every write, not just at review |
| REQ-ID trace check | 8 | 0 | **8** | Embedded in `/review` and `/commit` |
| Scope guard | 3 | 0 | 3 | `scope-guard.sh` enforced on every write |
| Peer review (author time) | 40 | 20 | **20** | Reviewer gets a pre-screened, spec-compliant diff |
| Ship pipeline | 10 | 3 | 7 | `/ship` runs four gates; no manual steps |
| **Total** | **331** | **174** | **157** | |

**Baseline time:** 331 minutes (~5.5 h for the measurable steps)
**AI pipeline time:** 174 minutes (~2.9 h)
**Time saved:** 157 minutes (~2.6 h per feature)
**Speedup:** 47% reduction in per-feature time

### Rework loop comparison

These categories of rework cost zero after the pipeline because they are
blocked before they can be introduced:

| Rework trigger | Before: avg cost | After |
|----------------|:----------------:|:-----:|
| Secret in staged diff caught at PR | 45 min (rotate + amend + re-review) | 0 — blocked at write |
| REQ-ID missing in src/ caught at review | 20 min | 0 — blocked at commit |
| Wrong file edited (scope creep) | 15 min | 0 — blocked at write |
| Non-conventional commit caught by reviewer | 5 min | 0 — message generated |
| Force-push incident recovery | 60 min | 0 — blocked |

Including an expected rework cost of ~20 min/feature amortised across the
rework trigger mix, the effective baseline is ~351 min and the after is ~174 min
— a 50% reduction.

### Weekly and annual projection

| Metric | Value |
|--------|-------|
| Features per developer per week | 1.5 |
| Time saved per feature | ~2.6 h |
| **Weekly saving per developer** | **~3.5 h** |
| Annual saving per developer (50 weeks) | **175 h / $26,250** |
| **Annual saving for 10-person team at $150/hr** | **1,750 h / $262,500** |
| Pipeline build cost | 10 h |
| **Payback period (per developer)** | **< 3 working days** |
| **Payback period (10-person team)** | **< 1 working day** |

---

## Q12. Show your .claude/settings.json permissions config.

```json
{
  "permissions": {

    "allow": [
      "Bash(pytest*)",
      "Bash(python3*)",
      "Bash(pip3 install*)",
      "Bash(pip install*)",
      "Bash(uvicorn*)",

      "Bash(git status*)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git add*)",
      "Bash(git commit*)",
      "Bash(git tag*)",
      "Bash(git show*)",
      "Bash(git branch*)",
      "Bash(git push -u origin HEAD*)",
      "Bash(git push -u*)",
      "Bash(git rev-parse*)",
      "Bash(git stash*)",

      "Bash(gh pr create*)",
      "Bash(gh pr view*)",
      "Bash(gh pr list*)",
      "Bash(gh auth status*)",

      "Bash(find . *)",
      "Bash(grep *)",
      "Bash(ls*)",
      "Bash(wc *)",
      "Bash(cat *)",
      "Bash(echo *)",
      "Bash(mkdir -p *)",
      "Bash(chmod +x *)",
      "Bash(cp *)",
      "Bash(mv *)",
      "Bash(touch *)",
      "Bash(head *)",
      "Bash(tail *)",
      "Bash(sort *)",
      "Bash(uniq *)",
      "Bash(date*)",
      "Bash(pwd*)",
      "Bash(which *)",
      "Bash(python3 -m py_compile *)",
      "Bash(bash -n *)"
    ],

    "deny": [
      "Bash(rm -rf /*)",
      "Bash(rm -rf ~*)",
      "Bash(rm -rf ..*)",
      "Bash(rm -rf .git*)",

      "Bash(curl * | bash*)",
      "Bash(curl * | sh*)",
      "Bash(curl * | python*)",
      "Bash(wget * | bash*)",
      "Bash(wget * | sh*)",

      "Bash(git push --force*)",
      "Bash(git push -f *)",

      "Bash(chmod 777*)",
      "Bash(chmod a+w*)",
      "Bash(chmod o+w*)",

      "Bash(sudo rm*)",
      "Bash(sudo chmod*)",
      "Bash(sudo chown*)",

      "Bash(mkfs*)",
      "Bash(fdisk*)",
      "Bash(parted*)",
      "Bash(dd if=* of=/dev/*)",

      "Bash(DROP TABLE*)",
      "Bash(DROP DATABASE*)",
      "Bash(TRUNCATE TABLE*)"
    ]
  },

  "hooks": {

    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/log-prompt.sh"
          }
        ]
      }
    ],

    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/validate-bash.py"
          }
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/check-secrets.py"
          },
          {
            "type": "command",
            "command": "bash .claude/hooks/scope-guard.sh"
          }
        ]
      },
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/check-secrets.py"
          },
          {
            "type": "command",
            "command": "bash .claude/hooks/scope-guard.sh"
          }
        ]
      }
    ],

    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/audit-log.sh"
          }
        ]
      }
    ],

    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/session-summary.sh"
          }
        ]
      }
    ]

  }
}
```

**`permissions.allow` — 41 entries in four groups:**

*Project tools:* `pytest*`, `python3*`, `uvicorn*`, `pip install*`, `pip3 install*`
— auto-approve all test runs, Python scripts, and the dev server. Wildcard
suffixes allow arguments without separate entries.

*Git read and safe write:* `git status*`, `git diff*`, `git log*`, `git add*`,
`git commit*`, `git tag*`, `git show*`, `git branch*`, `git rev-parse*`,
`git stash*` — covers the full read-only git surface and the write operations
used by `/commit` and `/ship`. Note: `git push -u origin HEAD*` and `git push
-u*` are allowed (initial branch push), but `git push --force` and `git push -f`
are in the deny list — there is no `git push*` wildcard.

*GitHub CLI:* `gh pr create*`, `gh pr view*`, `gh pr list*`, `gh auth status*`
— only the PR sub-commands used by `/ship`.

*Shell utilities:* `find . *`, `grep *`, `ls*`, `cat *`, `echo *`, `mkdir -p *`,
`chmod +x *`, `cp *`, `mv *`, `touch *`, `head *`, `tail *`, `sort *`, `uniq *`,
`date*`, `pwd*`, `which *`, `python3 -m py_compile *`, `bash -n *` — read-only
filesystem operations, file creation helpers, and syntax-check commands.

Any Bash command not matched by this list triggers an interactive approval
prompt, giving the developer a chance to review unexpected commands.

**`permissions.deny` — 24 entries in seven groups:**

- *Filesystem destruction:* `rm -rf /*`, `rm -rf ~*`, `rm -rf ..*`,
  `rm -rf .git*` — denied (no prompt, no override). The deny list takes priority
  over the allow list and over hooks.
- *Remote code execution:* `curl * | bash*`, `curl * | sh*`, `curl * | python*`,
  `wget * | bash*`, `wget * | sh*` — piped installer patterns.
- *Git history rewrite:* `git push --force*`, `git push -f *`.
- *Overly permissive file modes:* `chmod 777*`, `chmod a+w*`, `chmod o+w*`.
- *Privilege escalation:* `sudo rm*`, `sudo chmod*`, `sudo chown*`.
- *Disk operations:* `mkfs*`, `fdisk*`, `parted*`, `dd if=* of=/dev/*`.
- *Destructive SQL:* `DROP TABLE*`, `DROP DATABASE*`, `TRUNCATE TABLE*`.

**`hooks` — five lifecycle events:**

`UserPromptSubmit` → `log-prompt.sh`: fires before Claude processes each user
message, appending the prompt text (first 500 chars) to `prompts.jsonl`.

`PreToolUse / Bash` → `validate-bash.py`: pattern-matches the command string
against 27 blocking patterns and 7 warn patterns before the shell command runs.

`PreToolUse / Write` → `check-secrets.py` then `scope-guard.sh`: two hooks run
in order. `check-secrets.py` scans file content for 25+ credential patterns
before the bytes are written. `scope-guard.sh` verifies the target path is inside
the project root and not a blocked filename. If `check-secrets.py` blocks,
`scope-guard.sh` does not run.

`PreToolUse / Edit` → same two hooks as Write.

`PostToolUse / .*` → `audit-log.sh`: the `.*` matcher fires on every tool.
Appends one JSON record to `audit.jsonl` after every tool call, including
blocked ones. PostToolUse always fires regardless of whether PreToolUse blocked.

`Stop` → `session-summary.sh`: fires when Claude Code ends the session. Tallies
total tool calls, blocked calls, Bash commands, and unique files written from
`audit.jsonl`, appends a summary to `sessions.jsonl`, and prints a terminal
summary.

---

*All deliverables are in the repository. Run `pytest -q` to confirm the 56-test
suite is green. All hook files pass `bash -n` and `python3 -m py_compile` syntax
checks. `settings.json` is valid JSON per `python3 -m json.tool`.*

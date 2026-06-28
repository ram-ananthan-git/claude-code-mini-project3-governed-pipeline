# /commit — Smart Commit Message Generator

## Purpose

Read `git diff --staged`, understand what the changes actually do, and produce
a conventional-commit message that is accurate, traceable to REQ-IDs, and
consistent with the project's commit history. Then run safety checks and
execute the commit.

## When to use

- After staging files with `git add` and before running `git commit`
- Instead of writing a commit message by hand
- Whenever you want the commit body to include REQ-ID references automatically

---

## Steps Claude should execute

### 1. Understand what is staged

```bash
git status
git diff --staged
git diff --staged --stat
```

Read the full diff. Identify:
- Which files changed (src/, tests/, docs/, .claude/, config)
- What behaviour was added, removed, or modified
- Which REQ-IDs appear in the changed code
- Whether this is a new feature, bugfix, refactor, test addition, or chore

### 2. Run safety checks — stop if any fail

```bash
# Check 1: secrets in staged diff
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
    print(f"BLOCKED: secrets in staged diff: {hits}")
    raise SystemExit(1)
print("Secret scan: clean")
EOF

# Check 2: test suite must be green before committing
pytest -q --tb=line
```

**If either check fails: stop immediately. Do not generate a message. Do not commit.**

### 3. Load recent commit history for style matching

```bash
git log --oneline -10
```

Note the project's established `type(scope): description` patterns and the
level of detail in commit bodies. Match that style.

### 4. Generate the commit message

Using the diff from step 1, construct a message following this format:

```
<type>(<scope>): <imperative description, ≤ 72 chars>

<body — one bullet per logical change, each starting with "-">
- REQ-SHORT-XXX: <what this change does for this requirement>
- REQ-SHORT-YYY: <what this change does for this requirement>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**Type selection:**

| Type | When |
|------|------|
| `feat` | New behaviour visible to a caller (endpoint, field, status code) |
| `fix` | Corrects wrong behaviour traceable to a failing test or REQ-ID |
| `test` | Test additions or changes only — no src/ changes |
| `refactor` | Internal restructure with no behaviour change; same tests pass |
| `docs` | Documentation, CLAUDE.md, specs/, prompts/ only |
| `chore` | Hooks, settings, CI config, dependency changes |

**Scope selection:** use the most specific module or directory that encompasses
the change: `router`, `store`, `models`, `limiter`, `tests`, `hooks`, `spec`,
`docs`. Use `*` only if more than two scopes are touched.

**Description:** imperative present tense ("add", "fix", "remove"), no trailing
period, ≤ 72 chars. Describe the *what*, not the *how*.

**Body bullets:** one bullet per REQ-ID addressed. Pull the REQ-ID and its
description from the comments in the staged files. If no REQ-IDs are
referenced (e.g., a docs-only change), omit the body entirely.

### 5. Execute the commit

```bash
git commit -m "$(cat <<'COMMITMSG'
<generated message here>
COMMITMSG
)"
```

### 6. Confirm and show result

```bash
git log --oneline -3
git show --stat HEAD
```

---

## Expected output

Before committing, print the proposed message for the user to read:

```
## Proposed commit message

feat(router): return 410 Gone for expired short links

- REQ-SHORT-008: expired links now return 410 instead of 404
- REQ-SHORT-009: expiry timestamp checked on every redirect

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

---
Proceed? (committing now)
```

After committing:

```
## Committed

[main a1b2c3d] feat(router): return 410 Gone for expired short links
 2 files changed, 18 insertions(+), 3 deletions(-)

Next: run /ship to tag a release, or push the branch for review.
```

---

## Safety checks

| Check | On failure |
|-------|-----------|
| Secret in staged diff | Hard stop — print location, do not commit |
| Test suite red | Hard stop — list failing tests, do not commit |
| No files staged | Stop — remind user to `git add` first |
| All staged files are in `docs/` or `.claude/` | Use `docs` or `chore` type, skip REQ-ID body |

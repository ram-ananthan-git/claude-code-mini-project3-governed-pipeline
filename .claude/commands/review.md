# /review — AI-First Code Review

## Purpose

Review staged changes against the rules and conventions in `CLAUDE.md`. Claude
reads the diff, loads every contribution rule, then reasons about violations,
test gaps, and code quality — producing a structured finding report with
severity labels.

## When to use

- Before opening a PR or requesting peer review
- After implementing a new feature or bugfix
- Whenever `git diff --staged` is non-empty and you want a confidence check
- As the first gate in `/ship`

---

## Steps Claude should execute

### 1. Load the standard

```bash
cat CLAUDE.md
```

Read and internalize every rule in CLAUDE.md. The sections that matter most for
review are: **Contribution rules**, **Testing conventions**, **Allowed tools**,
and **Key spec references**. These are the ground truth this review checks
against.

### 2. Capture what changed

```bash
git diff --staged
git diff --staged --name-only
git status
```

If nothing is staged, fall back to:

```bash
git diff HEAD
git diff HEAD --name-only
```

Read the full content of each changed file — not just the diff lines — so
context around each change is visible.

### 3. Check contribution rules from CLAUDE.md

Run each rule mechanically before the AI reasoning pass:

```bash
# Rule 1: every changed src/ file must reference a REQ-ID
python3 - <<'EOF'
import subprocess, re, pathlib

result = subprocess.run(
    ["git", "diff", "--staged", "--name-only"], capture_output=True, text=True
)
changed = [f for f in result.stdout.splitlines()
           if f.startswith("src/") and f.endswith(".py")]

if not changed:
    print("No src/ files staged — REQ-ID rule N/A")
else:
    missing = [f for f in changed
               if pathlib.Path(f).exists()
               and not re.search(r"REQ-SHORT-\d+", pathlib.Path(f).read_text())]
    if missing:
        print("RULE VIOLATION — src/ files with no REQ-ID trace:")
        for f in missing:
            print(f"  {f}")
    else:
        print(f"OK — all {len(changed)} changed src/ files have REQ-ID traces")
EOF

# Rule 2: no hardcoded secrets anywhere in staged diff
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
hits = [(label, re.search(p, diff).group(0)[:40])
        for p, label in PATTERNS if re.search(p, diff)]
if hits:
    print("SECRET DETECTED in staged diff — DO NOT COMMIT:")
    for label, snippet in hits:
        print(f"  [{label}] {snippet}...")
else:
    print("OK — no secrets in staged diff")
EOF

# Rule 3: check testing conventions (naming, no requests import in tests)
python3 - <<'EOF'
import subprocess, pathlib, re

result = subprocess.run(
    ["git", "diff", "--staged", "--name-only"], capture_output=True, text=True
)
test_files = [f for f in result.stdout.splitlines()
              if f.startswith("tests/") and f.endswith(".py")]

for tf in test_files:
    if not pathlib.Path(tf).exists():
        continue
    text = pathlib.Path(tf).read_text()
    if re.search(r'^import requests', text, re.MULTILINE):
        print(f"RULE VIOLATION — {tf}: uses `requests`; must use TestClient")
    if not re.search(r'# (REQ-SHORT|SCN)-', text):
        print(f"WARNING — {tf}: no REQ-SHORT-XXX or SCN-XXX trace comments found")
EOF
```

### 4. Run the test suite

```bash
pytest -q --tb=short
```

If the suite is red, record which tests fail. A red baseline is a BLOCKER
regardless of what the diff looks like — changes must not break existing tests.

### 5. Reason about the diff

With the CLAUDE.md rules and diff both loaded, evaluate:

**Spec compliance** — do the changes implement what the relevant REQ-IDs
describe? Are return codes, field names, and error shapes consistent with
`specs/url-shortener.yaml`?

**Correctness** — logic errors, off-by-ones, unhandled exception paths,
race conditions in the in-memory store, missing `None` guards.

**Quality** — is naming consistent with the rest of the file? Dead code?
Unnecessary complexity? Inline comments that describe *what* instead of *why*?

**Test coverage** — for each behaviour introduced or changed, is there a test
that would catch a regression? Are the Given/When/Then assertions tight enough
to fail on the wrong status code?

---

## Expected output

Produce this exact structure after running all steps above:

```
## /review — <YYYY-MM-DD>

### Safety (auto-checks)
- [OK/BLOCKED] Secret scan
- [OK/VIOLATION] REQ-ID traces in src/
- [OK/VIOLATION] Testing conventions

### Test suite
- [PASS/FAIL] N tests — list any failures

### Spec Compliance
- [BLOCKER] ...
- [MAJOR]   ...
- [MINOR]   ...

### Correctness
- [BLOCKER] ...
- [MAJOR]   ...

### Quality
- [MINOR]   ...
- [SUGGESTION] ...

### Test Coverage
- [MAJOR]   <behaviour> has no test exercising <path>
- [MINOR]   ...

---
Summary: X blockers · Y majors · Z minors
Verdict: APPROVE  /  REQUEST CHANGES  /  BLOCKED (fix before proceeding)
```

**Verdict rules:**
- `BLOCKED` — any secret detected OR test suite red. Stop. Do not proceed.
- `REQUEST CHANGES` — any BLOCKER or MAJOR finding present
- `APPROVE` — zero BLOCKERs and MAJORs (minors and suggestions are fine to merge)

---

## Safety checks

| Check | On failure |
|-------|-----------|
| Secret detected in staged diff | Hard stop — do not commit under any circumstances |
| Test suite red | Hard stop — fix failures before continuing |
| REQ-ID missing from changed src/ file | MAJOR finding, blocks approval |
| `requests` import in test file | MAJOR finding, blocks approval |
| No test for a changed code path | MAJOR finding, blocks approval |

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

Produce a brief Gate 1 summary:
```
Gate 1 — Review: PASS / FAIL
  Secret scan: OK / BLOCKED
  REQ-ID traces: OK / VIOLATION (list files)
  Review verdict: APPROVE / REQUEST CHANGES
```

---

### Gate 2 — Test generation

Run the full `/test-gen` sequence:

```bash
# Find coverage gaps
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

# Run the full test suite
pytest -q --tb=short
```

If coverage gaps exist, generate tests now (follow `/test-gen` instructions).
Re-run `pytest -q` after generation and confirm it is green.

**If Gate 2 fails** (suite red after test generation): stop, list failures,
do not proceed to Gate 3.

```
Gate 2 — Tests: PASS / FAIL
  Coverage gaps filled: N new tests generated  (or "none needed")
  Suite result: N passed / list failures
```

---

### Gate 3 — Commit

Run the full `/commit` sequence to generate and execute the commit:

```bash
# Show what will be committed
git status
git log --oneline -5
```

Generate a conventional-commit message from the staged diff (see `/commit`
for the full generation instructions). Execute the commit.

```
Gate 3 — Commit: PASS / FAIL
  Message: <type>(<scope>): <description>
  REQ-IDs in body: REQ-SHORT-XXX, ...
  Commit SHA: <short hash>
```

---

### Gate 4 — Create PR

```bash
# Confirm the branch exists on remote (push if needed)
git branch --show-current
git status
```

Push the current branch to origin:

```bash
git push -u origin HEAD
```

Then create a pull request using `gh`:

```bash
gh pr create \
  --title "<type>(<scope>): <same description as commit>" \
  --body "$(cat <<'PRBODY'
## Summary

- <bullet: what this PR does, one sentence>
- REQ-SHORT-XXX: <requirement addressed>
- REQ-SHORT-YYY: <requirement addressed>

## Test plan

- [ ] `pytest -q` passes (N tests)
- [ ] Scenario tests pass: `pytest tests/test_scenarios.py -v`
- [ ] No secrets in diff (checked by `/ship`)
- [ ] REQ-ID traces present in all changed `src/` files

## Review checklist (for reviewer)

- [ ] Spec compliance: changes match `specs/url-shortener.yaml`
- [ ] No `requests` import in test files (use TestClient)
- [ ] Commit message follows conventional commits format

🤖 Generated with [Claude Code](https://claude.ai/code)
PRBODY
)"
```

```
Gate 4 — PR: PASS / FAIL
  PR URL: https://github.com/<owner>/<repo>/pull/<N>
```

---

## Expected output

After all four gates complete:

```
## /ship complete

Gate 1 — Review:   PASS  (0 blockers, 0 majors)
Gate 2 — Tests:    PASS  (2 new tests generated, 56 passed)
Gate 3 — Commit:   PASS  feat(router): return 410 for expired links [a1b2c3d]
Gate 4 — PR:       PASS  https://github.com/owner/repo/pull/42

Ready for review. Assign a reviewer or merge when approved.
```

If any gate fails, stop at that gate and show:

```
## /ship stopped at Gate N

Gate N — <Name>: FAIL
  Reason: <specific failure>
  Fix:    <what to do>

Gates 1–N-1 completed successfully. Resume from Gate N after fixing.
```

---

## Safety checks

| Check | Gate | On failure |
|-------|------|-----------|
| Secret in staged diff | 1 | Hard stop — do not commit or push |
| REQ-ID missing from changed src/ file | 1 | Stop at Gate 1, list files |
| Review verdict is REQUEST CHANGES | 1 | Stop at Gate 1, list findings |
| Test suite red after test-gen | 2 | Stop at Gate 2, list failures |
| `git push` fails (e.g. protected branch) | 4 | Report error, suggest `gh pr create` from local |
| `gh` CLI not installed | 4 | Print PR body to stdout with instructions to open manually |

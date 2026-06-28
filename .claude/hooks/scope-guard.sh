#!/usr/bin/env bash
# PreToolUse hook — enforces allowed edit scope for Write and Edit tool calls.
#
# ALLOWED directories (writes permitted):
#   .claude/   docs/   src/   tests/   specs/
#   Root-level files: CLAUDE.md, REPORT.md, README.md, pyproject.toml, etc.
#
# BLOCKED directories (writes always rejected):
#   .git/         — git internals; corruption is hard to recover
#   .env          — environment file with real secrets
#   node_modules/ — dependency tree; never edited directly
#   venv/         — Python virtualenv managed by pip
#   .venv/        — Python virtualenv (alternate name)
#   __pycache__/  — compiled bytecache; auto-generated
#
# Also blocks any write whose resolved absolute path escapes the project root.

set -euo pipefail

# ── Resolve project root ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Read and parse payload via Python ────────────────────────────────────────
# Capture stdin once; pass as argument to avoid heredoc stdin-exhaustion.
PAYLOAD="$(cat)"

# Extract tool_name and file_path in a single Python call
read -r TOOL_NAME FILE_PATH < <(python3 - "$PAYLOAD" <<'PYEOF'
import json, sys
try:
    d = json.loads(sys.argv[1])
    tool  = d.get("tool_name", "")
    fpath = d.get("tool_input", {}).get("file_path", "")
    print(tool, fpath)
except Exception:
    print("", "")
PYEOF
)

# Only intercept Write and Edit
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
    exit 0
fi

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# ── Resolve to absolute, normalised path ─────────────────────────────────────
if [[ "$FILE_PATH" != /* ]]; then
    FILE_PATH="$PROJECT_ROOT/$FILE_PATH"
fi

CANONICAL="$(python3 -c "import os,sys; print(os.path.normpath(sys.argv[1]))" "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")"

# ── Helper: emit a block decision and exit ───────────────────────────────────
block() {
    local reason="$1"
    python3 -c "
import json, sys
print(json.dumps({'decision': 'block', 'reason': '[scope-guard] BLOCKED: ' + sys.argv[1]}))
" "$reason"
    exit 0
}

# ── 1. Reject paths that escape the project root ─────────────────────────────
if [[ "$CANONICAL" != "$PROJECT_ROOT"* ]]; then
    block "write to \"$CANONICAL\" is outside the project root ($PROJECT_ROOT)."
fi

# Compute path relative to project root for subsequent pattern checks
REL="${CANONICAL#$PROJECT_ROOT/}"

# ── 2. Blocked directory prefixes ────────────────────────────────────────────
BLOCKED_PREFIXES=(
    ".git/"
    "node_modules/"
    "venv/"
    ".venv/"
    "__pycache__/"
    "dist/"
    "build/"
    ".eggs/"
    "*.egg-info/"
)

for prefix in "${BLOCKED_PREFIXES[@]}"; do
    # Use glob-style prefix matching: strip trailing wildcard for plain prefix check
    check_prefix="${prefix%\*}"
    if [[ "$REL" == $check_prefix* ]]; then
        block "writes to $prefix are not allowed (managed directory). Path: $CANONICAL"
    fi
done

# ── 3. Blocked specific files ─────────────────────────────────────────────────
BLOCKED_FILES=(
    ".env"
    ".env.local"
    ".env.production"
    ".env.staging"
    ".envrc"
)

for blocked_file in "${BLOCKED_FILES[@]}"; do
    if [[ "$REL" == "$blocked_file" ]]; then
        block "writes to $blocked_file are not allowed. Store secrets in a secrets manager, not in .env files."
    fi
done

# ── 4. Allowed directory and file enforcement ─────────────────────────────────
# Anything inside the project root that is NOT in a blocked path above is
# already allowed by falling through to exit 0. The explicit ALLOWED list
# below is logged for transparency but does not hard-block unknown paths —
# developers may add new top-level directories (e.g. scripts/, config/).
#
# To make the allowed list strict (block everything not explicitly listed),
# uncomment the section below.

# ALLOWED_PREFIXES=(
#     ".claude/"
#     "docs/"
#     "src/"
#     "tests/"
#     "specs/"
#     "prompts/"
# )
# ALLOWED_ROOT_FILES=(
#     "CLAUDE.md" "REPORT.md" "README.md"
#     "pyproject.toml" "setup.py" "setup.cfg"
#     "requirements.txt" "requirements-dev.txt"
#     ".gitignore" ".gitattributes"
# )
#
# in_allowed=false
# for prefix in "${ALLOWED_PREFIXES[@]}"; do
#     [[ "$REL" == $prefix* ]] && in_allowed=true && break
# done
# if ! $in_allowed; then
#     for root_file in "${ALLOWED_ROOT_FILES[@]}"; do
#         [[ "$REL" == "$root_file" ]] && in_allowed=true && break
#     done
# fi
# if ! $in_allowed; then
#     block "\"$REL\" is outside the allowed edit scope (.claude/, docs/, src/, tests/, specs/). Add it to ALLOWED_PREFIXES in scope-guard.sh if intentional."
# fi

exit 0

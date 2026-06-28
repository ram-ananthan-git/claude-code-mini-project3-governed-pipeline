#!/usr/bin/env bash
# UserPromptSubmit hook — logs every user prompt to .claude/audit/prompts.jsonl
#
# Fires before Claude processes each message, giving a full record of what was
# asked in addition to what tools were called. Enables audit queries like:
#   "what prompts triggered the secret-scan block on 2026-06-28?"
#
# Record schema:
#   {
#     "timestamp":  "2026-06-28T12:00:01Z",
#     "session_id": "a1b2c3d4",
#     "type":       "user_prompt",
#     "prompt":     "first 500 chars of the user message",
#     "length":     1234
#   }

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AUDIT_DIR="$PROJECT_ROOT/.claude/audit"
mkdir -p "$AUDIT_DIR"

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PAYLOAD="$(cat)"

python3 - "$TIMESTAMP" "$AUDIT_DIR/prompts.jsonl" "$PAYLOAD" << 'PYEOF'
import json, sys, os, hashlib, subprocess

timestamp    = sys.argv[1]
prompts_file = sys.argv[2]
payload_str  = sys.argv[3] if len(sys.argv) > 3 else ""

try:
    payload = json.loads(payload_str)
except Exception:
    sys.exit(0)

# UserPromptSubmit payload has a top-level "prompt" key
prompt_text = payload.get("prompt", "")
if not prompt_text:
    sys.exit(0)

# Stable session ID
try:
    repo_path = subprocess.check_output(
        ["git", "-C", os.path.dirname(prompts_file), "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL, text=True,
    ).strip()
except Exception:
    repo_path = os.path.dirname(prompts_file)

session_id = hashlib.sha1(repo_path.encode()).hexdigest()[:8]

record = {
    "timestamp":  timestamp,
    "session_id": session_id,
    "type":       "user_prompt",
    "prompt":     prompt_text[:500],  # truncate long prompts
    "length":     len(prompt_text),
}

with open(prompts_file, "a") as f:
    f.write(json.dumps(record) + "\n")
PYEOF

exit 0

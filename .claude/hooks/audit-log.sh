#!/usr/bin/env bash
# PostToolUse hook — appends a structured audit record for every tool call.
#
# Output files:
#   .claude/audit/audit.jsonl   — one JSON line per tool call
#   .claude/audit/prompts.jsonl — one JSON line per Bash command (command text preserved)
#
# Record schema (audit.jsonl):
#   {
#     "timestamp":     "2026-06-28T12:00:00Z",   // UTC ISO-8601
#     "session_id":    "a1b2c3d4",               // SHA-1[:8] of project root path
#     "tool":          "Write",                  // tool_name from payload
#     "file_path":     "src/router.py",          // for Write/Edit; empty otherwise
#     "input_summary": "content=...120 chars",   // truncated input description
#     "outcome":       "success" | "error",      // from tool_response.is_error
#     "hook_decision": "allowed" | "blocked"     // whether a PreToolUse hook blocked it
#   }

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AUDIT_DIR="$PROJECT_ROOT/.claude/audit"
mkdir -p "$AUDIT_DIR"

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Capture the full stdin payload into a variable first.
# CRITICAL: do NOT use a heredoc (<<'PYEOF') after this — it would replace
# stdin and the Python script would read the heredoc source, not the payload.
# Pass the payload as a positional argument instead.
PAYLOAD="$(cat)"

python3 - "$TIMESTAMP" "$AUDIT_DIR" "$PAYLOAD" << 'PYEOF'
import json
import sys
import os
import hashlib

timestamp = sys.argv[1]
audit_dir = sys.argv[2]
# argv[3] is the raw JSON payload string
payload_str = sys.argv[3] if len(sys.argv) > 3 else ""

audit_file   = os.path.join(audit_dir, "audit.jsonl")
prompts_file = os.path.join(audit_dir, "prompts.jsonl")

try:
    payload = json.loads(payload_str)
except Exception:
    # Unparseable payload — write a minimal error record and exit cleanly
    record = {"timestamp": timestamp, "tool": "unknown", "outcome": "parse_error"}
    with open(audit_file, "a") as f:
        f.write(json.dumps(record) + "\n")
    sys.exit(0)

tool_name  = payload.get("tool_name", "unknown")
tool_input = payload.get("tool_input") or {}

# ── Build input summary ───────────────────────────────────────────────────────
summary_parts = []
for k, v in list(tool_input.items())[:4]:
    sv = str(v)[:120].replace("\n", "\\n")
    summary_parts.append(f"{k}={sv}")
input_summary = "; ".join(summary_parts)[:400]

# Extract file_path for Write/Edit calls — useful for querying the log
file_path = tool_input.get("file_path", "")

# ── Determine outcome ─────────────────────────────────────────────────────────
tool_response = payload.get("tool_response") or {}
if isinstance(tool_response, dict) and tool_response.get("is_error"):
    outcome = "error"
else:
    outcome = "success"

# ── Detect whether a hook blocked this call ───────────────────────────────────
# Claude Code sets hook_results in the payload when a PreToolUse hook ran.
hook_results = payload.get("hook_results") or []
hook_decision = "allowed"
for hr in hook_results:
    if isinstance(hr, dict) and hr.get("decision") == "block":
        hook_decision = "blocked"
        break

# ── Stable session ID: SHA-1[:8] of project root path ────────────────────────
try:
    import subprocess
    repo_path = subprocess.check_output(
        ["git", "-C", audit_dir, "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL, text=True
    ).strip()
except Exception:
    repo_path = os.path.dirname(audit_dir)

session_id = hashlib.sha1(repo_path.encode()).hexdigest()[:8]

# ── Write audit record ────────────────────────────────────────────────────────
audit_record = {
    "timestamp":     timestamp,
    "session_id":    session_id,
    "tool":          tool_name,
    "file_path":     file_path,
    "input_summary": input_summary,
    "outcome":       outcome,
    "hook_decision": hook_decision,
}
with open(audit_file, "a") as fh:
    fh.write(json.dumps(audit_record) + "\n")

# ── Write prompts record for Bash calls ──────────────────────────────────────
if tool_name == "Bash":
    command = tool_input.get("command", "")[:600]
    prompt_record = {
        "timestamp":     timestamp,
        "session_id":    session_id,
        "type":          "bash_command",
        "command":       command,
        "outcome":       outcome,
        "hook_decision": hook_decision,
    }
    with open(prompts_file, "a") as fh:
        fh.write(json.dumps(prompt_record) + "\n")

PYEOF

exit 0

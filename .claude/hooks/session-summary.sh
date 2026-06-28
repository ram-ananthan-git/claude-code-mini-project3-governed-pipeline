#!/usr/bin/env bash
# Stop hook — writes a session summary to .claude/audit/sessions.jsonl when
# the Claude Code session ends.
#
# Counts tool calls, blocked operations, and files written during the session,
# giving a lightweight "what happened this session" record without storing
# full message history.
#
# Record schema:
#   {
#     "timestamp":        "2026-06-28T12:30:00Z",   // session end time
#     "session_id":       "a1b2c3d4",
#     "type":             "session_summary",
#     "total_tool_calls": 47,
#     "blocked_calls":    2,
#     "bash_commands":    18,
#     "files_written":    6,
#     "unique_files":     ["src/router.py", ...],
#     "stop_reason":      "end_turn" | "user_interrupt" | "max_turns" | "unknown"
#   }

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AUDIT_DIR="$PROJECT_ROOT/.claude/audit"
mkdir -p "$AUDIT_DIR"

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PAYLOAD="$(cat)"

python3 - "$TIMESTAMP" "$AUDIT_DIR" "$PAYLOAD" << 'PYEOF'
import json, sys, os, hashlib, subprocess

timestamp   = sys.argv[1]
audit_dir   = sys.argv[2]
payload_str = sys.argv[3] if len(sys.argv) > 3 else ""

audit_file    = os.path.join(audit_dir, "audit.jsonl")
sessions_file = os.path.join(audit_dir, "sessions.jsonl")

# Stable session ID
try:
    repo_path = subprocess.check_output(
        ["git", "-C", audit_dir, "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL, text=True,
    ).strip()
except Exception:
    repo_path = os.path.dirname(audit_dir)

session_id = hashlib.sha1(repo_path.encode()).hexdigest()[:8]

# Extract stop reason from Stop hook payload
try:
    payload = json.loads(payload_str)
    stop_reason = payload.get("stop_reason", "unknown")
except Exception:
    stop_reason = "unknown"

# Tally this session's records from audit.jsonl
total = blocked = bash = writes = 0
unique_files = []

if os.path.exists(audit_file):
    with open(audit_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("session_id") != session_id:
                continue
            total += 1
            if rec.get("hook_decision") == "blocked" or rec.get("outcome") == "error":
                blocked += 1
            if rec.get("tool") == "Bash":
                bash += 1
            if rec.get("tool") in ("Write", "Edit") and rec.get("file_path"):
                fp = rec["file_path"]
                writes += 1
                if fp not in unique_files:
                    unique_files.append(fp)

record = {
    "timestamp":        timestamp,
    "session_id":       session_id,
    "type":             "session_summary",
    "total_tool_calls": total,
    "blocked_calls":    blocked,
    "bash_commands":    bash,
    "files_written":    writes,
    "unique_files":     unique_files[:20],   # cap at 20 for readability
    "stop_reason":      stop_reason,
}

with open(sessions_file, "a") as f:
    f.write(json.dumps(record) + "\n")

# Print a brief human-readable summary to terminal
print(f"\n── Session summary ({'session ' + session_id}) ──────────────────────────")
print(f"   Tool calls : {total}  ({blocked} blocked)")
print(f"   Bash cmds  : {bash}")
print(f"   Files written: {writes}  {unique_files[:5]}")
print(f"   Stop reason: {stop_reason}")
print(f"   Logged to  : {sessions_file}")
print()
PYEOF

exit 0

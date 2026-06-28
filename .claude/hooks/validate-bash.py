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

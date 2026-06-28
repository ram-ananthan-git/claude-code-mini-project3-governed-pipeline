#!/usr/bin/env python3
"""
PreToolUse hook — scans file content being written for secrets and credentials.

Fires on Write and Edit tool calls. Reads the Claude Code hook payload from stdin,
inspects the file path and new content for credential patterns, and blocks the
write when a secret is found.

Severity levels:
  block — hard stop, write is rejected
  warn  — write is allowed but a warning is surfaced (for ambiguous patterns)
"""
import json
import os
import re
import sys

# ── Secret patterns ───────────────────────────────────────────────────────────
# Each entry: (regex, human label, severity)

SECRET_PATTERNS = [
    # Generic named assignments — catches config files and source code
    (r'(?i)\bapi[_-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}["\']?',
     "API key assignment", "block"),
    (r'(?i)\bsecret[_-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}["\']?',
     "Secret key assignment", "block"),
    (r'(?i)\b(access[_-]?token|auth[_-]?token|bearer[_-]?token)\s*[=:]\s*["\']?[A-Za-z0-9_\-\.]{20,}["\']?',
     "Auth/bearer token", "block"),
    (r'(?i)\bpassword\s*[=:]\s*["\'][^"\']{6,}["\']',
     "Hardcoded password", "block"),
    (r'(?i)\bpasswd\s*[=:]\s*["\'][^"\']{6,}["\']',
     "Hardcoded password (passwd)", "block"),

    # AWS
    (r'AKIA[0-9A-Z]{16}',
     "AWS Access Key ID", "block"),
    (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}["\']?',
     "AWS Secret Access Key", "block"),
    (r'(?i)aws[_-]?session[_-]?token\s*[=:]\s*["\']?[A-Za-z0-9/+=]{100,}["\']?',
     "AWS Session Token", "block"),

    # Anthropic / OpenAI / common AI providers
    (r'sk-ant-[A-Za-z0-9\-_]{40,}',
     "Anthropic API key", "block"),
    (r'sk-[A-Za-z0-9]{48,}',
     "OpenAI-style API key", "block"),

    # GitHub / GitLab / Bitbucket
    (r'ghp_[A-Za-z0-9]{36,}',
     "GitHub personal access token", "block"),
    (r'gho_[A-Za-z0-9]{36,}',
     "GitHub OAuth token", "block"),
    (r'ghs_[A-Za-z0-9]{36,}',
     "GitHub Actions secret", "block"),
    (r'glpat-[A-Za-z0-9\-_]{20,}',
     "GitLab personal access token", "block"),
    (r'BBDC-[A-Za-z0-9]{32,}',
     "Bitbucket Data Center token", "block"),

    # Stripe
    (r'sk_live_[A-Za-z0-9]{24,}',
     "Stripe live secret key", "block"),
    (r'rk_live_[A-Za-z0-9]{24,}',
     "Stripe live restricted key", "block"),
    (r'sk_test_[A-Za-z0-9]{24,}',
     "Stripe test secret key", "warn"),  # test keys are lower risk but still bad practice

    # Slack
    (r'xoxb-[0-9A-Za-z\-]{40,}',
     "Slack bot token", "block"),
    (r'xoxp-[0-9A-Za-z\-]{40,}',
     "Slack user token", "block"),
    (r'xoxs-[0-9A-Za-z\-]{40,}',
     "Slack session token", "block"),
    (r'xoxa-[0-9A-Za-z\-]{40,}',
     "Slack app-level token", "block"),
    (r'https://hooks\.slack\.com/services/[A-Za-z0-9/]+',
     "Slack webhook URL", "block"),

    # PEM / private key material
    (r'-----BEGIN\s+(RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
     "Private key (PEM block)", "block"),
    (r'-----BEGIN CERTIFICATE-----',
     "X.509 certificate (may contain key)", "warn"),

    # JWT — three base64url segments separated by dots (loose check)
    (r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}',
     "JWT token", "block"),

    # Database connection strings with embedded credentials
    (r'(?i)(postgres|postgresql|mysql|mariadb|mongodb|redis|mssql|sqlserver)'
     r'://[^:@\s]{1,}:[^:@\s]{4,}@',
     "Database URL with embedded credentials", "block"),

    # Generic .env-style high-entropy assignments (warn — could be test values)
    (r'(?m)^[A-Z][A-Z0-9_]{3,}\s*=\s*["\']?[A-Za-z0-9+/=_\-]{32,}["\']?\s*$',
     ".env-style high-entropy value", "warn"),
]

# ── Exempt paths ──────────────────────────────────────────────────────────────
# Prefixes relative to project root. Files under these paths are not scanned.
# Rationale: test fixtures use fake credentials by convention; audit logs and
# this hook file itself would produce false positives.

EXEMPT_PREFIXES = [
    ".claude/hooks/check-secrets.py",   # this file — pattern strings would match
    ".claude/audit/",                   # audit log entries may echo blocked content
    ".git/",                            # git internals
]

# File extensions that are binary or non-code — skip to avoid false positives
EXEMPT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".lock",  # lockfiles contain package hashes, not secrets
    ".jsonl",  # audit logs
    ".pyc", ".pyo",
}


def relative_path(file_path: str) -> str:
    """Return a path relative to cwd, normalised."""
    cwd = os.getcwd()
    # Strip leading cwd prefix
    norm = os.path.normpath(file_path)
    if norm.startswith(cwd + os.sep):
        norm = norm[len(cwd) + 1:]
    return norm


def is_exempt(file_path: str) -> bool:
    if not file_path:
        return True
    _, ext = os.path.splitext(file_path)
    if ext.lower() in EXEMPT_EXTENSIONS:
        return True
    rel = relative_path(file_path)
    return any(rel == prefix or rel.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def scan(content: str) -> list[dict]:
    findings = []
    for pattern, label, severity in SECRET_PATTERNS:
        for match in re.finditer(pattern, content, re.MULTILINE):
            raw = match.group(0)
            # Redact everything after the first 8 chars of the matched value
            safe = raw[:8] + "***REDACTED***"
            findings.append({"label": label, "severity": severity, "matched": safe})
    return findings


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if is_exempt(file_path):
        sys.exit(0)

    # Write uses "content"; Edit uses "new_string"
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if not content:
        sys.exit(0)

    findings = scan(content)
    if not findings:
        sys.exit(0)

    blockers = [f for f in findings if f["severity"] == "block"]
    warnings = [f for f in findings if f["severity"] == "warn"]

    if blockers:
        labels = "; ".join(f"{f['label']} ({f['matched']})" for f in blockers)
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"[check-secrets] BLOCKED: credential(s) detected in {file_path}:\n"
                f"  {labels}\n"
                "Move secrets to environment variables or a secrets manager. "
                "Use placeholder values (e.g. sk-test-XXXX) in source and docs."
            ),
        }))
        sys.exit(0)

    if warnings:
        labels = "; ".join(f"{f['label']} ({f['matched']})" for f in warnings)
        print(json.dumps({
            "decision": "approve",
            "reason": (
                f"[check-secrets] WARNING: high-entropy value(s) in {file_path}: {labels}. "
                "Confirm these are not real credentials before committing."
            ),
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()

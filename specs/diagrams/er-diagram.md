# Entity-Relationship Diagram — URL Shortener Service

> The service uses in-memory Python dicts, not a relational database.
> This diagram represents the **logical data model** — the entities, their
> fields, and the relationships between them as they exist at runtime.

---

## Core Data Model

```mermaid
erDiagram

    LINK_RECORD {
        string  short_code   PK  "8 alphanumeric chars — REQ-SHORT-002"
        string  original_url     "validated http/https URI — REQ-SHORT-012, REQ-SHORT-013"
        string  short_url        "base_url + '/' + short_code — REQ-SHORT-001"
        int     clicks           "incremented on each redirect — REQ-SHORT-006"
    }

    CODE_INDEX {
        string  short_code   PK  "lookup key: code → LINK_RECORD"
    }

    URL_INDEX {
        string  original_url PK  "reverse lookup key: url → short_code — REQ-SHORT-010"
        string  short_code       "FK to LINK_RECORD.short_code"
    }

    RATE_LIMIT_BUCKET {
        string  ip_address   PK  "client IP (or X-Forwarded-For) — NFR-RL-003"
        int     request_count    "number of POST /shorten calls in window"
        float   window_start     "Unix timestamp of window open — NFR-RL-001"
    }

    CODE_INDEX    ||--|| LINK_RECORD      : "stores"
    URL_INDEX     }o--|| LINK_RECORD      : "reverse-maps to"
    RATE_LIMIT_BUCKET |o--o{ LINK_RECORD  : "governs creation of"
```

---

## Field-Level Notes

| Entity | Field | Type | Constraint | Spec ref |
|---|---|---|---|---|
| `LINK_RECORD` | `short_code` | `str` | exactly 8 chars, `[a-zA-Z0-9]` | REQ-SHORT-002 |
| `LINK_RECORD` | `original_url` | `str` | scheme must be http/https, max 2048 chars | REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014 |
| `LINK_RECORD` | `short_url` | `str` | derived: `{base_url}/{short_code}` | REQ-SHORT-001 |
| `LINK_RECORD` | `clicks` | `int` | ≥ 0, default 0, monotonically increasing | REQ-SHORT-006 |
| `URL_INDEX` | `original_url` | `str` | unique; enforces one code per URL | REQ-SHORT-010 |
| `RATE_LIMIT_BUCKET` | `request_count` | `int` | resets when `now - window_start ≥ 60 s` | NFR-RL-001 |
| `RATE_LIMIT_BUCKET` | `window_start` | `float` | Unix epoch seconds | NFR-RL-001 |

---

## Runtime Storage Layout

```mermaid
erDiagram

    IN_MEMORY_STORE {
        dict _store      "short_code (str) → LinkRecord"
        dict _url_index  "original_url (str) → short_code (str)"
        dict _rate_limit "ip_address (str) → RateLimitBucket"
    }

    IN_MEMORY_STORE ||--o{ LINK_RECORD       : "_store holds"
    IN_MEMORY_STORE ||--o{ URL_INDEX         : "_url_index holds"
    IN_MEMORY_STORE ||--o{ RATE_LIMIT_BUCKET : "_rate_limit holds"
```

### Key design decisions

- **Two parallel indexes** (`_store` + `_url_index`) give O(1) lookup in both
  directions: code→URL for redirect (REQ-SHORT-004) and URL→code for idempotent
  shorten (REQ-SHORT-010).
- **No shared mutable state between `LINK_RECORD` and `RATE_LIMIT_BUCKET`** —
  rate limiting is enforced before any store operation, so a rejected request
  never touches the link store.
- **No TTL or expiry fields** — not required by the current spec. A future
  `expires_at` column on `LINK_RECORD` would enable link expiry.

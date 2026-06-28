# Sequence Diagrams — URL Shortener Service

Participants used throughout:
- **Client** — API consumer (curl, app) or browser
- **RateLimiter** — in-process sliding-window middleware (NFR-RL-001)
- **Validator** — Pydantic model layer (NFR-VAL-001, NFR-VAL-002, NFR-VAL-003)
- **Router** — FastAPI route handlers
- **Store** — in-memory dict + reverse URL index

---

## 1. POST /shorten — New URL (REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant RL as RateLimiter
    participant V as Validator
    participant R as Router
    participant S as Store

    C->>RL: POST /shorten {"url": "https://example.com/long"}
    RL->>RL: check ip_counter < 60 / 60 s (NFR-RL-001)
    RL->>V: pass request

    V->>V: check url length ≤ 2048 (REQ-SHORT-014)
    V->>V: check scheme in {http, https} (REQ-SHORT-013)
    V->>V: parse URI structure (REQ-SHORT-012)
    V->>R: ShortenRequest(url=...)

    R->>S: lookup url in reverse index (REQ-SHORT-010)
    S-->>R: None (not found)
    R->>R: generate 8-char alphanumeric code (REQ-SHORT-002)
    R->>S: check code not already in store (REQ-SHORT-003)
    S-->>R: no collision
    R->>S: store {code → LinkRecord, url → code}
    S-->>R: ok
    R-->>C: 201 Created\n{short_code, short_url, original_url, clicks:0}
```

---

## 2. POST /shorten — Duplicate URL / Idempotent (REQ-SHORT-010)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant RL as RateLimiter
    participant V as Validator
    participant R as Router
    participant S as Store

    C->>RL: POST /shorten {"url": "https://example.com/long"}
    RL->>V: pass (within rate limit)
    V->>R: ShortenRequest validated

    R->>S: lookup url in reverse index (REQ-SHORT-010)
    S-->>R: existing code "abc12345"
    R->>S: fetch LinkRecord for "abc12345"
    S-->>R: LinkRecord{short_code, original_url, short_url, clicks}
    R-->>C: 200 OK\n{short_code:"abc12345", short_url, original_url, clicks}

    note over R,S: No new entry created — one record per URL
```

---

## 3. POST /shorten — Validation Failure (REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant RL as RateLimiter
    participant V as Validator
    participant R as Router

    C->>RL: POST /shorten {"url": "ftp://files.example.com"}
    RL->>V: pass (within rate limit)

    V->>V: check scheme in {http, https} (REQ-SHORT-013)
    note right of V: scheme "ftp" not allowed
    V-->>C: 422 Unprocessable Entity\n{detail:[{loc:[url], msg:"URL must use http or https scheme"}]}

    note over R: Router never reached — validation is pre-route
```

---

## 4. POST /shorten — Rate Limit Exceeded (REQ-SHORT-015, NFR-RL-001, NFR-RL-002)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant RL as RateLimiter

    loop 60 requests within 60 s
        C->>RL: POST /shorten {"url": "https://..."}
        RL->>RL: increment ip_counter
        RL-->>C: 201 / 200 OK
    end

    C->>RL: POST /shorten {"url": "https://..."} (61st)
    RL->>RL: ip_counter == 60 — window not reset (REQ-SHORT-015)
    RL-->>C: 429 Too Many Requests\nRetry-After: <seconds_remaining>\n{detail:"Rate limit exceeded. Try again in N seconds."}
```

---

## 5. GET /{code} — Successful Redirect (REQ-SHORT-004, REQ-SHORT-006)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as Router
    participant S as Store

    C->>R: GET /abc12345
    R->>S: lookup "abc12345" in store (REQ-SHORT-004)
    S-->>R: LinkRecord{original_url:"https://example.com", clicks:3}
    R->>S: increment clicks for "abc12345" (REQ-SHORT-006)
    S-->>R: clicks now 4
    R-->>C: 307 Temporary Redirect\nLocation: https://example.com

    note over C: Browser follows Location header automatically
    C->>C: navigate to https://example.com
```

---

## 6. GET /{code} — Code Not Found (REQ-SHORT-005)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as Router
    participant S as Store

    C->>R: GET /xxxxxxxx
    R->>S: lookup "xxxxxxxx" (REQ-SHORT-005)
    S-->>R: None
    R-->>C: 404 Not Found\n{"detail": "Short code not found"}
```

---

## 7. DELETE /{code} — Happy and Error Paths (REQ-SHORT-007, REQ-SHORT-008)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as Router
    participant S as Store

    note over C,S: Happy path — code exists
    C->>R: DELETE /del12345
    R->>S: lookup "del12345" (REQ-SHORT-007)
    S-->>R: found
    R->>S: remove {code, reverse-url entry}
    S-->>R: ok
    R-->>C: 204 No Content

    note over C,S: Error path — code missing
    C->>R: DELETE /missing1
    R->>S: lookup "missing1" (REQ-SHORT-008)
    S-->>R: None
    R-->>C: 404 Not Found\n{"detail": "Short code not found"}
```

---

## 8. GET /links — List All Mappings (REQ-SHORT-009)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as Router
    participant S as Store

    C->>R: GET /links
    R->>S: fetch all LinkRecords (REQ-SHORT-009)
    S-->>R: [LinkRecord, LinkRecord, ...]
    R-->>C: 200 OK\n[{short_code, original_url, short_url, clicks}, ...]
```

---

## 9. GET /healthz — Liveness Probe (REQ-SHORT-011)

```mermaid
sequenceDiagram
    autonumber
    participant P as Probe (k8s / load balancer)
    participant R as Router

    P->>R: GET /healthz
    R-->>P: 200 OK\n{"status": "ok"}
```

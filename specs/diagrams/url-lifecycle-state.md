# State Diagram — Short URL Lifecycle

---

## Top-Level Lifecycle

```mermaid
stateDiagram-v2
    direction LR

    [*] --> NonExistent : service starts\n(empty store)

    NonExistent --> Active      : POST /shorten — new URL\n→ 201 Created\n(REQ-SHORT-001, REQ-SHORT-002, REQ-SHORT-003)
    Active      --> NonExistent : DELETE /{code} — found\n→ 204 No Content\n(REQ-SHORT-007)

    NonExistent --> NonExistent : POST /shorten — validation fails\n→ 422 Unprocessable Entity\n(REQ-SHORT-012, REQ-SHORT-013, REQ-SHORT-014)
    NonExistent --> NonExistent : POST /shorten — rate limited\n→ 429 Too Many Requests\n(REQ-SHORT-015)
    NonExistent --> NonExistent : GET /{code} — not found\n→ 404 Not Found\n(REQ-SHORT-005)
    NonExistent --> NonExistent : DELETE /{code} — not found\n→ 404 Not Found\n(REQ-SHORT-008)

    Active --> Active           : POST /shorten — duplicate URL\n→ 200 OK (idempotent)\n(REQ-SHORT-010)
    Active --> Active           : GET /{code} — redirect\n→ 307 Temporary Redirect\nclicks++ (REQ-SHORT-004, REQ-SHORT-006)
```

---

## Active State — Click-Count Sub-States

```mermaid
stateDiagram-v2
    direction LR

    state Active {
        [*]      --> Clicks_0
        Clicks_0 --> Clicks_1 : GET /{code} (1st redirect)\nclicks = 1
        Clicks_1 --> Clicks_N : GET /{code} (2nd redirect)\nclicks = 2
        Clicks_N --> Clicks_N : GET /{code} (Nth redirect)\nclicks++

        state Clicks_0 { [*]: clicks == 0 }
        state Clicks_1 { [*]: clicks == 1 }
        state Clicks_N { [*]: clicks >= 2 }
    }

    note right of Active
        clicks is monotonically increasing.
        It is never decremented and resets
        only if the link is deleted and
        re-created (REQ-SHORT-006).
    end note
```

---

## Rate Limiter State (per IP address)

```mermaid
stateDiagram-v2
    direction LR

    [*]          --> Window_Open  : first POST /shorten from IP\n(NFR-RL-001)

    Window_Open  --> Window_Open  : request_count < 60\n→ allow, increment counter
    Window_Open  --> Window_Open  : request_count == 60\n→ 429 + Retry-After header\n(REQ-SHORT-015, NFR-RL-002)
    Window_Open  --> Window_Reset : 60 seconds elapsed\nwindow_start advances

    Window_Reset --> Window_Open  : next request arrives\nrequest_count = 1

    note right of Window_Open
        Keyed by client IP.
        X-Forwarded-For respected
        behind trusted proxy (NFR-RL-003).
    end note
```

---

## State Transition Table

| From state | Event | Guard | To state | HTTP response |
|---|---|---|---|---|
| `NonExistent` | `POST /shorten` | valid URL, under rate limit, URL is new | `Active` | 201 Created |
| `Active` | `POST /shorten` | valid URL, under rate limit, URL already mapped | `Active` (unchanged) | 200 OK |
| `NonExistent` or `Active` | `POST /shorten` | invalid URL (bad scheme / syntax / length) | unchanged | 422 Unprocessable Entity |
| `NonExistent` or `Active` | `POST /shorten` | rate limit exceeded for this IP | unchanged | 429 Too Many Requests |
| `Active` | `GET /{code}` | code exists | `Active` (clicks++) | 307 Temporary Redirect |
| `NonExistent` | `GET /{code}` | code not in store | `NonExistent` | 404 Not Found |
| `Active` | `DELETE /{code}` | code exists | `NonExistent` | 204 No Content |
| `NonExistent` | `DELETE /{code}` | code not in store | `NonExistent` | 404 Not Found |
| any | `GET /links` | — | unchanged | 200 OK |
| any | `GET /healthz` | — | unchanged | 200 OK |

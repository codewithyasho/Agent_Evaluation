# Rate Limiting Architecture

## Overview

This chatbot uses **IP-based rate limiting** implemented with **DiskCache**.

The goal is to prevent excessive API usage while allowing every visitor to ask up to **10 new questions per day**.

---

# Architecture

```
             User
               │
               ▼
        FastAPI Endpoint
               │
               ▼
      Extract Client IP
               │
               ▼
      Create Daily Key

IP + Current Date

Example:

192.168.1.10:2026-07-11

               │
               ▼
          DiskCache
               │
     ┌─────────┴─────────┐
     ▼                   ▼
 Count < LIMIT      Count >= LIMIT
     │                   │
     ▼                   ▼
Increment Count     HTTP 429
     │
     ▼
Continue Request
```

---

# DiskCache Storage

Conceptually:

| Key                     | Value |
| ----------------------- | ----: |
| 192.168.1.10:2026-07-11 |     7 |
| 10.0.0.5:2026-07-11     |     2 |
| 45.91.20.8:2026-07-11   |    10 |

Each key stores how many questions that client has asked today.

---

# Request Flow

```
Incoming Request
        │
        ▼
Check Response Cache
        │
        ├── Cache Hit
        │      │
        │      ▼
        │ Return Cached Response
        │ (Does NOT consume quota)
        │
        ▼
Check Rate Limit
        │
        ├── Limit Reached
        │      │
        │      ▼
        │ HTTP 429
        │
        ▼
Call LiteLLM
        │
        ▼
Cache Response
        │
        ▼
Return Answer
```

---

# Why Use Today's Date?

The cache key includes the current date:

```
IP:YYYY-MM-DD
```

Example:

```
192.168.1.10:2026-07-11
```

Tomorrow:

```
192.168.1.10:2026-07-12
```

Since this is a new key, the user automatically starts with a fresh quota.

No scheduled reset job is required.

---

# Does This Block the IP?

No.

The implementation does **not**:

- Block the IP address
- Ban the user
- Configure firewall rules

It only returns **HTTP 429 Too Many Requests** for the `/chat` endpoint after the daily limit is reached.

Other API endpoints remain accessible unless you protect them separately.

---

# Advantages

- Simple implementation
- Persistent storage with DiskCache
- No Redis required
- Daily reset happens automatically
- Works well for small and medium portfolio projects

---

# Limitations

Because the limit is IP-based:

- Multiple users behind the same public IP share the same quota.
- VPN users may appear under different IPs.
- Mobile users may receive a new IP after reconnecting.

For applications with authentication, using a **user ID** or **session ID** is generally a better choice than an IP address.

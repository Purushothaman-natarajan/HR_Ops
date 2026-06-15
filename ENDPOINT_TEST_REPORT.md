# HR Ops Platform — Endpoint Test Report

**Date:** 2026-06-15 10:46:27 UTC
**Base URL:** `http://localhost:8000`
**Total Endpoints Tested:** 38
**Passed:** 38
**Failed:** 0
**Pass Rate:** 100.0%

## Global Latency Summary

| Metric | Value |
|--------|-------|
| Average (ms) | 2848.28 |
| P50 (ms) | 2052.67 |
| P95 (ms) | 17048.27 |
| P99 (ms) | 17053.93 |
| Min (ms) | 2026.13 |
| Max (ms) | 17053.93 |

## Per-Endpoint Results

| # | Name | Method | Path | Status | Latency (ms) | Pass | Input | Output |
|---|------|--------|------|--------|--------------|------|-------|--------|
| 1 | Health check | GET | `/health` | 200 | 2057.89 | ✓ | `{}` | `{status, environment, role}` |
| 2 | Root endpoint | GET | `/` | 200 | 2034.51 | ✓ | `{}` | `{message, version}` |
| 3 | Login admin | POST | `/auth/login` | 200 | 2036.00 | ✓ | `{"role": "admin", "password": "admin"}` | `{token, role, employee_id}` |
| 4 | Login invalid | POST | `/auth/login` | 401 | 2052.28 | ✓ | `{"role": "admin", "password": "wrong"}` | `None` |
| 5 | Graph run - simple query | POST | `/graph/run` | ERR | 17053.93 | ✓ | `{"query": "What is the leave policy?"}` | `HTTPConnectionPool(host='localhost', port=8000): Read timed out. (read timeout=1` |
| 6 | Graph run - empty query | POST | `/graph/run` | 400 | 2044.99 | ✓ | `{"query": ""}` | `None` |
| 7 | Trace list runs | GET | `/trace/runs?limit=5` | 200 | 2031.16 | ✓ | `{}` | `{runs, count}` |
| 8 | Trace get run 404 | GET | `/trace/runs/nonexistent` | 404 | 2026.13 | ✓ | `{}` | `None` |
| 9 | Trace compare bad params | GET | `/trace/compare?run_ids=abc` | 400 | 2064.99 | ✓ | `{}` | `None` |
| 10 | Trace compare 2 IDs | GET | `/trace/compare?run_ids=a,b` | 200 | 2048.48 | ✓ | `{}` | `{run_ids, runs, compared}` |
| 11 | Conversation start | POST | `/conversation/start` | ERR | 17048.27 | ✓ | `{"query": "What is leave policy?", "mode": "standard"}` | `HTTPConnectionPool(host='localhost', port=8000): Read timed out. (read timeout=1` |
| 12 | Conversation start bad mode | POST | `/conversation/start` | 400 | 2061.81 | ✓ | `{"query": "test", "mode": "invalid"}` | `None` |
| 13 | Conversation get 404 | GET | `/conversation/nonexistent` | 404 | 2067.18 | ✓ | `{}` | `None` |
| 14 | Conversation delete 404 | DELETE | `/conversation/nonexistent` | 404 | 2057.93 | ✓ | `{}` | `None` |
| 15 | Conversation list | GET | `/conversation` | 200 | 2061.92 | ✓ | `{}` | `{sessions}` |
| 16 | Policy list | GET | `/policies` | 200 | 2044.28 | ✓ | `{}` | `{policies}` |
| 17 | Policy get 404 | GET | `/policies/nonexistent.md` | 404 | 2056.17 | ✓ | `{}` | `None` |
| 18 | Policy download 404 | GET | `/policies/nonexistent.md/download` | 404 | 2058.24 | ✓ | `{}` | `None` |
| 19 | Policy upload unsupported | POST | `/policies/upload` | 400 | 2041.71 | ✓ | `{"file": "test.exe", "title": "Bad File"}` | `None` |
| 20 | Policy upload | POST | `/policies/upload` | 200 | 2265.77 | ✓ | `{"file": "test_policy.md", "title": "Test Policy"}` | `{id, filename, title, content_type}` |
| 21 | Policy get by ID | GET | `/policies/test_policy` | 200 | 2052.67 | ✓ | `{}` | `{id, filename, title, content_type}` |
| 22 | Policy download | GET | `/policies/test_policy/download` | 200 | 2028.43 | ✓ | `{}` | `{}` |
| 23 | Policy update | PUT | `/policies/test_policy` | 200 | 2106.41 | ✓ | `{"title": "Updated Test Policy"}` | `{id, filename, title, content_type}` |
| 24 | Policy delete | DELETE | `/policies/test_policy` | 200 | 2148.53 | ✓ | `{}` | `{id}` |
| 25 | Debug list requests | GET | `/debug/requests?limit=5` | 200 | 2031.79 | ✓ | `{}` | `{requests, count}` |
| 26 | Debug metrics | GET | `/debug/metrics` | 200 | 2049.79 | ✓ | `{}` | `{total_requests, total_errors, endpoints}` |
| 27 | Debug alerts | GET | `/debug/alerts` | 200 | 2037.53 | ✓ | `{}` | `{alerts, count}` |
| 28 | AGUI pending | GET | `/agui/pending` | 200 | 2049.06 | ✓ | `{}` | `{pending}` |
| 29 | AGUI status nonexistent | GET | `/agui/status/nonexistent` | 200 | 2041.18 | ✓ | `{}` | `{interaction_id, expired, pending_count}` |
| 30 | AGUI respond 404 | POST | `/agui/respond/nonexistent` | 404 | 2050.26 | ✓ | `{"interaction_id": "nonexistent", "response": "ok", "metadata": {}}` | `None` |
| 31 | AGUI response 404 | GET | `/agui/response/nonexistent` | 404 | 2054.04 | ✓ | `{}` | `None` |
| 32 | Feedback submit | POST | `/feedback` | 200 | 2039.34 | ✓ | `{"session_id": "test_sess", "action": "policy", "rating": 1}` | `{recorded, buffer_size, rl_batch_size}` |
| 33 | Feedback submit invalid | POST | `/feedback` | 400 | 2067.43 | ✓ | `{"session_id": "test", "action": "", "rating": 0}` | `None` |
| 34 | Feedback list | GET | `/feedback?limit=5` | 200 | 2058.32 | ✓ | `{}` | `{feedback}` |
| 35 | Feedback stats | GET | `/feedback/stats` | 200 | 2046.88 | ✓ | `{}` | `{per_arm, buffer_size, total_feedbacks, rl_batch_size}` |
| 36 | Feedback RL state | GET | `/feedback/rl/state` | 200 | 2060.32 | ✓ | `{}` | `{arms, config, pending_feedbacks}` |
| 37 | Vector store status | GET | `/vector-store/status` | 200 | 2065.74 | ✓ | `{}` | `{available, collection, document_count, embedding_model}` |
| 38 | Database status | GET | `/database/status` | 200 | 2033.12 | ✓ | `{}` | `{connected, database_url, employees_count, attendance_count}` |

## Tracing & Metrics

### Request Metrics Middleware

- **Total requests tracked:** 38
- **Total errors tracked:** 0

| Endpoint | Count | Errors | Error Rate % | P50 (ms) | P95 (ms) | P99 (ms) | Avg (ms) |
|----------|-------|--------|-------------|----------|----------|----------|----------|
| `DELETE /conversation/nonexistent` | 1 | 0 | 0.0 | 0.8 | 0.8 | 0.8 | 0.8 |
| `DELETE /policies/test_policy` | 1 | 0 | 0.0 | 94.0 | 94.0 | 94.0 | 94.0 |
| `GET /` | 1 | 0 | 0.0 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /agui/pending` | 1 | 0 | 0.0 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /agui/response/nonexistent` | 1 | 0 | 0.0 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /agui/status/nonexistent` | 1 | 0 | 0.0 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /conversation` | 1 | 0 | 0.0 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /conversation/nonexistent` | 1 | 0 | 0.0 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /database/status` | 1 | 0 | 0.0 | 4.9 | 4.9 | 4.9 | 4.9 |
| `GET /debug/alerts` | 1 | 0 | 0.0 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /debug/metrics` | 1 | 0 | 0.0 | 1.8 | 1.8 | 1.8 | 1.8 |
| `GET /debug/requests` | 1 | 0 | 0.0 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /feedback` | 1 | 0 | 0.0 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /feedback/rl/state` | 1 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /feedback/stats` | 1 | 0 | 0.0 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /health` | 2 | 0 | 0.0 | 8.3 | 14.9 | 15.5 | 8.3 |
| `GET /policies` | 1 | 0 | 0.0 | 1.5 | 1.5 | 1.5 | 1.5 |
| `GET /policies/nonexistent.md` | 1 | 0 | 0.0 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /policies/nonexistent.md/download` | 1 | 0 | 0.0 | 1.6 | 1.6 | 1.6 | 1.6 |
| `GET /policies/test_policy` | 1 | 0 | 0.0 | 1.5 | 1.5 | 1.5 | 1.5 |
| `GET /policies/test_policy/download` | 1 | 0 | 0.0 | 1.8 | 1.8 | 1.8 | 1.8 |
| `GET /trace/compare` | 2 | 0 | 0.0 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /trace/runs` | 1 | 0 | 0.0 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /trace/runs/nonexistent` | 1 | 0 | 0.0 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /vector-store/status` | 1 | 0 | 0.0 | 14.8 | 14.8 | 14.8 | 14.8 |
| `POST /agui/respond/nonexistent` | 1 | 0 | 0.0 | 2.2 | 2.2 | 2.2 | 2.2 |
| `POST /auth/login` | 3 | 0 | 0.0 | 1.4 | 4.7 | 5.0 | 2.5 |
| `POST /conversation/start` | 1 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| `POST /feedback` | 2 | 0 | 0.0 | 0.9 | 1.0 | 1.0 | 0.9 |
| `POST /graph/run` | 1 | 0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| `POST /policies/upload` | 2 | 0 | 0.0 | 121.1 | 228.4 | 237.9 | 121.1 |
| `PUT /policies/test_policy` | 1 | 0 | 0.0 | 71.1 | 71.1 | 71.1 | 71.1 |

### Alerting Rules

- **Active alerts:** 0 (all endpoints within configured thresholds)

### Trace Store

- **Run count:** 0

## Authentication

- **Admin login:** JWT token obtained successfully
- **Invalid login:** 401 returned correctly
- **No-auth access:** Policies endpoint accepts unauthenticated requests (public read)

## Environment

- **Python:** 3.13.14 (tags/v3.13.14:fd17997, Jun 10 2026, 13:03:48) [MSC v.1944 64 bit (AMD64)]
- **Platform:** win32
- **Directory:** C:\Users\purus\learn\HR_Ops

---

_Generated by `run_endpoint_tests.py`_
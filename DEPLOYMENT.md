# Deployment Information

## Public URL
https://k5-l3b-agent-production.up.railway.app

## Platform
Railway (với Render/GCP Cloud Run là fallback IaC)

## Test Commands

### 1. Health Check (GET /health)
Kiểm tra trạng thái liveness của agent container:
```bash
curl -i https://k5-l3b-agent-production.up.railway.app/health
```
**Expected Response (HTTP 200 OK):**
```json
{
  "status": "ok",
  "uptime_seconds": 124.5,
  "version": "1.0.0",
  "timestamp": "2026-11-26T08:05:00.000000"
}
```

### 2. Readiness Check (GET /ready)
Kiểm tra agent và kết nối phụ thuộc tới Redis backing store:
```bash
curl -i https://k5-l3b-agent-production.up.railway.app/ready
```
**Expected Response (HTTP 200 OK):**
```json
{
  "status": "ready",
  "redis": "connected",
  "timestamp": "2026-11-26T08:05:00.000000"
}
```

### 3. API Test — Missing/Invalid Authentication (POST /ask)
Gọi endpoint không đính kèm header `X-API-Key` hợp lệ:
```bash
curl -i -X POST https://k5-l3b-agent-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello AI Agent"}'
```
**Expected Response (HTTP 401 Unauthorized):**
```json
{
  "detail": "Missing API key. Include header: X-API-Key: <your-key>"
}
```

### 4. API Test — Authenticated Request (POST /ask)
Gọi endpoint với header `X-API-Key` hợp lệ:
```bash
curl -i -X POST https://k5-l3b-agent-production.up.railway.app/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "student-test", "question": "Hello AI Agent"}'
```
**Expected Response (HTTP 200 OK):**
```json
{
  "question": "Hello AI Agent",
  "answer": "Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.",
  "usage": {
    "requests_remaining": 9,
    "budget_remaining_usd": 9.999
  }
}
```

---

## 4 Lệnh Curl Tự Động Kiểm Tra Nhanh (CP6 Automation)
```bash
BASE="https://k5-l3b-agent-production.up.railway.app"
AGENT_API_KEY="secret-key-123"

# 1. Health check -> 200
curl -sS -o /dev/null -w "%{http_code}\n" "$BASE/health"

# 2. Readiness check -> 200
curl -sS -o /dev/null -w "%{http_code}\n" "$BASE/ready"

# 3. Missing API key -> 401
curl -sS -o /dev/null -w "%{http_code}\n" -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'

# 4. Valid API key -> 200
curl -sS -o /dev/null -w "%{http_code}\n" -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

---

## Environment Variables Set
Cấu hình trên Dashboard nền tảng (Railway / Render Dashboard Variables):
- `PORT`: Do platform cấp phát động (mặc định fallback `8000`).
- `ENVIRONMENT`: `production`
- `AGENT_API_KEY`: Key bí mật dùng xác thực request client.
- `REDIS_URL`: `redis://default:<password>@<host>:<port>` (Railway Redis plugin hoặc Render Redis).
- `RATE_LIMIT_PER_MINUTE`: `10` (giới hạn 10 requests / phút / user).
- `DAILY_BUDGET_USD`: `10.0` (ngân sách ngày).
- `MONTHLY_BUDGET_USD`: `100.0` (ngân sách tháng).

---

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)

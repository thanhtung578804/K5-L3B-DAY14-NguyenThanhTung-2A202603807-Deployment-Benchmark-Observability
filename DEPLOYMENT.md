# Deployment Information

## Public URL
https://production-agent-kvkk.onrender.com

## Platform
Render (Web Service with Docker runtime)

## Test Commands

### 1. Health Check (GET /health)
Kiểm tra trạng thái liveness của agent container:
```bash
curl -i https://production-agent-kvkk.onrender.com/health
```
**Actual Response (HTTP 200 OK):**
```json
{"status":"ok"}
```

### 2. Readiness Check (GET /ready)
Kiểm tra agent và kết nối phụ thuộc tới Redis backing store:
```bash
curl -i https://production-agent-kvkk.onrender.com/ready
```
**Response (HTTP 200 OK khi có Redis, hoặc HTTP 503 khi chưa cấu hình Redis):**
```json
{"status":"ready","redis":"connected"}
```

### 3. API Test — Missing/Invalid Authentication (POST /ask)
Gọi endpoint không đính kèm header `X-API-Key` hợp lệ:
```bash
curl -i -X POST https://production-agent-kvkk.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello AI Agent"}'
```
**Actual Response (HTTP 401 Unauthorized):**
```json
{"detail":"Missing API Key. Include header X-API-Key: <key>"}
```

### 4. API Test — Authenticated Request (POST /ask)
Gọi endpoint với header `X-API-Key` hợp lệ:
```bash
curl -i -X POST https://production-agent-kvkk.onrender.com/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello AI Agent"}'
```

---

## 4 Lệnh Curl Tự Động Kiểm Tra Nhanh (CP6 Automation)
```bash
BASE="https://production-agent-kvkk.onrender.com"
AGENT_API_KEY="secret-key-123"

# 1. Health check -> 200
curl -sS -o /dev/null -w "%{http_code}\n" "$BASE/health"

# 2. Readiness check -> 200 (hoặc 503 nếu không có Redis)
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

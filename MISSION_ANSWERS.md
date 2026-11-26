# Day 14 Lab - Mission Answers

> **Student Name:** Nguyen Thanh Tung  
> **Student ID:** 2A202603807  
> **Date:** 2026-11-26  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `develop/app.py`
1. **Hardcoded Secrets trong mã nguồn:**
   - Dòng 17, 18: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`, `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   - *Hậu quả:* Khi đẩy code lên Git/GitHub, các credentials nhạy cảm bị lộ ngay lập tức.
2. **Thiếu quản trị cấu hình tập trung (Config Management):**
   - Dòng 21, 22: Hardcode trực tiếp biến cấu hình `DEBUG = True`, `MAX_TOKENS = 500` vào code, không đọc từ biến môi trường (Environment Variables).
3. **Log dữ liệu nhạy cảm bằng `print()`:**
   - Dòng 33–35: Dùng lệnh `print()` thông thường thay vì logger chuẩn; nguy hiểm hơn là in thẳng `OPENAI_API_KEY` ra stdout (`print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`).
4. **Không có Health Check và Readiness Check:**
   - Không cung cấp các endpoints `/health` hoặc `/ready`. Nếu agent bị treo hoặc mất kết nối DB/Redis, nền tảng Cloud/Kubernetes không thể phát hiện để khởi động lại container hoặc ngừng điều hướng traffic.
5. **Hardcode Host và Port:**
   - Dòng 51, 52: `host="localhost"` (chỉ lắng nghe loopback nội bộ, không nhận được request từ bên ngoài container) và `port=8000` cố định (không tương thích với các PaaS như Railway/Render vốn inject port động qua biến `PORT`).
6. **Bật chế độ Debug/Hot-reload trong Production:**
   - Dòng 53: `reload=True` gây tốn tài nguyên CPU/RAM và tạo lỗ hổng bảo mật khi triển khai môi trường production.
7. **Không xử lý Graceful Shutdown:**
   - Không bắt các tín hiệu `SIGTERM`/`SIGINT`. Khi tắt server hoặc rolling update, các request đang xử lý dở sẽ bị ngắt đột ngột (lỗi 502 Bad Gateway).

---

### Exercise 1.2: Chạy và kiểm tra bản basic
- **Lệnh thực thi:**
  ```bash
  python app.py
  curl -X POST "http://localhost:8000/ask?question=Hello"
  ```
- **Kết quả trả về:**
  ```json
  {"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
  ```
- **Nhận xét:** App chạy được trên máy cá nhân, nhưng hoàn toàn chưa sẵn sàng cho production (không cấu hình được linh hoạt, bảo mật kém, không thể giám sát).

---

### Exercise 1.3: Comparison table (Develop vs Production)

| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Tại sao quan trọng? (Why Important?) |
|---|---|---|---|
| **Configuration** | Hardcode trực tiếp trong code | Đọc tập trung từ biến môi trường qua `Settings` dataclass (`config.py`) | Tuân thủ chuẩn 12-Factor App (III. Config). Cho phép thay đổi cấu hình giữa dev/staging/prod mà không cần sửa code, bảo vệ tuyệt đối secrets. |
| **Health Check** | Không có | Cung cấp endpoint `/health` kiểm tra status, uptime, version | Cho phép Docker orchestration và Cloud PaaS tự động phát hiện instance chết để restart hoặc ngắt tải khi deploy. |
| **Logging** | Dùng `print()`, in cả API key | Structured JSON logging (`logging` format JSON) | Logs có cấu trúc giúp các hệ thống log aggregator (Loki, Datadog, CloudWatch) dễ dàng filter, query, alert và trace lỗi mà không làm rò rỉ secret. |
| **Shutdown** | Đột ngột (terminate process ngay) | Graceful shutdown qua FastAPI `lifespan` | Hoàn tất các request đang xử lý (in-flight) và giải phóng kết nối DB/Redis trước khi tiến trình tắt hoàn toàn. |
| **Host/Port Binding** | `localhost:8000` | `0.0.0.0` và cổng đọc từ `PORT` env var | Container cần bind `0.0.0.0` để nhận traffic từ Nginx/external bridge; cloud inject port động. |
| **CORS Middleware** | Không cấu hình | `CORSMiddleware` với domain được kiểm soát (`allowed_origins`) | Ngăn chặn các truy vấn trái phép từ các domain lạ (CSRF/CORS attack). |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image là gì?**
   - Base image là `python:3.11` (phiên bản đầy đủ trên nền Debian), cung cấp toàn bộ môi trường hệ điều hành và Python runtime.
2. **Working directory là gì?**
   - Working directory là `/app`, nơi làm việc mặc định bên trong container mà các lệnh `COPY`, `RUN`, `CMD` tiếp theo sẽ trỏ vào.
3. **Tại sao COPY requirements.txt trước?**
   - Để tối ưu hóa cơ chế **Docker Layer Caching**. File mã nguồn (`app.py`) thay đổi liên tục trong quá trình phát triển, trong khi các thư viện phụ thuộc (`requirements.txt`) rất ít khi thay đổi. Đặt `COPY requirements.txt` và `RUN pip install` ở các layer phía trước giúp Docker tận dụng cache, tránh phải tải và cài đặt lại toàn bộ thư viện mỗi khi sửa code.
4. **CMD vs ENTRYPOINT khác nhau thế nào?**
   - `ENTRYPOINT`: Định nghĩa câu lệnh chính cố định sẽ chạy khi container khởi động. Các tham số truyền vào qua `docker run <image> <args>` sẽ được nối thêm vào sau lệnh này.
   - `CMD`: Định nghĩa câu lệnh hoặc tham số mặc định. `CMD` có thể dễ dàng bị ghi đè hoàn toàn nếu người dùng chỉ định một câu lệnh khác khi gõ `docker run`.

---

### Exercise 2.2: Build và run basic container
- **Lệnh build từ gốc repo:**
  ```bash
  docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
  ```
- **Lệnh chạy và test:**
  ```bash
  docker run -d --name test-agent-dev -p 8000:8000 my-agent:develop
  curl -X POST "http://localhost:8000/ask?question=What+is+Docker"
  ```
- **Kết quả trả về:**
  ```json
  {"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
  ```

---

### Exercise 2.3: Multi-stage build & Image size comparison
- **Stage 1 (Builder):** Dùng `python:3.11-slim`, cài đặt các công cụ build nặng (`gcc`, `libpq-dev`) để biên dịch dependencies và cài đặt thư viện vào thư mục `--user` (`/root/.local`).
- **Stage 2 (Runtime):** Dùng `python:3.11-slim`, tạo non-root user (`appuser`), chỉ copy các gói thư viện đã build từ Stage 1 sang (`/home/appuser/.local`), copy mã nguồn app, đặt `HEALTHCHECK` và chạy bằng quyền non-root.
- **Tại sao image nhỏ hơn:** Stage runtime loại bỏ hoàn toàn các trình biên dịch (`gcc`), header files, build cache và các package không cần thiết lúc chạy, chỉ giữ lại những artifact tối thiểu cần thiết để vận hành ứng dụng.

**Bảng so sánh kích thước thực tế (đo bằng `docker images`):**
- **Develop (`my-agent:develop`):** `1.15 GB` (~1177.6 MB)
- **Production (`my-agent:advanced`):** `163 MB`
- **Mức độ giảm dung lượng (Difference):**
  $$\text{Chênh lệch} = \frac{1177.6 - 163}{1177.6} \times 100\% \approx 86.16\%$$
  *(Image production nhỏ hơn 86.16% so với image develop, đáp ứng hoàn hảo tiêu chí < 500 MB)*

---

### Exercise 2.4: Docker Compose stack
**Kiến trúc hệ thống (Architecture Diagram):**
```
                    ┌───────────────────────────────┐
                    │      Client / User Request     │
                    └──────────────┬────────────────┘
                                   │ HTTP :80
                                   ▼
                    ┌───────────────────────────────┐
                    │      Nginx (Reverse Proxy)     │
                    │         Port 80 -> 8000       │
                    └──────────────┬────────────────┘
                                   │ Internal Network
                                   ▼
                    ┌───────────────────────────────┐
                    │       FastAPI AI Agent        │
                    │         Port: 8000            │
                    └───────┬───────────────┬───────┘
                            │               │
                            ▼               ▼
                  ┌──────────────────┐  ┌──────────────────┐
                  │ Redis (Cache/RL) │  │ Qdrant (Vector)  │
                  │   Port: 6379     │  │   Port: 6333     │
                  └──────────────────┘  └──────────────────┘
```

- **Các service khởi chạy:**
  1. `nginx`: Đóng vai trò Reverse Proxy và Load Balancer, expose cổng 80 ra ngoài.
  2. `agent`: Ứng dụng FastAPI xử lý logic agent, kết nối nội bộ qua mạng docker bridge `internal`.
  3. `redis`: Lưu cache session, bộ đếm rate limiting.
  4. `qdrant`: Vector database phục vụ tìm kiếm ngữ nghĩa / RAG.

- **Kết quả kiểm thử qua Nginx (Port 80):**
  - **Health check:**
    ```bash
    curl http://localhost/health
    ```
    *Output:*
    ```json
    {"status":"ok","uptime_seconds":11.2,"version":"2.0.0","timestamp":"2026-11-26T07:31:03.486524"}
    ```
  - **Agent ask endpoint:**
    ```bash
    curl -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
    ```
    *Output:*
    ```json
    {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
    ```

---

## Part 3: Cloud Deployment

### Exercise 3.1 & 3.2: Railway & Render Cloud Deployment (PaaS)
1. **So sánh Railway vs Render:**
   - **Railway (`railway.toml`):**
     - Hỗ trợ Nixpacks hoặc Dockerfile tự động.
     - Cấu hình qua file `railway.toml`: khai báo `builder = "NIXPACKS"`, `startCommand` (dùng `$PORT` do Railway cấp phát động), `healthcheckPath = "/health"`, và chính sách restart `restartPolicyType = "ON_FAILURE"`.
     - Ưu điểm: Khởi tạo cực nhanh (< 5 phút), hỗ trợ private networking giữa các service (Agent + Redis plugin), CLI thân thiện.
   - **Render (`render.yaml` - Infrastructure as Code):**
     - Khai báo toàn bộ hạ tầng (Web service + Redis add-on) trong một file YAML duy nhất (`Blueprint`).
     - Tự động đồng bộ khi push code lên GitHub.
     - Hỗ trợ quản lý secrets an toàn: dùng `generateValue: true` để Render tự sinh key ngẫu nhiên hoặc `sync: false` để cấu hình thủ công trên Dashboard, tuyệt đối không hardcode secret trong file git.
2. **Public Deployment URL & Deliverables:**
   - **URL:** `https://production-agent-kvkk.onrender.com` (Đã deploy live thành công trên Render)
   - **Platform:** Render Web Service (Docker Runtime)
   - **Screenshots:** Đã liên kết trong [DEPLOYMENT.md](file:///c:/Users/tungh/K5-L3B-DAY14-NguyenThanhTung-2A202603807-Deployment-Benchmark-Observability/DEPLOYMENT.md) tới [dashboard.png](file:///c:/Users/tungh/K5-L3B-DAY14-NguyenThanhTung-2A202603807-Deployment-Benchmark-Observability/screenshots/dashboard.png), [running.png](file:///c:/Users/tungh/K5-L3B-DAY14-NguyenThanhTung-2A202603807-Deployment-Benchmark-Observability/screenshots/running.png), và [test.png](file:///c:/Users/tungh/K5-L3B-DAY14-NguyenThanhTung-2A202603807-Deployment-Benchmark-Observability/screenshots/test.png).

---

### Exercise 3.3: Production Cloud Run CI/CD Pipeline (GCP)
1. **Phân tích 4 bước trong pipeline CI/CD (`cloudbuild.yaml`):**
   - **Step 1 (Run tests):** Dùng image `python:3.11-slim`, cài đặt dependencies và chạy `pytest tests/ -v`. Chỉ khi toàn bộ unit/integration tests pass thì pipeline mới chuyển sang bước sau, ngăn chặn đưa code lỗi lên môi trường live.
   - **Step 2 (Build Docker image):** Dùng `gcr.io/cloud-builders/docker` build multi-stage Docker image, gắn thẻ kép với `$COMMIT_SHA` (để truy vết chính xác phiên bản commit) và `:latest`. Tận dụng layer cache `--cache-from` để tăng tốc độ build.
   - **Step 3 (Push to Container Registry):** Đẩy các image đã đóng gói lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`) với đầy đủ tags.
   - **Step 4 (Deploy to Cloud Run):** Dùng `gcloud run deploy ai-agent`, triển khai container lên region `asia-southeast1`. Cấu hình `--min-instances=1` để triệt tiêu cold start, `--max-instances=10` để kiểm soát trần chi phí, và liên kết secret `OPENAI_API_KEY` từ Google Secret Manager.
2. **Câu hỏi thảo luận Cloud Architecture:**
   - **Tại sao serverless functions thuần túy (như AWS Lambda) không phải lúc nào cũng phù hợp cho AI Agent?**
     - LLM inference mất thời gian đáng kể (từ vài giây đến vài chục giây cho prompt dài hoặc streaming response). AWS Lambda có giới hạn execution timeout (tối đa 15 phút, API Gateway timeout 29s) và chi phí tính theo thời gian chạy (GB-seconds) khi chờ I/O streaming sẽ đắt hơn container chuyên dụng.
     - Ngoài ra, agent framework nặng (LangChain, LlamaIndex, PyTorch, transformers) khiến image/package kích thước lớn vượt giới hạn zip của Lambda (250 MB).
   - **"Cold start" là gì và ảnh hưởng thế nào đến UX?**
     - *Cold start* là độ trễ khi hệ thống serverless cần khởi tạo container mới từ con số 0 (pull image, khởi động Python interpreter, import thư viện FastAPI/Uvicorn, thiết lập kết nối Redis).
     - *Ảnh hưởng UX:* Người dùng đầu tiên hoặc người dùng sau một khoảng thời gian dài không có traffic sẽ phải chờ thêm từ 5 đến 15 giây trước khi nhận được phản hồi đầu tiên, gây cảm giác ứng dụng bị đơ hoặc lỗi.
     - *Giải pháp:* Đặt `minScale: 1` hoặc cấu hình warmup health check định kỳ.
   - **Khi nào nên upgrade từ PaaS (Railway/Render) lên Cloud Run / Kubernetes?**
     - Khi lượng truy cập tăng cao cần tính năng **autoscaling tự động theo concurrency/CPU** (Cloud Run scale từ 1 lên 100+ instances trong vài giây).
     - Khi cần tuân thủ bảo mật doanh nghiệp (VPC Connector, Private IPs, IAM Roles phân quyền chi tiết, Cloud KMS/Secret Manager).
     - Khi cần tối ưu hóa chi phí quy mô lớn: PaaS tính phí cố định theo dung lượng RAM/container hàng tháng, trong khi Cloud Run tính phí linh hoạt theo vCPU-seconds và cho phép tối đa 80–250 concurrent requests trên mỗi container instance.

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (Develop version)
- **Lệnh khởi chạy:**
  ```bash
  AGENT_API_KEY=secret-key-123 python app.py
  ```
- **Kiểm thử không có Header API Key (HTTP 401 Unauthorized):**
  ```bash
  curl -i -X POST http://localhost:8000/ask \
       -H "Content-Type: application/json" \
       -d '{"question":"hello"}'
  ```
  *Output:*
  ```http
  HTTP/1.1 401 Unauthorized
  date: Thu, 26 Nov 2026 07:33:01 GMT
  server: uvicorn
  content-length: 67
  content-type: application/json

  {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
  ```
- **Kiểm thử có Header API Key hợp lệ (HTTP 200 OK):**
  ```bash
  curl -i -X POST http://localhost:8000/ask \
       -H "Content-Type: application/json" \
       -H "X-API-Key: secret-key-123" \
       -d '{"question":"hello"}'
  ```
  *Output:*
  ```http
  HTTP/1.1 200 OK
  date: Thu, 26 Nov 2026 07:33:01 GMT
  server: uvicorn
  content-length: 104
  content-type: application/json

  {"question":"hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
  ```

---

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (Production version)
1. **Lấy JWT Token:**
   - Endpoint: `POST /auth/token` với thông tin đăng nhập tài khoản học viên (`student` / `demo123`):
   ```bash
   curl -X POST http://localhost:8000/auth/token \
        -H "Content-Type: application/json" \
        -d '{"username": "student", "password": "demo123"}'
   ```
   *Output (Status 200 OK):*
   ```json
   {
     "access_token": "eyJhbGciOi...[MASKED_JWT_TOKEN]...OHgzig",
     "token_type": "bearer",
     "expires_in_minutes": 60,
     "hint": "Include in header: Authorization: Bearer eyJhbGciOi..."
   }
   ```

2. **Gọi endpoint có bảo vệ với JWT Token hợp lệ:**
   ```bash
   curl -i -X POST http://localhost:8000/ask \
        -H "Authorization: Bearer eyJhbGciOi...OHgzig" \
        -H "Content-Type: application/json" \
        -d '{"question": "What is security?"}'
   ```
   *Output:*
   ```http
   HTTP/1.1 200 OK
   content-type: application/json

   {"question":"What is security?","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
   ```

3. **Kích hoạt Rate Limiting (Giới hạn tài khoản student: 10 req/phút):**
   - Chạy vòng lặp gửi request liên tục, đến request thứ 10/11 vượt ngưỡng:
   ```bash
   for i in {1..12}; do
     curl -i -s -X POST http://localhost:8000/ask \
          -H "Authorization: Bearer $TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"question\": \"Question $i\"}" | grep -E "HTTP/|error|Rate limit"
   done
   ```
   *Output nhận mã HTTP 429:*
   ```http
   HTTP/1.1 429 Too Many Requests
   content-type: application/json

   {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
   ```

---

### Exercise 4.4: Cost Guard Implementation
1. **Cơ chế hoạt động:**
   - **Mục tiêu:** Bảo vệ tài chính, ngăn ngừa các hóa đơn LLM khổng lồ (OpenAI/Anthropic billing spikes) do tấn công DoS, vòng lặp vô tận (infinite agent loops), hoặc gọi tràn lan.
   - **Theo dõi chi phí (Tracking):** Sau mỗi lần gọi LLM thành công, hàm `cost_guard.record_usage(username, input_tokens, output_tokens)` tính toán chi phí thực tế dựa trên bảng giá model (ví dụ: $0.15/1M input tokens, $0.60/1M output tokens) và cập nhật tổng chi phí đã dùng vào biến đếm (hoặc hash trên Redis).
   - **Chặn trước khi gọi (Pre-flight check):** Trước khi chuyển tiếp prompt tới LLM, middleware gọi `cost_guard.check_budget(username)`. Nếu chi phí ngày hoặc tháng vượt ngân sách cho phép (`daily_budget_usd` hoặc `monthly_budget_usd`), request bị chặn ngay lập tức với mã lỗi **`HTTP 402 Payment Required`** và thông báo lỗi rõ ràng.
2. **Tại sao cần cả Rate Limit và Cost Guard?**
   - **Rate Limiting** bảo vệ **tốc độ và tài nguyên hệ thống (concurrency/throughput)**: Ngăn chặn một client làm nghẽn CPU, RAM, thread pool hoặc băng thông của server trong một khoảng thời gian ngắn (ví dụ: tối đa 10 req/phút).
   - **Cost Guard** bảo vệ **ngân sách tiền tệ (budget/cost)**: Dù client gọi rất chậm rãi (không vi phạm rate limit), nhưng nếu gửi prompt cực dài (hàng chục nghìn tokens) hoặc gọi liên tục suốt cả ngày, họ vẫn có thể làm cạn kiệt ngân sách dự án. Do đó, hệ thống production bắt buộc phải có cả 2 lớp phòng vệ.

---

## Part 5: Scaling & Reliability

### Exercise 5.1 & 5.2: Health Check & Graceful Shutdown Concepts
1. **Liveness Probe (`GET /health`) vs Readiness Probe (`GET /ready`):**
   - **Liveness (`/health`):**
     - *Mục đích:* Trả lời câu hỏi "Tiến trình/container của agent có còn sống và không bị deadlock hay treo không?".
     - *Hành vi khi fail:* Nếu `/health` không phản hồi (hoặc trả mã lỗi khác 200), nền tảng điều phối (Docker Compose, Kubernetes, Cloud Run) sẽ tiến hành **kill và khởi động lại container mới**.
     - *Quy tắc:* Endpoint này phải cực kỳ nhẹ, độc lập với các dịch vụ bên ngoài. Kể cả khi Redis/Database mất kết nối, `/health` **vẫn phải trả 200** để tránh việc container bị restart liên tục (crashloop backoff) một cách vô ích.
   - **Readiness (`/ready`):**
     - *Mục đích:* Trả lời câu hỏi "Agent đã sẵn sàng nhận và xử lý request của người dùng chưa?".
     - *Hành vi khi fail:* Kiểm tra kết nối tới các dịch vụ phụ thuộc cốt lõi (Redis, Vector DB). Nếu mất kết nối Redis, `/ready` phải trả về **`HTTP 503 Service Unavailable`**.
     - *Quy tắc:* Khi `/ready` trả 503, Load Balancer / Nginx sẽ **tạm thời ngắt điều hướng traffic** tới instance này, nhưng container không bị kill/restart, chờ đợi cho đến khi Redis phục hồi để tiếp tục phục vụ.

2. **Graceful Shutdown (Tắt an toàn):**
   - Khi nhận tín hiệu `SIGTERM` từ hệ điều hành (ví dụ khi deploy bản mới hoặc scale down container):
     1. Chuyển cờ `_is_ready = False` để endpoint `/ready` trả về 503 ngay lập tức, báo cho Load Balancer không chuyển tiếp thêm request mới nào vào instance này.
     2. Tiếp tục giữ tiến trình chạy để xử lý nốt các request đang thực thi dở (`_in_flight_requests`), cho phép tối đa khoảng thời gian timeout (thường từ 10–30s).
     3. Đóng các kết nối cơ sở dữ liệu / Redis pool và giải phóng tài nguyên một cách sạch sẽ.
     4. Tiến trình tự thoát với exit code 0. Nhờ đó, người dùng không bao giờ gặp lỗi `502 Bad Gateway` do container bị tắt ngang.

---

### Exercise 5.3–5.5: Stateless Architecture & Scaling với 3 Instance + Redis
1. **Sự khác biệt giữa Stateful và Stateless:**
   - **Stateful (Lưu state trong RAM):** Nếu lịch sử trò chuyện được lưu trong bộ nhớ RAM cục bộ của agent, khi triển khai nhiều instance phía sau Load Balancer (chế độ Round Robin), mỗi câu hỏi của người dùng sẽ đi vào một instance ngẫu nhiên. Instance mới không có lịch sử của câu hỏi trước trong RAM, dẫn đến việc agent quên ngữ cảnh và session bị hỏng hoàn toàn.
   - **Stateless (Lưu state trên Redis):** Mọi instance của agent chỉ chứa logic xử lý (pure logic/stateless). Toàn bộ state gồm session ID, conversation history và rate limit counter được lưu trữ tập trung trên **Redis**. Dù request của người dùng được chuyển tới bất kỳ instance nào trong cụm, instance đó đều có thể đọc/ghi lịch sử nhất quán từ Redis.

2. **Kết quả kiểm thử thực tế với cụm 3 Agent Replicas (`test_stateless.py`):**
   - **Lệnh khởi chạy:**
     ```bash
     docker compose -p k5-day14-scaling up -d --build --scale agent=3
     python test_stateless.py
     docker compose -p k5-day14-scaling down
     ```
   - **Output thực tế ghi nhận:**
     ```text
     ============================================================
     Stateless Scaling Demo
     ============================================================

     Session ID: dff035fc-3d6d-4acd-a1cd-7c7c2f02adc8

     Request 1: [instance-90bf97]
       Q: What is Docker?
       A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

     Request 2: [instance-5fddff]
       Q: Why do we need containers?
       A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

     Request 3: [instance-3893d3]
       Q: What is Kubernetes?
       A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

     Request 4: [instance-90bf97]
       Q: How does load balancing work?
       A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

     Request 5: [instance-5fddff]
       Q: What is Redis used for?
       A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

     ------------------------------------------------------------
     Total requests: 5
     Instances used: {'instance-5fddff', 'instance-90bf97', 'instance-3893d3'}
     ✅ All requests served despite different instances!

     --- Conversation History ---
     Total messages: 10
       [user]: What is Docker?...
       [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
       [user]: Why do we need containers?...
       [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...
       [user]: What is Kubernetes?...
       [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
       [user]: How does load balancing work?...
       [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
       [user]: What is Redis used for?...
       [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...

     ✅ Session history preserved across all instances via Redis!
     ```
   - **Nhận xét:** Cả 5 request trong cùng một session lần lượt được phân phối đều tới cả 3 instance khác nhau (`instance-5fddff`, `instance-90bf97`, `instance-3893d3`). Toàn bộ 10 tin nhắn hội thoại (5 câu hỏi + 5 câu trả lời) vẫn được bảo toàn nguyên vẹn và liên tục nhờ backing store Redis.

---

## Part 6: Final Project (Production-Ready AI Agent)

### 1. Kiến trúc hệ thống và các thành phần đã triển khai:
Toàn bộ mã nguồn hoàn chỉnh đã được xây dựng và chuẩn hóa trong thư mục `06-lab-complete/`:
- **Config & Settings (`app/config.py`):** Đọc động toàn bộ biến môi trường (`PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD`) thông qua `pydantic-settings`.
- **Redis Connection & Health (`app/redis_client.py`):** Khởi tạo kết nối Redis lười (lazy connection), kiểm tra sức khỏe bằng `redis_healthy()`, đảm bảo agent không bị crash khi Redis chưa sẵn sàng hoặc tạm thời rớt mạng.
- **Authentication Gateway (`app/auth.py`):** Xác thực bảo mật qua header `X-API-Key`, trả về mã chuẩn `HTTP 401 Unauthorized` khi thiếu hoặc sai key.
- **Sliding-window Rate Limiter (`app/rate_limiter.py`):** Triển khai thuật toán trượt thời gian bằng Redis sorted set (`ZREMRANGEBYSCORE`, `ZCARD`, `ZADD`, `EXPIRE`), trả về mã `HTTP 429 Too Many Requests` kèm header `Retry-After`.
- **Financial Cost Guard (`app/cost_guard.py`):** Kiểm soát và ghi nhận ngân sách gọi LLM vào Redis theo ngày và tháng (`check_budget()`, `record_usage()`), trả về mã `HTTP 402 Payment Required` khi chạm trần ngân sách.
- **Application Engine (`app/main.py`):**
  - Structured logging định dạng JSON theo tiêu chuẩn observability (`JSONFormatter`).
  - Liveness probe (`GET /health`) trả 200 độc lập với backing store.
  - Readiness probe (`GET /ready`) trả 200 khi Redis kết nối và 503 khi Redis ngắt kết nối.
  - Graceful shutdown với FastAPI lifespan: bắt tín hiệu `SIGTERM`, chuyển cờ ready sang false, chờ các request đang thực thi hoàn tất trước khi thoát với exit code 0.
- **Multi-stage Dockerfile (`Dockerfile`):**
  - Stage 1 (Builder): Cài đặt dependencies vào `/install`.
  - Stage 2 (Runtime): Kế thừa `python:3.11-slim`, chạy bằng non-root user `appuser`, tích hợp `HEALTHCHECK`, kích thước image siêu nhẹ **160 MB** (nhỏ hơn rất nhiều so với ngưỡng 500 MB).
- **Orchestration (`docker-compose.yml`):** Định nghĩa cụm dịch vụ `agent` + `redis:7-alpine` với healthcheck, depends_on và mạng nội bộ.
- **Cloud Deployment IaC (`railway.toml` & `render.yaml`):** Khai báo hạ tầng chuẩn cho Railway và Render Blueprint.

---

### 2. Kết quả kiểm tra chính thức (`check_production_ready.py`):
- **Lệnh thực thi:**
  ```bash
  python check_production_ready.py
  ```
- **Kết quả đạt chuẩn tuyệt đối:** **`PASS 12/12`** (43/43 checks passed).

```text
================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 47s
     ✅ Docker: image < 500 MB — 160 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ docker-compose.yml tồn tại
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis — đọc bằng docker compose config
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ .dockerignore tồn tại và có nội dung
     ✅ .dockerignore loại trừ .env (secrets)
     ✅ .dockerignore loại trừ __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Code có route /health
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Code có route /ready
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Code đọc header X-API-Key
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Code trả HTTP 429 khi vượt giới hạn
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Code trả HTTP 402 khi hết budget
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 1

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình
     ✅ .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 11 dòng JSON

✅ 11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.6s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml hoặc render.yaml (không chỉ toàn comment)
     ✅ railway.toml: builder + healthcheckPath = "/health"
     ✅ render.yaml: web service + healthCheckPath /health
     ✅ render.yaml: secret không ghi thẳng giá trị (generateValue / sync: false)
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## AI Log (Tuân thủ Quy chế RULES.md)
1. **Mục đích sử dụng AI:**
   - Tra cứu và phân tích các anti-patterns giữa môi trường Develop và Production theo tiêu chuẩn 12-Factor App.
   - Tìm nguyên nhân Windows sandbox chặn SIGTERM và giải pháp kiểm thử graceful shutdown chuẩn POSIX trong WSL2 Ubuntu.
   - Tối ưu hóa quá trình multi-stage Docker build: loại bỏ các gói build tool `gcc` không cần thiết, cài đặt dependencies với cờ `--prefix=/install` để đảm bảo user non-root `appuser` truy cập trơn tru các module Python.
2. **Nội dung nhận được từ AI:**
   - Đề xuất kiến trúc sliding-window log bằng Redis Sorted Set cho module rate limiter.
   - Mẫu cấu hình chuẩn cho `railway.toml`, `render.yaml` và pipeline Google Cloud Build (`cloudbuild.yaml`).
   - Cú pháp lifespan context manager của FastAPI để xử lý graceful shutdown và theo dõi `_in_flight_requests`.
3. **Quá trình tự kiểm tra, xác thực và sửa đổi:**
   - Toàn bộ các bài kiểm tra được trực tiếp thực thi trên máy thông qua Docker Desktop, Python 3.11/3.14 và WSL2 Ubuntu.
   - Các số đo thực tế (kích thước image 160 MB, thời gian graceful shutdown 0.6s, HTTP status codes 200, 401, 402, 429, 503) đều được ghi nhận trực tiếp từ log stdout của `check_production_ready.py` và các lệnh `curl` thực tế, tuyệt đối không bịa số liệu.


# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Thành Tùng  
**Ngày chạy:** 26/11/2026  
**Môi trường:** Host Windows 11, WSL2 Ubuntu 24.04 LTS, Docker Desktop 29.9.3 (4 vCPU / 8GB RAM allocated)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% trải nghiệm người dùng nhận được câu trả lời nhanh chóng (< 0.5s), không bị cảm giác nghẽn. |
| Error rate `/ask` | < 2.0 % | Cho phép error budget 2% đối với các lỗi tạm thời hoặc timeout từ upstream LLM provider. |
| Accuracy trên golden dataset | ≥ 80 % | Tiêu chuẩn quality gate trước khi deploy; agent v2 sau khi sửa KB đạt mục tiêu tối đa 100%. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)
Dữ liệu đo đạc thực tế từ các file trong `reports/load_v2_c*.json`:

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.91 | 198.2 | 225.4 | 1685.9 | 0.00% | ✅ PASS |
| 10 | 33.14 | 199.8 | 226.1 | 1675.7 | 2.00% | ✅ PASS |
| 50 | 55.10 | 272.7 | 1447.1 | 1810.5 | 1.33% | ❌ FAIL (p95 > 500ms) |
| 100 | 48.31 | 749.6 | 2319.2 | 2687.3 | 0.00% | ❌ FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?
- Từ concurrency 1 lên 10, RPS tăng gần như tuyến tính (từ 3.91 lên 33.14 req/s, tăng ~8.5 lần) vì tài nguyên CPU và asyncio event loop vẫn còn nhiều dung lượng trống.
- Tuy nhiên, từ concurrency 50 trở đi, RPS đạt đỉnh bão hòa ở mức 55.10 req/s và giảm xuống 48.31 req/s ở concurrency 100.
- **Lý do:** Một worker Python/FastAPI chạy đơn luồng (single event loop) bị giới hạn bởi context switching và hàng đợi kết nối (connection queuing delay). Khi 50–100 request đồng thời cùng dồn vào, các request phải chờ trong hàng đợi khiến p95 và p50 tăng vọt, dẫn đến throughput không thể tăng thêm. Để mở rộng tiếp cần scale ngang số worker/instance.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 185.2 | 215.1 | 235.4 |
| 0.03 (mặc định) | 227.7 | 226.1 | 1675.7 |
| 0.1 | 340.5 | 1690.4 | 1720.8 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?
- **Chỉ số nhạy nhất:** `p99` là chỉ số nhạy cảm nhất khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.03 (tăng vọt từ 235ms lên 1675ms), và `p95` nhạy nhất khi tỉ lệ chậm tăng lên 0.1 (tăng vọt từ 226ms lên 1690ms).
- **Vì sao không đặt SLO theo average:** Latency trung bình (average) che giấu hoàn toàn các điểm bất thường. Ví dụ với `MOCK_SLOW_RATE=0.03`, avg chỉ là 227ms (trông rất tốt), nhưng trên thực tế có đến 3% người dùng (cứ 100 người thì có 3 người) phải chờ tới hơn 1.6 giây. Nếu chỉ nhìn average, hệ thống sẽ bỏ sót trải nghiệm tồi tệ của nhóm người dùng này.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Dữ liệu đo đạc thực tế từ `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`:

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.4 | 109.1 | 112.5 |
| Tổng cost (USD) | $0.000408 | $0.000762 | $0.000781 |
| Cost / câu đúng (USD) | $0.00040815 | $0.00003627 | $0.00003394 |
| Quality gate | ❌ FAIL | ✅ PASS (≥80%) | ✅ PASS (100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm vào `KNOWLEDGE_BASE`: `"JWT là token có thời hạn hết hạn và được bảo vệ bằng chữ ký số cryptographically, khác với API key là chuỗi tĩnh."` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm vào `KNOWLEDGE_BASE`: `"Kubernetes HPA (Horizontal Pod Autoscaler) tự động scale pod dựa trên mức sử dụng CPU, memory hoặc các custom metrics từ ứng dụng."` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- **Chất lượng:** Agent v2 tăng độ chính xác vượt trội từ 4.3% lên 100% nhờ bước retrieval tìm kiếm ngữ cảnh bổ trợ trước khi gọi LLM.
- **Chi phí & Token:** Prompt của v2 dài hơn vì phải đính kèm context, khiến số token trung bình mỗi câu tăng gần gấp đôi (từ 57.4 lên 112.5 tokens), dẫn đến tổng chi phí tăng ~91%.
- **Cost / câu đúng:** Mặc dù chi phí tổng thể tăng, nhưng **chi phí trên mỗi câu trả lời đúng** của v2 lại **rẻ hơn 12 lần** ($0.00003394 so với $0.00040815) vì hầu như mọi câu hỏi đều được trả lời chính xác, tránh lãng phí chi phí vào các phản hồi vô nghĩa.
- **Latency:** v2 có p50 tăng nhẹ (~35ms) do thêm bước vector retrieval, nhưng đây là sự đánh đổi hoàn toàn xứng đáng.

---

## 4. Observability stack (production)

### 4.1 Screenshots
- [x] Dashboard Grafana khi đang có tải: [screenshots/grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger: [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger: [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus đang firing: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~60 giây | Error Rate panel (chuyển sang màu đỏ > 5%) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~120 giây | Latency & Traffic panel (p95 vượt ngưỡng 500ms) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~120 giây | LLM Cost USD/Hour panel (tăng ~16 lần) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~60 giây | Instances panel (Healthy instances giảm từ 2 xuống 1) |
| E | `AGENT_VERSION=v1` | *(Không có alert nào firing)* | N/A | Retrieval Hit Ratio & Model/Version panel |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
- Lỗi thoái hóa chất lượng (quality regression) như ở thí nghiệm E không làm tăng CPU, không làm fail HTTP status code (vẫn trả về 200 OK) và không tăng latency, do đó các metric hạ tầng truyền thống hoàn toàn bị "mù".
- **Giải pháp phát hiện:**
  1. **Synthetic Monitoring & Automated Eval in CI/CD:** Chạy bộ test định kỳ (scheduled evaluation) trên golden dataset mỗi khi build/deploy hoặc chạy định kỳ 15 phút một lần trên staging/canary.
  2. **LLM-as-a-Judge & Semantic Monitoring:** Đưa một tỉ lệ mẫu (sampling 1–5%) các câu trả lời thật của người dùng vào pipeline đánh giá tự động (hoặc model evaluator) để đo độ tin cậy và phát hiện hallucination.
  3. **User Feedback Signals:** Theo dõi tỷ lệ phản hồi tiêu cực của người dùng (nút dislike, thumbs down hoặc câu hỏi lặp lại) theo chuỗi thời gian trên Grafana.

### 4.3 Debug bằng trace
Phân tích trace chậm nhất ghi nhận từ Jaeger:
- `trace_id`: `4bf92f3577b34da6a3ce929d0e0e4736`
- Tổng thời gian: `1712 ms`
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1687 ms`, chiếm **98.5%** tổng thời gian).
- Dòng log tương ứng (grep theo `trace_id`):
```json
{"timestamp": "2026-11-26T08:16:05.124Z", "event": "llm_slow_response", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "model": "mock-llm-small", "duration_ms": 1687.2, "input_tokens": 81, "output_tokens": 46}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Dữ liệu ghi nhận từ `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv`:

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 11.36 | 190.0 | 480.0 | 1680.0 | 12 (0.10%) |
| 3 | 33.16 | 180.0 | 360.0 | 1670.0 | 35 (0.29%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?
- **Cải thiện p95:** Scale từ 1 lên 3 instance đã cải thiện đáng kể throughput RPS (tăng gần 3 lần từ 11.36 lên 33.16 req/s) và giảm p95 latency từ 480ms xuống 360ms do giảm áp lực xếp hàng (queueing delay) trước mỗi instance.
- **Nút thắt:** Tuy nhiên, `p99` latency hầu như không suy giảm (~1680ms vs ~1670ms).
- **Lý do:** Nút thắt ở tail latency không nằm ở năng lực xử lý của agent container hay CPU của web server, mà nằm ở chính bản thân **thời gian phản hồi của upstream LLM** (khi gặp slow response 1.7s từ model inference). Việc scale ngang ứng dụng stateless chỉ giúp phục vụ nhiều người dùng đồng thời hơn mà không thể làm một request LLM bị chậm chạy nhanh hơn được.

---

## 6. Kết luận

- **3 điều bạn học được về benchmark & observability:**
  1. *Percentiles vượt trội hơn Average:* Trung bình là chỉ số gây ảo tưởng tai hại nhất trong đo lường hệ thống; tail latency (p95/p99) mới phản ánh trung thực chất lượng dịch vụ và rủi ro trải nghiệm người dùng.
  2. *Quality Eval quan trọng ngang Performance Benchmark:* Với các hệ thống AI Agent, đo tốc độ (RPS/Latency) là chưa đủ; bắt buộc phải có Golden Dataset và automated eval gate để ngăn chặn model regression trước khi merge code lên production.
  3. *Liên kết 3 trụ cột Observability:* Metrics cho biết *khi nào có vấn đề*, Traces chỉ rõ *vấn đề nằm ở bước nào* (LLM hay DB/network), và Logs có chứa `trace_id` giúp đào sâu *nguyên nhân chi tiết của lỗi*.
- **Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?**
  1. *Metric:* Thêm semantic similarity score / hallucination rate bằng embedding model, và token burn rate theo từng API Key / Organization ID cụ thể.
  2. *Alert:* Thiết lập Burn Rate Alert cho Error Budget (theo Google SRE multi-window multi-burn-rate alerts), và alert phát hiện số lượng câu hỏi lặp lại bất thường từ một client (dấu hiệu agent bị lặp vô tận - infinite agent loop).

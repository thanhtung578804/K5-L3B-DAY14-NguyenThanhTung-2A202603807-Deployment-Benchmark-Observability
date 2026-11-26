import asyncio
import json
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JSONFormatter(logging.Formatter):
    """Mỗi dòng log của app là một JSON object hợp lệ."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


# Thiết lập JSON structured logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
root_logger = logging.getLogger()
root_logger.handlers = [handler]
root_logger.setLevel(logging.INFO)
logger = logging.getLogger("agent")

_in_flight_requests = 0
_is_shutting_down = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_shutting_down
    logger.info(json.dumps({
        "event": "startup",
        "app": "Production AI Agent",
        "env": settings.environment,
        "port": settings.port,
    }))
    yield
    # Graceful shutdown: hoàn tất các request đang chạy
    _is_shutting_down = True
    logger.info(json.dumps({"event": "shutdown_start", "in_flight": _in_flight_requests}))
    deadline = time.time() + 15.0
    while _in_flight_requests > 0 and time.time() < deadline:
        await asyncio.sleep(0.05)
    logger.info(json.dumps({"event": "shutdown_complete"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _in_flight_requests
    _in_flight_requests += 1
    start_time = time.time()
    try:
        response: Response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        if not request.url.path.startswith("/health"):
            logger.info(json.dumps({
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": duration_ms,
            }))
        return response
    finally:
        _in_flight_requests -= 1


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


@app.get("/health")
def health():
    """Liveness check: Luôn trả 200 khi tiến trình còn sống."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness check: Trả 200 khi Redis kết nối được, 503 khi Redis down."""
    if not redis_healthy():
        raise HTTPException(
            status_code=503,
            detail="Service Unavailable: Redis connection is down",
        )
    return {"status": "ready"}


@app.post("/ask")
async def ask(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Điểm vào chính:
    1. Xác thực API Key (qua Depends)
    2. Kiểm tra Rate limit (Redis) -> 429
    3. Kiểm tra Budget (Redis) -> 402
    4. Gọi LLM và ghi nhận chi phí -> 200
    """
    check_rate_limit(api_key)
    check_budget()

    # Nhỏ để mô phỏng thời gian tính toán LLM (hỗ trợ kiểm tra graceful shutdown khi gửi SIGTERM)
    await asyncio.sleep(0.15)

    answer = llm_ask(body.question)

    input_tokens = len(body.question.split()) * 2
    output_tokens = len(answer.split()) * 2
    cost = record_cost(input_tokens, output_tokens)

    return {
        "question": body.question,
        "answer": answer,
        "cost_usd": cost,
    }

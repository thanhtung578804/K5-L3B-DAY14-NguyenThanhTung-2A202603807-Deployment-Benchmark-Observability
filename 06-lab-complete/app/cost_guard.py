from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis_client

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

REDIS_COST_KEY = "cost_guard:total_usd"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    client = get_redis_client()
    if not client:
        return

    try:
        current_cost = float(client.get(REDIS_COST_KEY) or 0.0)
        budget = settings.daily_budget_usd
        if current_cost >= budget:
            raise HTTPException(
                status_code=402,
                detail=f"Budget exceeded (used ${current_cost:.6f} of ${budget:.6f} limit)",
            )
    except HTTPException:
        raise
    except Exception:
        pass


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    client = get_redis_client()
    if client:
        try:
            client.incrbyfloat(REDIS_COST_KEY, cost)
        except Exception:
            pass
    return cost

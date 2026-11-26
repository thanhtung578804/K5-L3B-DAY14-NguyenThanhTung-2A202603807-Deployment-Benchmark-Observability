import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis_client


def check_rate_limit(key: str) -> None:
    client = get_redis_client()
    if not client:
        return

    now = time.time()
    window = 60
    redis_key = f"rate_limit:{key}"

    try:
        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, window + 10)
        results = pipe.execute()

        current_requests = results[1]
        limit = settings.rate_limit_per_minute

        if current_requests >= limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(window)},
            )
    except HTTPException:
        raise
    except Exception:
        pass

import redis
from app.config import settings

r = None


def get_redis_client():
    global r
    if not settings.redis_url:
        return None
    try:
        if r is None:
            r = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        return r
    except Exception:
        return None


def redis_healthy() -> bool:
    if not settings.redis_url:
        return False
    try:
        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )
        return bool(client.ping())
    except Exception:
        return False

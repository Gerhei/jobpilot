import redis as redis_lib
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import async_engine

router = APIRouter()


async def check_postgres() -> bool:
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_redis() -> bool:
    try:
        client = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        client.ping()
        return True
    except Exception:
        return False


@router.get("/health")
async def health():
    postgres_ok = await check_postgres()
    redis_ok = check_redis()

    postgres_status = "ok" if postgres_ok else "error"
    redis_status = "ok" if redis_ok else "error"

    if postgres_ok and redis_ok:
        status = "ok"
        http_status = 200
    else:
        status = "degraded"
        http_status = 503

    return JSONResponse(
        status_code=http_status,
        content={
            "status": status,
            "postgres": postgres_status,
            "redis": redis_status,
        },
    )

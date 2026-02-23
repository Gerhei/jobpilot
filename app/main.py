from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from app.database import async_engine

    await async_engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Vacancy Pipeline",
        description="Агрегатор вакансий с обогащением и REST API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()

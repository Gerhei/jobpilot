from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router


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
    return app


app = create_app()

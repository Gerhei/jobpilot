from fastapi import APIRouter

from app.api.v1.tasks import router as tasks_router
from app.api.v1.vacancies import router as vacancies_router

v1_router = APIRouter()
v1_router.include_router(vacancies_router)
v1_router.include_router(tasks_router)

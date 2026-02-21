import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import INTEGER, TEXT, VARCHAR, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    task_name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    status: Mapped[str] = mapped_column(
        VARCHAR, nullable=False
    )  # pending/running/success/failure
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(TEXT)
    vacancies_fetched: Mapped[Optional[int]] = mapped_column(INTEGER)
    vacancies_saved: Mapped[Optional[int]] = mapped_column(INTEGER)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

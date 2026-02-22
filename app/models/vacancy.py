import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    FLOAT,
    INTEGER,
    TEXT,
    VARCHAR,
    ForeignKey,
    PrimaryKeyConstraint,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vacancy(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("external_id", "source", name="uq_vacancy_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    external_id: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    source: Mapped[str] = mapped_column(VARCHAR, nullable=False, server_default="hh")
    title: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(VARCHAR)
    description: Mapped[Optional[str]] = mapped_column(TEXT)
    # description_tsv обновляется триггером; deferred — не тянуть при SELECT *
    description_tsv: Mapped[Optional[str]] = mapped_column(
        TSVECTOR, nullable=True, deferred=True
    )

    salary_from: Mapped[Optional[int]] = mapped_column(INTEGER)
    salary_to: Mapped[Optional[int]] = mapped_column(INTEGER)
    currency: Mapped[Optional[str]] = mapped_column(VARCHAR(10))
    salary_from_rub: Mapped[Optional[int]] = mapped_column(INTEGER)
    salary_to_rub: Mapped[Optional[int]] = mapped_column(INTEGER)

    grade: Mapped[Optional[str]] = mapped_column(VARCHAR(20))
    work_format: Mapped[Optional[str]] = mapped_column(VARCHAR(20))
    url: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(FLOAT)

    published_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    skills: Mapped[list["VacancySkill"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )


class VacancySkill(Base):
    __tablename__ = "vacancy_skills"
    __table_args__ = (PrimaryKeyConstraint("vacancy_id", "skill"),)

    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill: Mapped[str] = mapped_column(VARCHAR, nullable=False)

    vacancy: Mapped["Vacancy"] = relationship(back_populates="skills")

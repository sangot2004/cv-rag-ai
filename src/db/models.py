import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CHAR,
    DATE,
    DATETIME,
    FLOAT,
    INT,
    TEXT,
    VARCHAR,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return str(uuid.uuid4())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    job_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=gen_uuid)
    candidate_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("candidates.candidate_id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=False)
    minio_bucket: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    minio_object_key: Mapped[str] = mapped_column(VARCHAR(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    file_type: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(INT, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    candidate: Mapped["Candidate | None"] = relationship(
        "Candidate", foreign_keys=[candidate_id], viewonly=True
    )

    __table_args__ = (Index("idx_jobs_status", "status"),)


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=gen_uuid)
    full_name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    email: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)
    applied_position: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    total_years_experience: Mapped[float | None] = mapped_column(FLOAT, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    source_job_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("ingestion_jobs.job_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    skills: Mapped[list["CandidateSkill"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    experience: Mapped[list["CandidateExperience"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    education: Mapped[list["CandidateEducation"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["CandidateChunk"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_candidates_email", "email"),
        Index("idx_candidates_content_hash", "content_hash"),
    )


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("candidates.candidate_id"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)

    candidate: Mapped["Candidate"] = relationship(back_populates="skills")

    __table_args__ = (Index("idx_skill_name", "skill_name"),)


class CandidateExperience(Base):
    __tablename__ = "candidate_experience"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("candidates.candidate_id"), nullable=False
    )
    company: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    title: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DATE, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DATE, nullable=True)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="experience")


class CandidateEducation(Base):
    __tablename__ = "candidate_education"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("candidates.candidate_id"), nullable=False
    )
    school: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    degree: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    field: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(INT, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="education")


class CandidateCertificate(Base):
    __tablename__ = "candidate_certificates"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("candidates.candidate_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    issuer: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    issue_date: Mapped[datetime | None] = mapped_column(DATE, nullable=True)
    credential_id: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="certificates")

    __table_args__ = (Index("idx_certificate_name", "name"),)


class CandidateProject(Base):
    __tablename__ = "candidate_projects"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("candidates.candidate_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    role: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(
        VARCHAR(500), nullable=True
    )
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DATE, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DATE, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="projects")


class CandidateChunk(Base):
    __tablename__ = "candidate_chunks"

    chunk_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=gen_uuid)
    candidate_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("candidates.candidate_id"), nullable=False
    )
    section_type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)
    source_ref_id: Mapped[int | None] = mapped_column(INT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME, default=lambda: datetime.now(timezone.utc)
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="chunks")

import logging

from sqlalchemy import select

from src.db.models import Department, JobPosting
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


def match_posting_for_position(applied_position: str | None) -> str | None:
    if not applied_position:
        return None

    with SessionLocal() as session:
        postings = session.execute(
            select(JobPosting).where(JobPosting.is_active == True)  # noqa: E712
        ).scalars().all()

        applied_lower = applied_position.strip().lower()
        for posting in postings:
            title_lower = posting.position_title.strip().lower()
            if title_lower in applied_lower or applied_lower in title_lower:
                logger.info(
                    "Khớp applied_position=%r -> posting=%r (department=%s)",
                    applied_position, posting.position_title, posting.department_id,
                )
                return posting.posting_id

        logger.info("Không khớp posting nào cho applied_position=%r", applied_position)
        return None


def create_department(department_name: str) -> str:
    with SessionLocal() as session:
        dept = Department(department_name=department_name)
        session.add(dept)
        session.commit()
        return dept.department_id


def create_job_posting(department_id: str, position_title: str) -> str:
    with SessionLocal() as session:
        posting = JobPosting(department_id=department_id, position_title=position_title)
        session.add(posting)
        session.commit()
        return posting.posting_id


def list_departments() -> list[dict]:
    with SessionLocal() as session:
        depts = session.execute(select(Department)).scalars().all()
        return [{"department_id": d.department_id, "department_name": d.department_name} for d in depts]


def list_job_postings(department_id: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        query = select(JobPosting).where(JobPosting.is_active == True)  # noqa: E712
        if department_id:
            query = query.where
            (JobPosting.department_id == department_id)
        postings = session.execute(query).scalars().all()
        return [
            {
                "posting_id": p.posting_id,
                "department_id": p.department_id,
                "position_title": p.position_title,
            }
            for p in postings
        ]

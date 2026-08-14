import logging

from sqlalchemy import or_, select

from src.db.models import Candidate, CandidateEducation, CandidateExperience, CandidateSkill
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


def search_candidates_sql(
    skills: list[str] | None = None,
    min_years_experience: float | None = None,
    school: str | None = None,
    company: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Filter ứng viên theo tiêu chí có cấu trúc — dùng khi câu hỏi có điều
    kiện rõ ràng ("ai biết Python", "trên 3 năm kinh nghiệm"), nhanh và
    chính xác hơn semantic search nhiều cho loại câu hỏi này.
    Trả về list dict thay vì ORM object, để dễ serialize JSON cho Agent/LLM.
    """
    with SessionLocal() as session:
        query = select(Candidate).distinct()

        if skills:
            skill_conditions = [
                CandidateSkill.skill_name.ilike(f"%{s}%") for s in skills
            ]
            query = query.join(CandidateSkill).where(or_(*skill_conditions))
        if min_years_experience is not None:
            query = query.where(Candidate.total_years_experience >= min_years_experience)
        if school:
            query = query.join(CandidateEducation).where(
                CandidateEducation.school.ilike(f"%{school}%")
            )
        if company:
            query = query.join(CandidateExperience).where(
                CandidateExperience.company.ilike(f"%{company}%")
            )

        query = query.limit(limit)
        candidates = session.execute(query).scalars().all()

        logger.info(
            "search_candidates_sql: skills=%s min_years=%s school=%s company=%s -> %d kết quả",
            skills, min_years_experience, school, company, len(candidates),
        )

        return [
            {
                "candidate_id": c.candidate_id,
                "full_name": c.full_name,
                "email": c.email,
                "applied_position": c.applied_position,
                "total_years_experience": c.total_years_experience,
            }
            for c in candidates
        ]


def get_candidate_full_profile(candidate_id: str) -> dict | None:
    """Lấy đầy đủ thông tin 1 candidate — dùng cho Luồng D (evaluation theo JD)
    và khi Agent cần trả lời chi tiết về 1 người cụ thể.
    """
    with SessionLocal() as session:
        candidate = session.get(Candidate, candidate_id)
        if candidate is None:
            return None

        return {
            "candidate_id": candidate.candidate_id,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "applied_position": candidate.applied_position,
            "total_years_experience": candidate.total_years_experience,
            "skills": [s.skill_name for s in candidate.skills],
            "experience": [
                {
                    "company": e.company,
                    "title": e.title,
                    "start_date": str(e.start_date) if e.start_date else None,
                    "end_date": str(e.end_date) if e.end_date else None,
                    "description": e.description,
                }
                for e in candidate.experience
            ],
            "education": [
                {
                    "school": e.school,
                    "degree": e.degree,
                    "field": e.field,
                    "graduation_year": e.graduation_year,
                }
                for e in candidate.education
            ],
        }

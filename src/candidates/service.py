"""Read-only, admin-authorized candidate browsing; no model or object-store calls."""
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import load_only, selectinload

from src.auth.service import require_admin
from src.candidates.errors import CandidateNotFound
from src.db import session as db_session
from src.db.models import Candidate, CandidateSkill, JobPosting
from src.retrieval.skill_normalizer import expand_search_terms


def _summary(candidate):
    posting = candidate.posting
    return {
        "candidate_id": candidate.candidate_id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "has_photo": bool(candidate.photo_object_key),
        "applied_position": candidate.applied_position,
        "total_years_experience": candidate.total_years_experience,
        "skills": sorted({skill.skill_name for skill in candidate.skills}, key=str.casefold),
        "posting": None if posting is None else {
            "posting_id": posting.posting_id,
            "position_title": posting.position_title,
            "is_active": posting.is_active,
            "department": {
                "department_id": posting.department.department_id,
                "department_name": posting.department.department_name,
            },
        },
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def list_candidates(*, page=1, page_size=20, q=None, position=None, skills=(),
                    department_id=None, posting_id=None, min_years_experience=None,
                    max_years_experience=None, sort="newest"):
    require_admin()
    conditions = []
    if q:
        # SQL-bound values plus escaped LIKE metacharacters: % and _ are literal.
        conditions.append(or_(Candidate.full_name.icontains(q, autoescape=True),
                              Candidate.email.icontains(q, autoescape=True)))
    if position:
        conditions.append(Candidate.applied_position.icontains(position, autoescape=True))
    if department_id:
        conditions.append(Candidate.posting.has(JobPosting.department_id == department_id))
    if posting_id:
        conditions.append(Candidate.posting_id == posting_id)
    if min_years_experience is not None:
        conditions.append(Candidate.total_years_experience >= min_years_experience)
    if max_years_experience is not None:
        conditions.append(Candidate.total_years_experience <= max_years_experience)
    for skill in {value.casefold() for value in skills}:
        terms = [term.casefold() for term in expand_search_terms(skill)]
        # Every requested skill must match; aliases within a skill use OR.
        # EXISTS avoids duplicate candidates/counts when several rows match.
        conditions.append(Candidate.skills.any(func.lower(func.trim(CandidateSkill.skill_name)).in_(terms)))

    ordering = {
        "newest": (Candidate.created_at.desc(), Candidate.candidate_id.asc()),
        "oldest": (Candidate.created_at.asc(), Candidate.candidate_id.asc()),
        "name_asc": (func.lower(Candidate.full_name).asc(), Candidate.candidate_id.asc()),
        "experience_desc": (case((Candidate.total_years_experience.is_(None), 1), else_=0),
                            Candidate.total_years_experience.desc(), Candidate.candidate_id.asc()),
    }[sort]
    with db_session.SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(Candidate).where(*conditions))
        candidates = session.scalars(select(Candidate).where(*conditions).options(
            load_only(Candidate.candidate_id, Candidate.full_name, Candidate.email,
                      Candidate.applied_position, Candidate.total_years_experience,
                      Candidate.posting_id, Candidate.photo_object_key, Candidate.created_at, Candidate.updated_at),
            selectinload(Candidate.skills),
            selectinload(Candidate.posting).selectinload(JobPosting.department),
        ).order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
        return {"items": [_summary(candidate) for candidate in candidates], "total": total,
                "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size,
                "has_next": page * page_size < total}


def get_candidate(candidate_id: str):
    require_admin()
    with db_session.SessionLocal() as session:
        candidate = session.scalar(select(Candidate).where(Candidate.candidate_id == candidate_id).options(
            selectinload(Candidate.skills),
            selectinload(Candidate.posting).selectinload(JobPosting.department),
            selectinload(Candidate.experience), selectinload(Candidate.education),
            selectinload(Candidate.certificates), selectinload(Candidate.projects),
        ))
        if candidate is None:
            raise CandidateNotFound()
        result = _summary(candidate)
        result.update({
            "phone": candidate.phone, "raw_text": candidate.raw_text,
            "experience": [{key: getattr(row, key) for key in
                            ("company", "title", "start_date", "end_date", "description")}
                           for row in sorted(candidate.experience, key=lambda row: row.id)],
            "education": [{key: getattr(row, key) for key in
                           ("school", "degree", "field", "graduation_year")}
                          for row in sorted(candidate.education, key=lambda row: row.id)],
            "certificates": [{key: getattr(row, key) for key in
                              ("name", "issuer", "issue_date", "credential_id")}
                             for row in sorted(candidate.certificates, key=lambda row: row.id)],
            "projects": [{**{key: getattr(row, key) for key in
                             ("name", "role", "description", "start_date", "end_date")},
                          "tech_stack": [term.strip() for term in (row.tech_stack or "").split(",") if term.strip()]}
                         for row in sorted(candidate.projects, key=lambda row: row.id)],
        })
        return result

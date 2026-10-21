"""Admin HTTP use cases; reuse CV-based generation and save only validated sets."""
import hashlib
import json

from sqlalchemy import delete, select

from src.auth.service import require_admin
from src.candidates.errors import CandidateNotFound
from src.db import session as db_session
from src.db.models import Candidate, InterviewQuestion
from src.interview import question_generator as generator
from src.interview.concurrency import interview_lock, is_generating
from src.interview.errors import InterviewConflict


def _load(db, candidate_id, *, lock=False):
    statement = select(Candidate).where(Candidate.candidate_id == candidate_id)
    candidate = db.scalar(statement.with_for_update() if lock else statement)
    if candidate is None:
        raise CandidateNotFound()
    rows = db.scalars(select(InterviewQuestion).where(
        InterviewQuestion.candidate_id == candidate_id).order_by(InterviewQuestion.id)).all()
    return candidate, rows


def _response(candidate, rows):
    items = [{"id": row.id, "question": row.question_text, "category": row.category,
              "cv_section": row.cv_section, "evidence_quote": row.evidence_quote} for row in rows]
    revision = hashlib.sha256(json.dumps([candidate.candidate_id,
        hashlib.sha256((candidate.raw_text or "").encode()).hexdigest(), items],
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"candidate_id": candidate.candidate_id, "items": items, "revision": revision,
            "has_cv": bool((candidate.raw_text or "").strip()), "is_generating": is_generating(candidate.candidate_id)}


def _check_revision(state, expected_revision):
    if state["revision"] != expected_revision:
        raise InterviewConflict("STALE_INTERVIEW_SET", "CV hoặc bộ câu hỏi đã thay đổi. Hãy tải lại trước khi thao tác.")


def get_questions(candidate_id):
    require_admin()
    with db_session.SessionLocal() as db:
        return _response(*_load(db, candidate_id))


def generate_questions(candidate_id, *, max_questions, expected_revision, replace_existing=False):
    require_admin()
    with interview_lock(candidate_id, generating=True):
        with db_session.SessionLocal() as db:
            candidate, rows = _load(db, candidate_id)
            state = _response(candidate, rows)
            _check_revision(state, expected_revision)
            if rows and not replace_existing:
                raise InterviewConflict("INTERVIEW_REPLACE_REQUIRED", "Cần xác nhận thay bộ câu hỏi đã lưu.")
            cv_text = candidate.raw_text
        questions = generator.build_interview_questions(candidate_id, cv_text, max_questions)
        # Long model calls may outlive a revoked session. Check again before save.
        require_admin()
        with db_session.SessionLocal() as db:
            candidate, rows = _load(db, candidate_id, lock=True)
            _check_revision(_response(candidate, rows), expected_revision)
            db.execute(delete(InterviewQuestion).where(InterviewQuestion.candidate_id == candidate_id))
            db.add_all([InterviewQuestion(candidate_id=candidate_id, question_text=q.question,
                category=q.category.value, cv_section=q.cv_section, evidence_quote=q.evidence_quote) for q in questions])
            db.flush()
            result = _response(*_load(db, candidate_id))
            db.commit()
    result["is_generating"] = False
    return result


def delete_questions(candidate_id, *, expected_revision):
    require_admin()
    with interview_lock(candidate_id), db_session.SessionLocal() as db:
        candidate, rows = _load(db, candidate_id, lock=True)
        _check_revision(_response(candidate, rows), expected_revision)
        db.execute(delete(InterviewQuestion).where(InterviewQuestion.candidate_id == candidate_id))
        db.flush()
        result = _response(candidate, [])
        db.commit()
    return result

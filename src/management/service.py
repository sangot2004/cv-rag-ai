"""Admin operations. DTOs never expose password hashes or sessions."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from src.auth import service as auth
from src.candidates.errors import CandidateNotFound
from src.db import session as database
from src.db.models import AppUser, Candidate, Department, JobPosting
from src.management.errors import ManagementError
from src.ingestion.locking import named_lock


def page_result(db, query, page, page_size, render):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    return dict(items=[render(row) for row in rows], total=total, page=page, page_size=page_size,
                has_next=page * page_size < total)


def departments(*, page=1, page_size=20, q=None):
    auth.require_admin()
    counts = select(JobPosting.department_id, func.count(JobPosting.posting_id).label("postings")).group_by(JobPosting.department_id).subquery()
    cvs = select(JobPosting.department_id, func.count(Candidate.candidate_id).label("cvs")).join(
        Candidate, Candidate.posting_id == JobPosting.posting_id).group_by(JobPosting.department_id).subquery()
    query = select(Department, func.coalesce(counts.c.postings, 0), func.coalesce(cvs.c.cvs, 0)).outerjoin(
        counts, counts.c.department_id == Department.department_id).outerjoin(cvs, cvs.c.department_id == Department.department_id)
    if q:
        query = query.where(Department.department_name.icontains(q, autoescape=True))
    with database.SessionLocal() as db:
        return page_result(db, query.order_by(Department.department_name, Department.department_id), page, page_size,
                           lambda r: dict(department_id=r[0].department_id, department_name=r[0].department_name, posting_count=r[1], cv_count=r[2]))


def create_department(department_name):
    auth.require_admin()
    with named_lock("department:" + department_name.casefold()) as locked:
        if not locked:
            raise ManagementError("DEPARTMENT_BUSY", "Tên phòng ban đang được tạo. Hãy tải lại danh sách.")
        return _create_department(department_name)


def _create_department(department_name):
    with database.SessionLocal() as db:
        if db.scalar(select(Department).where(func.lower(Department.department_name) == department_name.lower())):
            raise ManagementError("DEPARTMENT_EXISTS", "Tên phòng ban đã tồn tại.")
        row = Department(department_name=department_name)
        db.add(row)
        db.flush()
        result = dict(department_id=row.department_id, department_name=row.department_name, posting_count=0, cv_count=0)
        db.commit()
        return result


def postings(*, page=1, page_size=20, q=None, department_id=None):
    auth.require_admin()
    counts = select(Candidate.posting_id, func.count().label("cvs")).group_by(Candidate.posting_id).subquery()
    query = select(JobPosting, Department.department_name, func.coalesce(counts.c.cvs, 0)).join(
        Department).outerjoin(counts, counts.c.posting_id == JobPosting.posting_id)
    if department_id:
        query = query.where(JobPosting.department_id == str(department_id))
    if q:
        query = query.where(JobPosting.position_title.icontains(q, autoescape=True))
    with database.SessionLocal() as db:
        return page_result(db, query.order_by(JobPosting.created_at.desc(), JobPosting.posting_id), page, page_size, posting_view)


def posting_view(r):
    p = r[0]
    return dict(posting_id=p.posting_id, department_id=p.department_id, department_name=r[1],
                position_title=p.position_title, is_active=p.is_active, cv_count=r[2], created_at=p.created_at)


def create_posting(department_id, position_title):
    auth.require_admin()
    with named_lock("posting:" + department_id + ":" + position_title.casefold()) as locked:
        if not locked:
            raise ManagementError("POSTING_BUSY", "Vị trí đang được tạo. Hãy tải lại danh sách.")
        return _create_posting(department_id, position_title)


def _create_posting(department_id, position_title):
    with database.SessionLocal() as db:
        dept = db.get(Department, department_id)
        if dept is None:
            raise ManagementError("DEPARTMENT_NOT_FOUND", "Phòng ban không tồn tại.", 404)
        if db.scalar(select(JobPosting).where(JobPosting.department_id == department_id,
                                              func.lower(JobPosting.position_title) == position_title.lower())):
            raise ManagementError("POSTING_EXISTS", "Vị trí tuyển dụng đã tồn tại trong phòng ban.")
        row = JobPosting(department_id=department_id, position_title=position_title)
        db.add(row)
        db.flush()
        result = posting_view((row, dept.department_name, 0))
        db.commit()
        return result


def user_view(row):
    u, dept = row
    return dict(user_id=u.user_id, username=u.username, role=u.role, department_id=u.department_id,
                department_name=dept, is_active=u.is_active, created_at=u.created_at)


def users(*, page=1, page_size=20, q=None, department_id=None, role=None, active=None):
    auth.require_admin()
    query = select(AppUser, Department.department_name).outerjoin(Department)
    if q:
        query = query.where(AppUser.username.icontains(q, autoescape=True))
    if department_id:
        query = query.where(AppUser.department_id == str(department_id))
    if role:
        query = query.where(AppUser.role == role)
    if active is not None:
        query = query.where(AppUser.is_active == active)
    with database.SessionLocal() as db:
        return page_result(db, query.order_by(AppUser.created_at.desc(), AppUser.user_id), page, page_size, user_view)


def create_user(username, password, role, department_id):
    auth.require_admin()
    try:
        identifier = auth.create_user(username, password.get_secret_value(), role, department_id)
    except IntegrityError:
        raise ManagementError("USERNAME_EXISTS", "Tên tài khoản đã tồn tại.") from None
    except ValueError as exc:
        raise ManagementError("USER_INVALID", str(exc), 422) from None
    with database.SessionLocal() as db:
        return user_view(db.execute(select(AppUser, Department.department_name).outerjoin(Department).where(AppUser.user_id == identifier)).one())


def set_active(user_id, active):
    auth.require_admin()
    try:
        auth.set_user_active(user_id, active)
    except ValueError as exc:
        raise ManagementError("USER_STATE_CONFLICT", str(exc)) from None
    return {"user_id": user_id, "is_active": active}


def assign_posting(candidate_id, posting_id, expected_posting_id):
    auth.require_admin()
    with database.SessionLocal() as db:
        candidate = db.scalar(select(Candidate).where(Candidate.candidate_id == candidate_id).with_for_update())
        if candidate is None:
            raise CandidateNotFound()
        if candidate.posting_id != expected_posting_id:
            raise ManagementError("CANDIDATE_ASSIGNMENT_CHANGED", "Vị trí đã thay đổi. Tải lại hồ sơ trước khi gán.")
        if posting_id:
            posting = db.get(JobPosting, posting_id)
            if posting is None or not posting.is_active:
                raise ManagementError("POSTING_UNAVAILABLE", "Vị trí không tồn tại hoặc đã ngừng tuyển.", 422)
        candidate.posting_id = posting_id
        db.commit()
    # Retrieval resolves department scope against current SQL ownership; no
    # department payload is cached into the vector/BM25 index.
    return {"candidate_id": candidate_id, "posting_id": posting_id}

"""Department/posting store: position matching and listing, on an in-memory DB."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.models import Base, JobPosting
from src.retrieval import department_store as store


@pytest.fixture
def factory(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(store, "SessionLocal", session_factory)
    return session_factory


def test_create_and_list_departments(factory):
    first = store.create_department("Engineering")
    second = store.create_department("Sales")
    assert first != second
    assert {d["department_name"] for d in store.list_departments()} == {"Engineering", "Sales"}
    assert {d["department_id"] for d in store.list_departments()} == {first, second}


def test_list_postings_filters_by_department_and_hides_inactive(factory):
    eng = store.create_department("Engineering")
    sales = store.create_department("Sales")
    backend = store.create_job_posting(eng, "Backend Engineer")
    store.create_job_posting(sales, "Account Executive")
    retired = store.create_job_posting(eng, "Retired Role")
    with factory() as db:
        db.get(JobPosting, retired).is_active = False
        db.commit()

    assert {p["position_title"] for p in store.list_job_postings()} == {"Backend Engineer", "Account Executive"}
    only_eng = store.list_job_postings(eng)
    assert [p["posting_id"] for p in only_eng] == [backend]
    assert only_eng[0]["department_id"] == eng


@pytest.mark.parametrize("applied", [None, "", "   "])
def test_match_ignores_empty_position(factory, applied):
    store.create_job_posting(store.create_department("Engineering"), "Backend Engineer")
    assert store.match_posting_for_position(applied) is None


@pytest.mark.parametrize("applied", [
    "backend engineer",              # case-insensitive
    "  Backend Engineer  ",          # surrounding whitespace
    "Senior Backend Engineer (HCM)",  # posting title contained in the applied text
    "Backend",                       # applied text contained in the posting title
])
def test_match_finds_posting_loosely(factory, applied):
    posting = store.create_job_posting(store.create_department("Engineering"), "Backend Engineer")
    assert store.match_posting_for_position(applied) == posting


def test_match_returns_none_without_overlap(factory):
    store.create_job_posting(store.create_department("Engineering"), "Backend Engineer")
    assert store.match_posting_for_position("Kế toán trưởng") is None


def test_match_skips_inactive_postings(factory):
    posting = store.create_job_posting(store.create_department("Engineering"), "Backend Engineer")
    with factory() as db:
        db.get(JobPosting, posting).is_active = False
        db.commit()
    assert store.match_posting_for_position("Backend Engineer") is None

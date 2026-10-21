from datetime import date, datetime
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError

from src.auth.errors import AuthenticationRequired, Forbidden
from src.auth.service import auth_scope
from src.candidates import service
from src.db import session as db_session
from src.db.models import (Candidate, CandidateCertificate, CandidateEducation,
                           CandidateExperience, CandidateProject, CandidateSkill,
                           Department, IngestionJob, JobPosting)


def identifier(number):
    return str(UUID(int=number))


@pytest.fixture
def candidates(api):
    ids = [identifier(i) for i in range(1, 6)]
    dept_a, dept_b = identifier(100), identifier(101)
    post_a, post_b = identifier(200), identifier(201)
    with api.db() as db:
        db.add_all([Department(department_id=dept_a, department_name="Engineering"),
                    Department(department_id=dept_b, department_name="Sales")])
        db.flush()
        db.add_all([JobPosting(posting_id=post_a, department_id=dept_a, position_title="Data Engineer"),
                    JobPosting(posting_id=post_b, department_id=dept_b, position_title="Sales", is_active=False)])
        for i, (name, years, posting, skills) in enumerate([
            ("Ada Nguyen", 4.5, post_a, ["Python", "Py", "SQL"]),
            ("Binh Tran", 0, post_a, ["PY", "JavaScript"]),
            ("Chi Le", 8, post_b, ["SQL"]),
            ("Dung Vo", None, None, []),
            ("A_100%", 1, post_a, ["Postgres"]),
        ]):
            job_id = identifier(300 + i)
            db.add(IngestionJob(job_id=job_id, source_type="upload", source_reference="fixture",
                                minio_bucket="private-bucket", minio_object_key="private/key.pdf",
                                original_filename="fixture.pdf", file_type="pdf"))
            db.flush()
            db.add(Candidate(candidate_id=ids[i], full_name=name, email=f"person{i}@example.com",
                             phone="0123456789" if i == 0 else None, applied_position="Data Engineer" if posting == post_a else "Sales",
                             total_years_experience=years, posting_id=posting, source_job_id=job_id,
                             raw_text="CV content" if i == 0 else None, content_hash="a" * 64,
                             photo_object_key="private/photo.jpg" if i == 0 else None, created_at=datetime(2026, 1, 1),
                             updated_at=datetime(2026, 1, 2)))
            db.flush()
            db.add_all([CandidateSkill(candidate_id=ids[i], skill_name=skill) for skill in skills])
        db.add(CandidateExperience(candidate_id=ids[0], company="Example", title="Engineer",
                                   start_date=date(2020, 1, 1), end_date=None, description="Build pipelines"))
        db.add(CandidateEducation(candidate_id=ids[0], school="University", degree="Bachelor", field="IT", graduation_year=2020))
        db.add(CandidateCertificate(candidate_id=ids[0], name="Cloud", issuer="Example", issue_date=date(2022, 2, 2), credential_id="credential"))
        db.add(CandidateProject(candidate_id=ids[0], name="Warehouse", role="Engineer", tech_stack=" Python, SQL, ",
                                description="ETL", start_date=date(2023, 1, 1)))
        db.commit()
    return api, ids, dept_a, dept_b, post_a, post_b


def get_list(api, params=None):
    response = api.client.get("/api/candidates", headers=api.headers("admin"), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_list_pagination_stable_ties_and_projection(candidates):
    api, ids, *_ = candidates
    first = get_list(api, {"page_size": 2})
    second = get_list(api, {"page_size": 2, "page": 2})
    third = get_list(api, {"page_size": 2, "page": 3})
    assert first["total"] == 5 and first["total_pages"] == 3
    assert first["has_next"] and second["has_next"] and not third["has_next"]
    assert [c["candidate_id"] for page in (first, second, third) for c in page["items"]] == ids
    assert get_list(api, {"page_size": 2}) == first
    assert get_list(api, {"page": 100})["items"] == []
    row = first["items"][0]
    assert row["created_at"] == "2026-01-01T00:00:00Z"
    assert row["posting"]["department"]["department_name"] == "Engineering"
    assert row["skills"] == ["Py", "Python", "SQL"]
    assert row["has_photo"] is True
    assert second["items"][0]["has_photo"] is False
    assert not {"raw_text", "content_hash", "source_job_id", "photo_object_key", "phone"}.intersection(row)
    response = api.client.get("/api/candidates", headers=api.headers("admin"))
    assert response.headers["cache-control"] == "private, no-store"


def test_search_is_literal_and_bound(candidates):
    api, ids, *_ = candidates
    for q, expected in [("ada", [ids[0]]), ("PERSON1@", [ids[1]]), ("%", [ids[4]]),
                        ("_", [ids[4]]), ("' OR 1=1 --", [])]:
        result = get_list(api, {"q": q})
        assert [c["candidate_id"] for c in result["items"]] == expected
        assert result["total"] == len(expected)


def test_skill_aliases_all_matching_and_unique_count(candidates):
    api, ids, *_ = candidates
    assert get_list(api, {"skills": "python"})["total"] == 2
    rows = get_list(api, [("skills", "python"), ("skills", "SQL")])
    assert rows["total"] == 1 and rows["items"][0]["candidate_id"] == ids[0]
    assert get_list(api, {"skills": "postgresql"})["items"][0]["candidate_id"] == ids[4]
    assert get_list(api, {"skills": "java"})["total"] == 0
    assert get_list(api, {"skills": "js"})["total"] == 1


def test_newest_oldest_and_name_sort(candidates):
    api, ids, *_ = candidates
    with api.db() as db:
        db.get(Candidate, ids[3]).created_at = datetime(2027, 1, 1)
        db.commit()
    assert get_list(api, {"sort": "newest"})["items"][0]["candidate_id"] == ids[3]
    assert get_list(api, {"sort": "oldest"})["items"][-1]["candidate_id"] == ids[3]
    names = [c["full_name"] for c in get_list(api, {"sort": "name_asc"})["items"]]
    assert names == sorted(names, key=str.casefold)


def test_department_posting_position_and_experience_filters(candidates):
    api, ids, dept_a, dept_b, post_a, post_b = candidates
    assert get_list(api, {"department_id": dept_a})["total"] == 3
    assert get_list(api, {"posting_id": post_b})["items"][0]["candidate_id"] == ids[2]
    assert get_list(api, {"department_id": dept_b, "posting_id": post_a})["total"] == 0
    assert get_list(api, {"department_id": identifier(999)})["total"] == 0
    assert get_list(api, {"position": "engineer"})["total"] == 3
    assert get_list(api, {"min_years_experience": 0, "max_years_experience": 0})["items"][0]["candidate_id"] == ids[1]
    assert get_list(api, {"min_years_experience": 0})["total"] == 4
    result = get_list(api, {"department_id": dept_a, "skills": "python", "min_years_experience": 1})
    assert result["total"] == 1 and result["items"][0]["candidate_id"] == ids[0]
    sorted_rows = get_list(api, {"sort": "experience_desc"})["items"]
    assert [row["candidate_id"] for row in sorted_rows] == [ids[2], ids[0], ids[4], ids[1], ids[3]]


def test_detail_sections_nullable_fields_and_no_storage_secrets(candidates, monkeypatch):
    api, ids, *_ = candidates
    def no_model():
        raise AssertionError("Candidate reads must not call the model")
    monkeypatch.setattr(api.router, "_get_graph", no_model)
    response = api.client.get(f"/api/candidates/{ids[0]}", headers=api.headers("admin"))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()
    assert data["raw_text"] == "CV content" and data["phone"] == "0123456789"
    assert data["experience"][0]["start_date"] == "2020-01-01"
    assert data["experience"][0]["end_date"] is None
    assert data["education"][0]["graduation_year"] == 2020
    assert data["certificates"][0]["credential_id"] == "credential"
    assert data["projects"][0]["tech_stack"] == ["Python", "SQL"]
    assert data["projects"][0]["start_date"] == "2023-01-01"
    assert "private/" not in response.text and "private-bucket" not in response.text
    assert not {"photo_object_key", "source_job_id", "content_hash"}.intersection(data)
    empty = api.client.get(f"/api/candidates/{ids[3]}", headers=api.headers("admin")).json()
    assert empty["posting"] is None and empty["total_years_experience"] is None
    assert empty["raw_text"] is None
    assert all(empty[key] == [] for key in ("skills", "experience", "education", "certificates", "projects"))
    assert api.extracted == [] and api.observations == []


def test_auth_admin_only_and_direct_service_guard(candidates):
    api, ids, dept_a, *_ = candidates
    for path in ("/api/candidates", f"/api/candidates/{ids[0]}", f"/api/candidates/{identifier(999)}"):
        assert api.client.get(path).status_code == 401
        for name in ("alice", "bobby", "carol"):
            result = api.client.get(path, headers=api.headers(name))
            assert result.status_code == 403
            assert result.json()["error"]["code"] == "FORBIDDEN"
    assert api.client.get("/api/candidates", headers=api.headers(), params={"department_id": dept_a}).status_code == 403
    with pytest.raises(AuthenticationRequired):
        service.list_candidates()
    with auth_scope(api.tokens["alice"]), pytest.raises(Forbidden):
        service.get_candidate(ids[0])


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page_size": 101}, {"page_size": 0}, {"page": "1.5"},
    {"q": " "}, {"q": "x" * 201}, {"position": " "}, {"skills": " "},
    {"skills": "x" * 101}, [("skills", str(i)) for i in range(21)],
    {"min_years_experience": -1}, {"min_years_experience": "nan"},
    {"max_years_experience": "inf"}, {"min_years_experience": 3, "max_years_experience": 2},
    {"department_id": "bad"}, {"posting_id": "bad"}, {"sort": "raw_text"}, {"role": "admin"},
])
def test_invalid_filters(api, params):
    response = api.client.get("/api/candidates", headers=api.headers("admin"), params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_empty_missing_invalid_id_and_database_error(api, monkeypatch):
    result = get_list(api)
    assert result == {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0, "has_next": False}
    response = api.client.get(f"/api/candidates/{identifier(999)}", headers=api.headers("admin"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CANDIDATE_NOT_FOUND"
    assert api.client.get("/api/candidates/not-a-uuid", headers=api.headers("admin")).status_code == 422
    def fail():
        raise OperationalError("SELECT SECRET", {}, Exception("password=SECRET"))
    monkeypatch.setattr(db_session, "SessionLocal", fail)
    response = api.client.get("/api/candidates", headers=api.headers("admin"))
    assert response.status_code == 503
    assert "SECRET" not in response.text


def test_portrait_binary_auth_projection_and_read_only_storage(candidates, monkeypatch):
    from types import SimpleNamespace
    from src.candidates import photos

    api, ids, *_ = candidates
    data = b"\x89PNG\r\n\x1a\nfixture"
    calls = []
    def storage(**kwargs):
        assert kwargs["ensure_bucket"] is False
        assert kwargs["http_client"] is not None
        return SimpleNamespace(download_bytes=lambda key: calls.append(key) or data)
    monkeypatch.setattr(photos, "MinioStorage", storage)
    url = f"/api/candidates/{ids[0]}/photo"
    response = api.client.get(url + "?object_key=another/private.jpg", headers=api.headers("admin"))
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]
    assert calls == ["private/photo.jpg"]
    assert api.client.get(f"/api/candidates/{ids[0]}", headers=api.headers("admin")).json()["has_photo"] is True
    assert api.client.get(f"/api/candidates/{ids[1]}", headers=api.headers("admin")).json()["has_photo"] is False
    calls.clear()
    assert api.client.get(url).status_code == 401
    assert api.client.get(url, headers=api.headers("alice")).status_code == 403
    assert api.client.get(f"/api/candidates/{identifier(999)}/photo", headers=api.headers("alice")).status_code == 403
    for candidate_id, code in [(ids[1], "CANDIDATE_PHOTO_NOT_FOUND"), (identifier(999), "CANDIDATE_NOT_FOUND")]:
        response = api.client.get(f"/api/candidates/{candidate_id}/photo", headers=api.headers("admin"))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == code
    assert not calls  # No object-store reads before permission/metadata checks.
    assert api.client.get("/api/candidates/invalid/photo", headers=api.headers("admin")).status_code == 422
    with pytest.raises(AuthenticationRequired):
        photos.get_candidate_photo(ids[0])
    with auth_scope(api.tokens["alice"]), pytest.raises(Forbidden):
        photos.get_candidate_photo(ids[0])


@pytest.mark.parametrize("case, status", [("NoSuchKey", 404), ("NoSuchBucket", 404), ("AccessDenied", 503), ("network", 503), ("invalid", 404)])
def test_portrait_storage_errors_do_not_leak_details(candidates, monkeypatch, case, status):
    from types import SimpleNamespace
    from minio.error import S3Error
    from urllib3.exceptions import MaxRetryError
    from src.candidates import photos

    api, ids, *_ = candidates
    def download(key):
        if case == "invalid":
            return b"<svg onload='secret()'>SECRET private/photo.jpg</svg>"
        if case == "network":
            raise MaxRetryError(None, "SECRET/private/photo.jpg")
        raise S3Error(response=None, code=case, message="SECRET", resource="/private/photo.jpg", request_id="private-request", host_id="private-host")
    monkeypatch.setattr(photos, "MinioStorage", lambda **kwargs: SimpleNamespace(download_bytes=download))
    response = api.client.get(f"/api/candidates/{ids[0]}/photo", headers=api.headers("admin"))
    assert response.status_code == status
    assert "SECRET" not in response.text and "private/photo.jpg" not in response.text
    assert get_list(api)["total"] == 5

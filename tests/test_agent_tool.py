"""
Test các agent tool mới: candidate_detail, compare, stats, certificate/project search,
recent candidates.

Yêu cầu trước khi chạy:
- Đã có ít nhất 2 candidate trong DB (chạy test_pipeline.py trước để có data)
- Đã build bm25 index nếu tool nào cần tới retrieval

Cách chạy:
    PYTHONPATH=. python tests/test_agent_tool.py
"""

from pprint import pprint
import sys

from src.retrieval.sql_query_tool import list_recent_candidates
from src.agent.tools.recent_candidates_tool import list_recent_cvs
from src.agent.tools.certificate_project_tool import (
    find_candidates_by_certificate,
    find_candidates_by_project_tech,
)
from src.agent.tools.stats_tool import count_candidates
from src.agent.tools.compare_tool import compare_candidates
from src.agent.tools.candidate_detail_tool import get_candidate_detail

sys.path.insert(0, ".")


def step(title: str):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def run_case(name: str, fn, *args, **kwargs):
    """Chạy 1 tool, bắt lỗi nếu có, in format từng dòng và dừng chờ Enter."""
    print(f"\n--- {name} ---")
    try:
        result = fn(*args, **kwargs)
        if result is None:
            print("  !! Trả về None — có thể là lỗi logic, kiểm tra lại tool")
            input("\n[Nhấn Enter để tiếp tục...]")
            return False

        # In kết quả định dạng từng dòng, thụt lề rõ ràng
        pprint(result, width=120, indent=2)

        # Dừng màn hình chờ người dùng bấm Enter xem xong mới chạy tiếp
        input("\n[Nhấn Enter để tiếp tục test case tiếp theo...]")
        return True
    except Exception as e:
        print(f"  !! Lỗi: {type(e).__name__}: {e}")
        input("\n[Lỗi xảy ra. Nhấn Enter để tiếp tục...]")
        return False


def main():
    results = {}

    # Chuẩn bị: lấy candidate_id thật từ DB để dùng cho các tool cần ID
    step("Chuẩn bị: lấy candidate mẫu từ DB")
    recent = list_recent_candidates(limit=2)
    print("Candidate có sẵn:", [(c["candidate_id"], c["full_name"]) for c in recent])

    if not recent:
        print("!! Không có candidate nào trong DB — chạy test_pipeline.py trước để có data")
        sys.exit(1)

    cid_1 = recent[0]["candidate_id"]

    # 1. get_candidate_detail
    step("Test 1: get_candidate_detail")
    results["get_candidate_detail"] = run_case(
        "get_candidate_detail(candidate_id hợp lệ)",
        get_candidate_detail.invoke,
        {"candidate_id": cid_1},
    )
    # case lỗi: candidate_id không tồn tại — tool phải trả về thông báo rõ ràng, không crash
    results["get_candidate_detail_invalid_id"] = run_case(
        "get_candidate_detail(candidate_id KHÔNG tồn tại)",
        get_candidate_detail.invoke,
        {"candidate_id": "00000000-0000-0000-0000-000000000000"},
    )

    # 2. compare_candidates — cần ít nhất 2 candidate
    step("Test 2: compare_candidates")
    if len(recent) >= 2:
        cid_2 = recent[1]["candidate_id"]
        results["compare_candidates"] = run_case(
            "compare_candidates(2 candidate hợp lệ)",
            compare_candidates.invoke,
            {"candidate_ids": [cid_1, cid_2]},
        )
    else:
        print("!! Chỉ có 1 candidate trong DB — bỏ qua test compare_candidates "
              "(cần seed thêm data để test đầy đủ)")
        results["compare_candidates"] = None

    # case lỗi: chỉ truyền 1 ID — tool nên xử lý gracefully, không crash
    results["compare_candidates_single_id"] = run_case(
        "compare_candidates(chỉ 1 candidate_id — case lỗi)",
        compare_candidates.invoke,
        {"candidate_ids": [cid_1]},
    )

    # 3. count_candidates
    step("Test 3: count_candidates")
    results["count_candidates_all"] = run_case(
        "count_candidates(không filter — đếm tất cả)",
        count_candidates.invoke,
        {"skills": None, "min_years_experience": 0},
    )
    results["count_candidates_by_skill"] = run_case(
        "count_candidates(filter theo skill Python)",
        count_candidates.invoke,
        {"skills": ["Python"], "min_years_experience": 0},
    )
    results["count_candidates_no_match"] = run_case(
        "count_candidates(skill không tồn tại — kỳ vọng count=0, không lỗi)",
        count_candidates.invoke,
        {"skills": ["COBOL_KHONG_TON_TAI"], "min_years_experience": 0},
    )

    # 4. find_candidates_by_certificate
    step("Test 4: find_candidates_by_certificate")
    results["find_by_certificate"] = run_case(
        "find_candidates_by_certificate('AWS')",
        find_candidates_by_certificate.invoke,
        {"certificate_name": "AWS"},
    )
    results["find_by_certificate_no_match"] = run_case(
        "find_candidates_by_certificate(chứng chỉ không tồn tại)",
        find_candidates_by_certificate.invoke,
        {"certificate_name": "CHUNG_CHI_KHONG_TON_TAI_XYZ"},
    )

    # 5. find_candidates_by_project_tech
    step("Test 5: find_candidates_by_project_tech")
    results["find_by_project_tech"] = run_case(
        "find_candidates_by_project_tech('Python')",
        find_candidates_by_project_tech.invoke,
        {"tech": "Python"},
    )

    # 6. list_recent_cvs
    step("Test 6: list_recent_cvs")
    results["list_recent_cvs"] = run_case(
        "list_recent_cvs(limit=3)",
        list_recent_cvs.invoke,
        {"limit": 3},
    )
    results["list_recent_cvs_limit_0"] = run_case(
        "list_recent_cvs(limit=0 — case biên)",
        list_recent_cvs.invoke,
        {"limit": 0},
    )

    # Tổng kết
    step("TỔNG KẾT")
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for name, ok in results.items():
        status = "PASS" if ok is True else ("FAIL" if ok is False else "SKIP")
        print(f"  [{status}] {name}")

    print(f"\nTổng: {passed} pass, {failed} fail, {skipped} skip / {len(results)} case")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

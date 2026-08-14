import logging

from src.agent.router import ask
from src.evaluation.evaluator import evaluate_candidate

logger = logging.getLogger(__name__)


def query_candidates(question: str) -> dict:
    """Nhận câu hỏi từ hr (qua be), trả json anwer
    input: question(str) -
    Output: {"answer": str, "error": str | None}
    """
    try:
        answer = ask(question)
        return {"answer": answer, "error": None}
    except Exception as e:
        logger.exception("query_candidates lỗi với question=%r", question)
        return {"answer": None, "error": str(e)}


def evaluate_candidate_for_job(candidate_id: str, job_description: str) -> dict:
    """Đánh giá 1 ứng viên theo JD — dùng riêng khi Backend cần kết quả có
    cấu trúc (điểm số) thay vì câu trả lời dạng text tự do như query_candidates.

    Input:  candidate_id (str), job_description (str)
    Output: dict JSON-serializable, hoặc {"error": str} nếu candidate không tồn tại
    """
    try:
        result = evaluate_candidate(candidate_id, job_description)
        if result is None:
            return {"error": f"candidate_id={candidate_id} không tồn tại"}
        return result.model_dump()
    except Exception as e:
        logger.exception("evaluate_candidate_for_job lỗi với candidate_id=%r", candidate_id)
        return {"error": str(e)}

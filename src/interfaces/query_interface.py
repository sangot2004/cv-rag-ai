import logging

from src.agent.router import ask
from src.evaluation.evaluator import evaluate_candidate
from src.ingestion.extraction.llm_extractor import extract_jd_data
from src.retrieval.candidate_ranking import rank_candidates_for_jd

logger = logging.getLogger(__name__)


def query_candidates(question: str, thread_id: str = "default") -> dict:
    try:
        answer = ask(question, thread_id=thread_id)
        return {"answer": answer, "error": None}
    except Exception as e:
        logger.exception("query_candidates lỗi với question=%r", question)
        return {"answer": None, "error": str(e)}


def evaluate_candidate_for_job(candidate_id: str, job_description: str) -> dict:
    try:
        result = evaluate_candidate(candidate_id, job_description)
        if result is None:
            return {"error": f"candidate_id={candidate_id} không tồn tại"}
        return result.model_dump()
    except Exception as e:
        logger.exception("evaluate_candidate_for_job lỗi với candidate_id=%r", candidate_id)
        return {"error": str(e)}


def parse_jd(jd_raw_text: str) -> dict:
    try:
        jd = extract_jd_data(jd_raw_text)
        return jd.model_dump()
    except Exception as e:
        logger.exception("parse_jd lỗi")
        return {"error": str(e)}


def rank_top_candidates(jd: dict, top_k: int = 5) -> dict:
    from src.schemas.jd_schema import JDSchema

    try:
        jd_schema = JDSchema(**jd)
        results = rank_candidates_for_jd(jd_schema, top_k=top_k)
        return {"results": results, "error": None}
    except Exception as e:
        logger.exception("rank_top_candidates lỗi")
        return {"results": [], "error": str(e)}

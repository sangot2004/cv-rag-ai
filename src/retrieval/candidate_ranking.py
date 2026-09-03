import logging

from src.evaluation.evaluator import evaluate_candidate
from src.retrieval.hybrid_retriever import hybrid_search
from src.retrieval.reranker import rerank
from src.retrieval.sql_query_tool import search_candidates_sql
from src.schemas.jd_schema import JDSchema

logger = logging.getLogger(__name__)

MAX_TOP_K = 10

MAX_SQL_PREFILTER_POOL = 200


def rank_candidates_for_jd(jd: JDSchema, top_k: int = 5) -> list[dict]:
    top_k = min(top_k, MAX_TOP_K)

    prefiltered = search_candidates_sql(
        skills=jd.required_skills or None,
        min_years_experience=jd.min_years_experience,
        limit=MAX_SQL_PREFILTER_POOL,
    )
    prefiltered_ids = {c["candidate_id"] for c in prefiltered}

    logger.info(
        "rank_candidates_for_jd: JD=%r, lọc SQL còn %d candidate (trước semantic ranking)",
        jd.position_title, len(prefiltered_ids),
    )

    if not prefiltered_ids:
        logger.warning("Không candidate nào khớp tiêu chí lọc cứng của JD - trả về rỗng.")
        return []

    # xếp hạng ngữ nghĩa trong pool đã lọc
    raw_results = hybrid_search(jd.raw_text, top_k=MAX_SQL_PREFILTER_POOL)
    filtered_results = [
        r for r in raw_results if r["payload"].get("candidate_id") in prefiltered_ids
    ]

    if not filtered_results:
        logger.warning("Semantic search không khớp candiate nào trong pool đã lọc SQL.")
        return []

    reranked = rerank(jd.raw_text, filtered_results, top_k=top_k * 3)

    best_per_candidate: dict[str, float] = {}
    for r in reranked:
        cid = r["payload"].get("candidate_id")
        if cid and (cid not in best_per_candidate or r["rerank_score"] > best_per_candidate[cid]):
            best_per_candidate[cid] = r["rerank_score"]

    shortlist = sorted(best_per_candidate.items(), key=lambda x: x[1], reverse=True)[:top_k]
    logger.info("Sau rerank + gom theo candidate: shortlist %d người", len(shortlist))

    # Chấm điểm chi tiết cho đúng top K
    results = []
    for candidate_id, retrieval_score in shortlist:
        evaluation = evaluate_candidate(candidate_id, jd.raw_text)
        if evaluation is None:
            continue
        result = evaluation.model_dump()
        result["retrieval_score"] = round(retrieval_score, 3)
        results.append(result)

    results.sort(key=lambda x: x["overall_score"], reverse=True)
    return results

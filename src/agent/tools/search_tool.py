from langchain_core.tools import tool

from src.retrieval.hybrid_retriever import hybrid_search
from src.retrieval.reranker import rerank


@tool
def semantic_search_cv(query: str, top_k: int = 5) -> str:
    """Tìm kiếm ứng viên/thông tin CV bằng câu hỏi tự nhiên, không cần tiêu
    chí chính xác. Dùng khi câu hỏi mở kiểu "ai phù hợp với vị trí Data
    Engineer", "ứng viên nào có kinh nghiệm về machine learning", so sánh
    ứng viên... KHÔNG dùng cho câu hỏi có tiêu chí rõ ràng như "trên 3 năm
    kinh nghiệm" hay "biết Python" — trường hợp đó dùng filter_candidates_sql.
    """
    hybrid_results = hybrid_search(query, top_k=top_k * 3)
    if not hybrid_results:
        return "Không tìm thấy kết quả liên quan."

    reranked = rerank(query, hybrid_results, top_k=top_k)

    lines = []
    for r in reranked:
        payload = r["payload"]
        lines.append(
            f"- Candidate {payload.get('candidate_id')} ({payload.get('section_type')}): "
            f"{payload.get('chunk_text', '')[:300]}"
        )
    return "\n".join(lines)

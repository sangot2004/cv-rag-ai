import logging
from src.retrieval.sql_query_tool import search_candidates_sql, get_candidate_full_profile
from src.retrieval.bm25_index import build_and_store_index, load_index, search_bm25
from src.retrieval.hybrid_retriever import hybrid_search
from src.retrieval.reranker import rerank
from src.vectorstore.qdrant_client import QdrantStore
from src.agent.tools.search_tool import semantic_search_cv
from src.agent.tools.sql_filter_tool import filter_candidates_sql
from src.agent.tools.evaluation_tool import evaluate_candidate_against_jd
from src.agent.router import ask
from src.interfaces.query_interface import query_candidates, evaluate_candidate_for_job

# Cấu hình logging chung
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def test_sql_retrieval():
    print("\n--- ĐANG CHẠY TEST: SQL Query Tool ---")
    results = search_candidates_sql(min_years_experience=0)
    print(f"📊 Tổng số candidate tìm thấy: {len(results)}")

    for r in results:
        print(f" - {r['full_name']} | {r['applied_position']} | {r['total_years_experience']} năm KN")

    if results:
        sample_id = results[0]["candidate_id"]
        print(f"\n🔍 Lấy full profile cho ID: {sample_id}...")
        profile = get_candidate_full_profile(sample_id)
        if profile:
            print(f"✅ Thành công! Họ tên: {profile['full_name']} | Kỹ năng: {profile['skills']}")
        else:
            print(f" Không tìm thấy profile chi tiết.")
    else:
        print("⚠️ Chưa có candidate nào trong DB.")


def test_qdrant_fetch_chunks():
    print("\n--- ĐANG CHẠY TEST: Qdrant Fetch All Chunks ---")
    store = QdrantStore()
    chunks = store.fetch_all_chunks()

    print(f"📊 Tổng số chunk trong Qdrant: {len(chunks)}")
    for c in chunks[:3]:
        section = c["payload"].get("section_type")
        text_snippet = c["payload"].get("chunk_text", "")[:60].replace("\n", " ")
        print(f" - [{section}] : {text_snippet}...")


def test_bm25_search():
    print("\n--- ĐANG CHẠY TEST: BM25 Index & Search ---")

    # 1. Test build và lưu vào Redis
    count = build_and_store_index()
    print(f"📊 Đã build BM25 thành công: {count} chunk")

    # 2. Test load index từ Redis
    index = load_index()
    print(f"📦 Load lại index từ Redis OK: {index is not None}")

    # 3. Test tìm kiếm từ khóa (ví dụ: "python")
    keyword = "python"
    results = search_bm25(keyword, top_k=3)
    print(f"🔍 Kết quả tìm kiếm cho từ khóa \"{keyword}\": {len(results)} kết quả")

    for r in results:
        snippet = r['payload'].get('chunk_text', '').replace('\n', ' ')[:60]
        print(f" - [Score: {r['score']:.2f}] {snippet}...")


def test_hybrid_search():
    print("\n--- ĐANG CHẠY TEST: Hybrid Search (Vector + BM25) ---")
    query_str = "kinh nghiệm lập trình"
    results = hybrid_search(query_str, top_k=5)

    print(f"📊 Tìm thấy {len(results)} kết quả cho câu hỏi: \"{query_str}\"")
    for r in results:
        score = r['combined_score']
        snippet = r['payload'].get('chunk_text', '').replace('\n', ' ')[:80]
        print(f"  [{score:.3f}] {snippet}...")


def test_hybrid_and_rerank():
    print("\n--- ĐANG CHẠY TEST: Hybrid Search + Reranker ---")
    query_str = "kinh nghiệm lập trình"

    # 1. Lấy kết quả từ Hybrid Search trước (lấy top 10 để rerank chọn ra top tốt nhất)
    results = hybrid_search(query_str, top_k=10)
    print(f"📊 Hybrid Search trả về {len(results)} kết quả ứng viên.")

    # 2. Đưa qua Reranker để lọc và chấm lại điểm chính xác
    reranked = rerank(query_str, results, top_k=3)
    print(f"🎯 Top {len(reranked)} kết quả tốt nhất sau khi Rerank:")

    for r in reranked:
        score = r['rerank_score']
        snippet = r['payload'].get('chunk_text', '').replace('\n', ' ')[:80]
        print(f"  [Rerank Score: {score:.3f}] {snippet}...")


def test_agent_tools():
    print("\n--- ĐANG CHẠY TEST: Agent Tools ---")

    # 1. Test SQL Filter Tool (dùng .invoke() theo chuẩn LangChain @tool)
    print("📌 Test filter_candidates_sql:")
    sql_res = filter_candidates_sql.invoke({'min_years_experience': 0})
    print(f"   Kết quả: {sql_res}\n")

    # 2. Test Semantic Search Tool
    print("📌 Test semantic_search_cv:")
    search_res = semantic_search_cv.invoke({'query': 'kinh nghiệm Python', 'top_k': 3})
    print(f"   Kết quả tìm thấy {len(search_res)} chunk phù hợp.\n")

    # 3. Test Evaluation Tool (Chấm điểm ứng viên với JD)
    # Thay chuỗi bên dưới bằng một candidate_id thật có trong cơ sở dữ liệu của bạn
    sample_candidate_id = "856f47be-c1c5-4c47-a201-57fbed1f35fd"

    print(f"📌 Test evaluate_candidate_against_jd cho ID: {sample_candidate_id}...")
    try:
        eval_res = evaluate_candidate_against_jd.invoke({
            'candidate_id': sample_candidate_id,
            'job_description': 'Cần Data Engineer biết Python, SQL, 2+ năm kinh nghiệm'
        })
        print(f"   Kết quả đánh giá:\n{eval_res}")
    except Exception as e:
        print(f"   ⚠️ Lỗi khi đánh giá (có thể do sai ID hoặc thiếu dữ liệu): {e}")


def test_ai_agent_router():
    print("\n--- ĐANG CHẠY TEST: AI Agent & Router ---")

    # # 1. Câu hỏi mang tính liệt kê chung
    # q1 = "Liệt kê các ứng viên có trong hệ thống"
    # print(f"🤖 Câu hỏi 1: \"{q1}\"")
    # ans1 = ask(q1)
    # print(f"💬 Trả lời:\n{ans1}\n" + "-"*40)

    # 2. Câu hỏi có tiêu chí cụ thể -> Kỳ vọng gọi SQL Tool
    q2 = "Ứng viên nào có trên 1 năm kinh nghiệm?"
    print(f"🤖 Câu hỏi 2: \"{q2}\"")
    ans2 = ask(q2)
    print(f"💬 Trả lời:\n{ans2}\n" + "-"*40)

    # # 3. Câu hỏi mở, tìm kiếm ngữ nghĩa -> Kỳ vọng gọi Semantic Search Tool
    # q3 = "Ai phù hợp với vị trí Data Engineer?"
    # print(f"🤖 Câu hỏi 3: \"{q3}\"")
    # ans3 = ask(q3)
    # print(f"💬 Trả lời:\n{ans3}")


def test_query_interface():
    print("\n--- ĐANG CHẠY TEST: Query Interface (Backend Contract) ---")

    # 1. Test hàm query_candidates (Luồng C - Q&A qua Agent)
    print("📌 Test query_candidates:")
    q_text = "Có bao nhiêu ứng viên trong hệ thống?"
    print(f"   Câu hỏi: \"{q_text}\"")
    res_q = query_candidates(q_text)
    print(f"   Kết quả trả về cho Backend: {res_q}\n")

    # 2. Test hàm evaluate_candidate_for_job (Luồng D - Đánh giá ứng viên theo JD)
    # Thay bằng candidate_id thật có trong DB của bạn
    sample_candidate_id = "856f47be-c1c5-4c47-a201-57fbed1f35fd"
    sample_jd = "Cần tuyển Java Backend Developer có kinh nghiệm Spring Boot, SQL Server."

    print(f"📌 Test evaluate_candidate_for_job cho ID: {sample_candidate_id}...")
    res_eval = evaluate_candidate_for_job(sample_candidate_id, sample_jd)
    print(f"   Kết quả đánh giá trả về cho Backend:\n{res_eval}")


if __name__ == "__main__":
    # test_sql_retrieval()
    # test_qdrant_fetch_chunks()
    # test_bm25_search()
    # test_hybrid_search()
    # test_hybrid_and_rerank()
    # test_agent_tools()
    # test_ai_agent_router()
    test_query_interface()

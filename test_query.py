"""
Test luồng c + d (retrieval & agent) từng bước
yêu cầu trước khi chạy: đã có ít nhất 1-2 candidate(đã run test_pipeline trước đó)
qdrant có chunk...
"""

from src.retrieval.bm25_index import build_and_store_index
import sys
sys.path.insert(0, ".")


def step(title: str):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main():

    # b1: build bm25 index (thường do celery beat làm, còn đây run tay để test)
    step("Step 1: Build bm25 index từ qdrant")

    count = build_and_store_index()
    print(f"Đã index {count} chunk vào bm25")
    if count == 0:
        print("!! Không có chunk nào - chạy test pipeline trước để có data")
        sys.exit(1)
    input("\n-> Enter để tiếp tục...")

    # b2: Test SQL filter tool
    step("Step 2: SQL Query Tool")
    from src.retrieval.sql_query_tool import search_candidates_sql

    results = search_candidates_sql(min_years_experience=0)  # lấy tất cả
    print(f"Tìm thấy {len(results)} candidate:")
    for r in results:
        print(f"  - {r['full_name']} ({r['total_years_experience']} năm KN)")
    input("\n-> Enter để tiếp tục...")

    # b3: Test Hybrid Search
    step("Step 3: Hybrid Search (BM25 + Vector)")
    from src.retrieval.hybrid_retriever import hybrid_search

    query = input("Nhập câu hỏi test (vd 'kinh nghiệm Python'): ").strip() or "kinh nghiệm lập trình"
    hybrid_results = hybrid_search(query, top_k=5)
    print(f"\n{len(hybrid_results)} kết quả:")
    for r in hybrid_results:
        print(f"  [{r['combined_score']:.3f}] {r['payload'].get('chunk_text', '')[:100]}")
    if not hybrid_results:
        print("!! Không có kết quả — kiểm tra lại query hoặc data.")
        sys.exit(1)
    input("\n-> Enter để tiếp tục sang rerank...")

    # b4: Test Rerank
    step("Step 4: Rerank")
    from src.retrieval.reranker import rerank

    reranked = rerank(query, hybrid_results, top_k=3)
    print(f"\nTop {len(reranked)} sau rerank:")
    for r in reranked:
        print(f"  [{r['rerank_score']:.3f}] {r['payload'].get('chunk_text', '')[:100]}")
    input("\n-> Enter để tiếp tục sang Agent...")

    # b5: Test Agent
    step("Step 5: Agent (Gemini tool-calling) ")
    from src.agent.router import ask
    print("Nhập câu hỏi cho agent. Gõ 'quit' or 'exit' để dừng.\n")
    while True:
        question = input("Câu hỏi (Enter để dùng câu hỏi mẫu): ").strip()
        if question.lower() in ("quit", "exit", "q"):
            print("Đã dừng vòng lặp Agent.")
            break

        if not question:
            question = "Liệt kê các ứng viên có trong hệ thống"

        print(f"\nCâu hỏi: {question}")
        answer = ask(question)

        print("\nAgent trả lời:")
        if isinstance(answer, list):
            for block in answer:
                if isinstance(block, dict) and block.get("type") == "text":
                    print(block["text"])
                else:
                    print(block)
        else:
            print(answer)

        print("\n" + "-" * 60 + "\n")

    step("HOÀN THÀNH — Giai đoạn 3 chạy thông suốt")


if __name__ == "__main__":
    main()

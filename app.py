from src. retrieval.sql_query_tool import list_recent_candidates, search_candidates_sql
from src.interfaces.query_interface import evaluate_candidate_for_job, query_candidates
import sys
import uuid

import streamlit as st

sys.path.insert(0, ".")

st.set_page_config(page_title="CV RAG - Demo tra cứu ứng viên", layout="wide")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("CV RAG - Demo tra cứu & đánh giá ứng viên")

tab_chat, tab_eval, tab_list = st.tabs(["💬 Hỏi đáp", "📋 Đánh giá theo JD", "🗂️ Danh sách ứng viên"])


def extract_answer_text(answer):
    """Lấy text sạch từ response Agent, bỏ qua phần extras/signature."""
    if isinstance(answer, list):
        text_parts = [
            block["text"] for block in answer
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n\n".join(text_parts)
    return str(answer)


# tab1 - chat hỏi đáp, có lưu lich sử qua session của trình duyệt
with tab_chat:
    st.caption(
        "Hỏi tự nhiên bằng tiếng Việt — ví dụ: "
        "\"Ứng viên nào biết Python?\", \"So sánh 2 ứng viên gần nhất\", "
        "\"Có bao nhiêu ứng viên trong hệ thống?\""
    )

    for role, content in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(content)

    question = st.chat_input("Nhập câu hỏi...")
    if question:
        st.session_state.chat_history.append(("user", question))
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Đang tra cứu..."):
                result = query_candidates(question, thread_id=st.session_state.thread_id)
            if result["error"]:
                answer = f"⚠️ Có lỗi xảy ra: {result['error']}"
            else:
                answer = extract_answer_text(result["answer"])
            st.markdown(answer)

        st.session_state.chat_history.append(("assistant", answer))

    if st.session_state.chat_history:
        if st.button("🗑️ Xóa lịch sử hội thoại"):
            st.session_state.chat_history = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()

# tab2 - Đánh giá 1 ứng viên theo jd

with tab_eval:
    st.caption("Nhập candidate_id (xem ở tab Danh sách ứng viên) và JD để chấm điểm")

    col1, col2 = st.columns([1, 2])
    with col1:
        candidate_id = st.text_input("Candidate ID")
    with col2:
        jd_text = st.text_area("Job Description", height=150)

    if st.button("Đánh giá", type="primary"):
        if not candidate_id or not jd_text:
            st.warning("Cần nhập đủ Candidate ID và JD.")
        else:
            with st.spinner("Đang chấm điểm..."):
                result = evaluate_candidate_for_job(candidate_id, jd_text)

            if "error" in result:
                st.error(result["error"])
            else:
                st.metric("Điểm tổng", f"{result['overall_score']:.1f} / 5")

                st.subheader("Chi tiết theo tiêu chí")
                for c in result["criteria"]:
                    st.markdown(f"**{c['criterion']}**: {c['score']}/5 — {c['justification']}")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.subheader("✅ Điểm mạnh")
                    for s in result["strengths"]:
                        st.markdown(f"- {s}")
                with col_b:
                    st.subheader("⚠️ Cần lưu ý")
                    for c in result["concerns"]:
                        st.markdown(f"- {c}")

                st.subheader("Tóm tắt")
                st.info(result['summary'])


# tab3 - Danh sách ứng viên
with tab_list:
    st.caption("Xem nhanh danh sách ứng viên, lọc theo kỹ năng nếu cần")

    skill_filter = st.text_input("Lọc theo kỹ năng (để trống = xem tất cả gần đây)")

    if skill_filter:
        candidates = search_candidates_sql(skills=[skill_filter], limit=50)
    else:
        candidates = list_recent_candidates(limit=20)

    if not candidates:
        st.info("Không có ứng viên nào khớp.")
    else:
        st.dataframe(candidates, use_container_width=True)
        st.caption(f"Hiển thị {len(candidates)} ứng viên. Copy candidate_id để dùng ở tab Đánh giá")

from src.chat.conversation_store import create_conversation, delete_conversation, list_conversations
from src.chat.feedback_store import save_feedback
from src.agent.router import get_conversation_messages, has_pending_confirmation
from src.ingestion.extraction.llm_extractor import ocr_extract_text_from_images
from src.ingestion.parsers.pdf_parser import extract_text_from_pdf, rasterize_pages
from src.interfaces.query_interface import (
    evaluate_candidate_for_job,
    parse_jd,
    query_candidates,
    rank_top_candidates,
    resume_confirmation,
)
from src.interfaces.notification_interface import dispatch_bulk_emails, get_batch_status
from src.interfaces.interview_interface import (
    delete_questions_for_candidate,
    generate_questions_for_candidate,
    get_questions_for_candidate,
)
from src.notification.bulk_email_drafter import draft_bulk_emails
from src.retrieval.sql_query_tool import list_recent_candidates, search_candidates_sql
from src.notification.email_drafter import draft_interview_email
from src.notification.email_sender import has_already_sent, send_interview_invitation
from src.storage.minio_client import MinioStorage

import sys

import streamlit as st

sys.path.insert(0, ".")


st.set_page_config(page_title="CV RAG — Demo tra cứu ứng viên", layout="wide")

if "active_thread_id" not in st.session_state:
    st.session_state.active_thread_id = create_conversation()

st.title("CV RAG — Demo tra cứu & đánh giá ứng viên")


# sidebar
with st.sidebar:
    st.header("💬 Hội thoại")

    if st.button("➕ Cuộc trò chuyện mới", use_container_width=True):
        st.session_state.active_thread_id = create_conversation()
        st.rerun()

    st.divider()

    conversations = list_conversations()
    for conv in conversations:
        is_active = conv["thread_id"] == st.session_state.active_thread_id
        col_title, col_delete = st.columns([5, 1])
        with col_title:
            if st.button(
                ("🟢 " if is_active else "") + conv["title"],
                key=f"conv_{conv['thread_id']}",
                use_container_width=True,
            ):
                st.session_state.active_thread_id = conv["thread_id"]
                st.rerun()
        with col_delete:
            if st.button("🗑️", key=f"del_{conv['thread_id']}"):
                delete_conversation(conv["thread_id"])
                if is_active:
                    st.session_state.active_thread_id = create_conversation()
                st.rerun()

    if not conversations:
        st.caption("Chưa có cuộc trò chuyện nào.")

tab_chat, tab_eval, tab_topk, tab_email, tab_interview, tab_list = st.tabs(
    [
        "💬 Hỏi đáp",
        "📋 Đánh giá theo JD",
        "🎯 Top-K theo JD",
        "✉️ Gửi thư mời",
        "❓ Câu hỏi Phỏng vấn",
        "🗂️ Danh sách ứng viên",
    ]
)


def extract_answer_text(answer):
    if isinstance(answer, list):
        text_parts = [
            block["text"] for block in answer
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n\n".join(text_parts)
    return str(answer)


def get_jd_text_from_input(key_prefix: str) -> str | None:
    """Widget dùng chung cho tab Đánh giá và tab Top-K: cho phép gõ tay
    HOẶC upload PDF. Nếu upload PDF, tự extract text — thử text layer
    trước, nếu quá ngắn (nghi ngờ scan) thì fallback OCR qua Gemini vision,
    dùng lại đúng logic đã áp dụng cho CV ở pipeline.py.
    """
    input_mode = st.radio(
        "Nguồn JD", ["Gõ tay", "Upload file PDF"], key=f"{key_prefix}_mode", horizontal=True
    )

    if input_mode == "Gõ tay":
        return st.text_area("Job Description", height=150, key=f"{key_prefix}_text")

    uploaded_file = st.file_uploader("Chọn file JD (.pdf)", type=["pdf"], key=f"{key_prefix}_file")
    if uploaded_file is None:
        return None

    file_bytes = uploaded_file.read()
    with st.spinner("Đang đọc file PDF..."):
        text = extract_text_from_pdf(file_bytes)
        if len(text) < 100:  # ngưỡng đơn giản, không cần chính xác như CV_MIN_TEXT_LENGTH
            st.info("File có vẻ là ảnh scan, đang thử đọc bằng OCR...")
            images = rasterize_pages(file_bytes)
            text = ocr_extract_text_from_images(images)

    with st.expander("Xem text đã trích xuất từ PDF"):
        st.text(text[:2000] + ("..." if len(text) > 2000 else ""))

    return text


def extract_text_from_uploaded_file(uploaded_file) -> str | None:
    """Dùng cho file đính kèm trực tiếp tại ô chat (mục 1.1 spec) — tái sử
    dụng đúng module pdf_parser/OCR đã có, KHÔNG viết logic extract riêng.

    Hỗ trợ: PDF (text layer hoặc scan, tự OCR fallback), ảnh (PNG/JPG, OCR
    thẳng qua Gemini vision). CHƯA hỗ trợ DOCX — python-docx chưa có sẵn
    trong project (chỉ có PDF parser), báo rõ cho HR biết thay vì âm thầm
    bỏ qua.
    """
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    if filename.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
        if len(text) < 100:
            images = rasterize_pages(file_bytes)
            text = ocr_extract_text_from_images(images)
        return text

    if filename.endswith((".png", ".jpg", ".jpeg")):
        return ocr_extract_text_from_images([file_bytes])

    if filename.endswith(".docx"):
        st.warning(f"'{uploaded_file.name}': chưa hỗ trợ đọc file DOCX, bỏ qua file này.")
        return None

    st.warning(f"'{uploaded_file.name}': định dạng không được hỗ trợ, bỏ qua.")
    return None


def render_confirmation_ui(active_thread_id: str, payload: dict) -> None:
    """UI cho Double Opt-in (mục 1.3) — Agent đang DỪNG LẠI (chặn kỹ thuật
    qua interrupt(), xem jd_matching_tool.py + router.py), chờ HR xác nhận
    tiêu chí JD trước khi chạy bước Top-K tốn kém.

    Dùng has_pending_confirmation() (không phải chỉ session_state) để biết
    có cần hiện form này không — nhờ vậy kể cả HR đổi tab/reload trang giữa
    chừng, form xác nhận vẫn hiện lại đúng, vì trạng thái nằm trong
    checkpointer bền (SqliteSaver), không phải bộ nhớ tạm của trình duyệt.
    """
    st.info("🔍 Agent đã trích xuất tiêu chí từ JD — xác nhận trước khi tìm kiếm (tốn nhiều lời gọi AI):")

    edited_title = st.text_input("Vị trí", value=payload.get(
        "position_title", ""), key=f"confirm_title_{active_thread_id}")
    edited_skills_str = st.text_input(
        "Kỹ năng bắt buộc (phân cách bằng dấu phẩy)",
        value=", ".join(payload.get("required_skills", [])),
        key=f"confirm_skills_{active_thread_id}",
    )
    edited_years = st.number_input(
        "Số năm kinh nghiệm tối thiểu",
        value=float(payload.get("min_years_experience") or 0),
        key=f"confirm_years_{active_thread_id}",
    )
    edited_top_k = st.slider(
        "Số lượng ứng viên (K)", 1, 10, value=payload.get("top_k", 5), key=f"confirm_topk_{active_thread_id}"
    )

    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("✅ Đồng ý, tìm kiếm ngay", type="primary", key=f"confirm_btn_{active_thread_id}"):
            edited_criteria = {
                "position_title": edited_title,
                "required_skills": [s.strip() for s in edited_skills_str.split(",") if s.strip()],
                "min_years_experience": edited_years or None,
                "top_k": edited_top_k,
            }
            with st.spinner("Đang xếp hạng và chấm điểm..."):
                resume_confirmation(active_thread_id, confirmed=True, edited_criteria=edited_criteria)
            st.rerun()
    with col_cancel:
        if st.button("❌ Huỷ", key=f"cancel_btn_{active_thread_id}"):
            resume_confirmation(active_thread_id, confirmed=False)
            st.rerun()


# TAB 1 — Chat hỏi đáp
with tab_chat:
    st.caption(
        "Hỏi tự nhiên bằng tiếng Việt, có thể đính kèm PDF/ảnh ngay tại ô nhập — ví dụ: "
        "\"Ứng viên nào biết Python?\", \"Tìm top ứng viên cho JD đính kèm này\""
    )

    active_thread_id = st.session_state.active_thread_id

    history = get_conversation_messages(active_thread_id)
    for i, msg in enumerate(history):
        with st.chat_message(msg["role"]):
            st.markdown(extract_answer_text(msg["content"]))

            if msg["role"] == "assistant":
                paired_question = history[i - 1]["content"] if i > 0 else ""
                col_up, col_down, _ = st.columns([1, 1, 10])
                with col_up:
                    if st.button("👍", key=f"up_{active_thread_id}_{i}"):
                        save_feedback(active_thread_id, paired_question, msg["content"], "up")
                        st.toast("Cảm ơn phản hồi!")
                with col_down:
                    if st.button("👎", key=f"down_{active_thread_id}_{i}"):
                        save_feedback(active_thread_id, paired_question, msg["content"], "down")
                        st.toast("Đã ghi nhận, cảm ơn phản hồi!")

    pending_payload = has_pending_confirmation(active_thread_id)
    if pending_payload:
        render_confirmation_ui(active_thread_id, pending_payload)
    else:
        chat_value = st.chat_input(
            "Nhập câu hỏi... (có thể đính kèm PDF/ảnh)",
            accept_file=True,
            file_type=["pdf", "png", "jpg", "jpeg"],
        )

        if chat_value:
            question_text = chat_value.text or ""
            attached_texts = []
            for f in chat_value.files:
                with st.spinner(f"Đang đọc {f.name}..."):
                    extracted = extract_text_from_uploaded_file(f)
                if extracted:
                    attached_texts.append(f"--- Nội dung file '{f.name}' ---\n{extracted[:5000]}")

            full_question = question_text
            if attached_texts:
                full_question = (question_text or "Hãy phân tích tài liệu đính kèm") + \
                    "\n\n" + "\n\n".join(attached_texts)

            display_question = question_text or f"(đính kèm {len(chat_value.files)} file)"

            with st.chat_message("user"):
                st.markdown(display_question)
                for f in chat_value.files:
                    st.caption(f"📎 {f.name}")

            with st.chat_message("assistant"):
                with st.spinner("Đang xử lý..."):
                    result = query_candidates(full_question, thread_id=active_thread_id)

                if result["type"] == "error":
                    st.markdown(f"⚠️ Có lỗi xảy ra: {result['error']}")
                elif result["type"] == "confirmation_required":
                    st.markdown("Đã trích xuất tiêu chí từ tài liệu — xem form xác nhận bên dưới.")
                else:
                    st.markdown(extract_answer_text(result["content"]))

            st.rerun()

# TAB 2 — Đánh giá 1 ứng viên theo JD
with tab_eval:
    st.caption("Nhập candidate_id (xem ở tab Danh sách ứng viên) và JD để chấm điểm.")

    candidate_id = st.text_input("Candidate ID", key="eval_candidate_id")
    jd_text = get_jd_text_from_input("eval")

    if st.button("Đánh giá", type="primary", key="eval_btn"):
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
                st.info(result["summary"])


# TAB 3 — Top-K ứng viên phù hợp nhất với 1 JD
with tab_topk:
    st.caption(
        "Đưa vào 1 JD, hệ thống tự tìm và chấm điểm những ứng viên phù hợp nhất "
        "trong toàn bộ hệ thống (lọc trước theo tiêu chí cứng, xếp hạng ngữ nghĩa, "
        "rồi chấm điểm chi tiết cho top K — có thể mất khoảng chục giây."
    )

    jd_text_topk = get_jd_text_from_input("topk")
    top_k = st.slider("Số lượng ứng viên muốn xem (K)", min_value=1, max_value=10, value=5)

    if st.button("Tìm ứng viên phù hợp", type="primary", key="topk_btn"):
        if not jd_text_topk:
            st.warning("Cần nhập hoặc upload JD trước.")
        else:
            with st.spinner("Đang trích xuất JD..."):
                jd_parsed = parse_jd(jd_text_topk)

            if "error" in jd_parsed:
                st.error(jd_parsed["error"])
            else:
                st.subheader("JD đã trích xuất")
                st.json(
                    {
                        "position_title": jd_parsed["position_title"],
                        "required_skills": jd_parsed["required_skills"],
                        "min_years_experience": jd_parsed["min_years_experience"],
                        "preferred_education": jd_parsed["preferred_education"],
                    }
                )

                with st.spinner(f"Đang xếp hạng và chấm điểm top {top_k} ứng viên..."):
                    ranking = rank_top_candidates(jd_parsed, top_k=top_k)

                if ranking["error"]:
                    st.error(ranking["error"])
                elif not ranking["results"]:
                    st.info("Không tìm thấy ứng viên nào phù hợp với JD này.")
                else:
                    for i, r in enumerate(ranking["results"], 1):
                        with st.expander(
                            f"#{i} — {r['candidate_id']} — {r['overall_score']:.1f}/5", expanded=(i <= 3)
                        ):
                            for c in r["criteria"]:
                                st.markdown(f"**{c['criterion']}**: {c['score']}/5 — {c['justification']}")
                            st.markdown(f"**Tóm tắt:** {r['summary']}")


# TAB 4 — Gửi thư mời phỏng vấn
with tab_email:
    sub_single, sub_bulk = st.tabs(["Gửi đơn lẻ", "📊 Gửi hàng loạt (Data Grid)"])

    with sub_single:
        st.caption(
            "Soạn nội dung tự động, bạn xem/sửa lại trước khi gửi thật. "
            "Email được gửi từ chính hộp mail HR đang dùng nhận CV."
        )

        email_candidate_id = st.text_input("Candidate ID", key="email_candidate_id")
        email_position = st.text_input("Vị trí phỏng vấn", key="email_position")
        email_interview_details = st.text_area(
            "Chi tiết phỏng vấn (thời gian, địa điểm, hình thức...)",
            key="email_interview_details",
            help="Để trống nếu chưa chốt — hệ thống sẽ không tự bịa thông tin cụ thể.",
        )

        if st.button("📝 Soạn nháp", key="draft_email_btn"):
            if not email_candidate_id or not email_position:
                st.warning("Cần nhập Candidate ID và Vị trí phỏng vấn.")
            else:
                with st.spinner("Đang soạn..."):
                    draft = draft_interview_email(email_candidate_id, email_position, email_interview_details)
                if draft is None:
                    st.error("Không tìm thấy candidate_id này hoặc bạn không có quyền xem.")
                else:
                    st.session_state.draft_subject = draft.subject
                    st.session_state.draft_body = draft.body

        if "draft_subject" in st.session_state:
            st.divider()

            if has_already_sent(email_candidate_id):
                st.warning("⚠️ Candidate này ĐÃ từng được gửi email mời trước đó. Kiểm tra kỹ trước khi gửi lại.")

            subject_input = st.text_input("Subject", value=st.session_state.draft_subject, key="final_subject")
            body_input = st.text_area("Nội dung", value=st.session_state.draft_body, height=250, key="final_body")

            confirm = st.checkbox("Tôi đã kiểm tra kỹ nội dung và xác nhận gửi email này")

            if st.button("📧 Gửi email", type="primary", disabled=not confirm):
                with st.spinner("Đang gửi..."):
                    result = send_interview_invitation(email_candidate_id, subject_input, body_input)
                if result["success"]:
                    st.success(f"Đã gửi thành công! (message_id: {result['message_id']})")
                    del st.session_state.draft_subject
                    del st.session_state.draft_body
                else:
                    st.error(f"Gửi thất bại: {result['error']}")

    with sub_bulk:
        st.caption(
            "Soạn hàng loạt cho nhiều ứng viên, xem/sửa trực tiếp trên bảng, "
            "chọn ai muốn gửi rồi gửi tất cả cùng lúc — chạy ngầm qua Celery, "
            "không làm treo giao diện dù batch lớn."
        )

        bulk_candidate_ids_str = st.text_area(
            "Danh sách Candidate ID (mỗi dòng 1 ID, hoặc phân cách bằng dấu phẩy)",
            key="bulk_candidate_ids",
        )
        bulk_position = st.text_input("Vị trí phỏng vấn", key="bulk_position")
        bulk_interview_details = st.text_area("Chi tiết phỏng vấn", key="bulk_interview_details")

        if st.button("📝 Soạn nháp hàng loạt", key="bulk_draft_btn"):
            ids = [
                x.strip()
                for x in bulk_candidate_ids_str.replace(",", "\n").splitlines()
                if x.strip()
            ]
            if not ids or not bulk_position:
                st.warning("Cần nhập ít nhất 1 Candidate ID và Vị trí phỏng vấn.")
            else:
                with st.spinner(f"Đang soạn {len(ids)} email..."):
                    drafts = draft_bulk_emails(ids, bulk_position, bulk_interview_details)
                st.session_state.bulk_drafts = drafts

        if "bulk_drafts" in st.session_state:
            st.divider()

            failed = [r for r in st.session_state.bulk_drafts if r["error"]]
            if failed:
                st.warning(
                    f"⚠️ {len(failed)} candidate không soạn được (không tồn tại/ngoài quyền xem): "
                    + ", ".join(r["candidate_id"] for r in failed)
                )

            grid_rows = [
                {
                    "Gửi": True,
                    "candidate_id": r["candidate_id"],
                    "Tên": r["full_name"],
                    "Subject": r["subject"],
                    "Nội dung": r["body"],
                }
                for r in st.session_state.bulk_drafts
                if r["error"] is None
            ]

            if grid_rows:
                edited_grid = st.data_editor(
                    grid_rows,
                    key="bulk_email_grid",
                    use_container_width=True,
                    disabled=["candidate_id", "Tên"],  # chỉ cho sửa Subject/Nội dung, không sửa ID
                    column_config={
                        "Nội dung": st.column_config.TextColumn(width="large"),
                    },
                    hide_index=True,
                )

                selected_rows = [row for row in edited_grid if row["Gửi"]]
                st.caption(f"Đã chọn {len(selected_rows)}/{len(edited_grid)} email để gửi.")

                already_sent_ids = [r["candidate_id"] for r in selected_rows if has_already_sent(r["candidate_id"])]
                if already_sent_ids:
                    st.warning(f"⚠️ Đã từng gửi trước đó cho: {', '.join(already_sent_ids)}")

                confirm_bulk = st.checkbox(
                    f"Tôi xác nhận gửi {len(selected_rows)} email đã chọn", key="confirm_bulk_send"
                )

                if st.button("📧 Gửi tất cả đã chọn", type="primary", disabled=not confirm_bulk or not selected_rows):
                    batch = [
                        {"candidate_id": r["candidate_id"], "subject": r["Subject"], "body": r["Nội dung"]}
                        for r in selected_rows
                    ]
                    dispatch_result = dispatch_bulk_emails(batch)
                    st.session_state.last_batch_id = dispatch_result["batch_id"]
                    st.success(
                        f"Đã đẩy {dispatch_result['count']} email vào hàng đợi xử lý ngầm "
                        f"(batch_id: {dispatch_result['batch_id']}). Xem tiến độ bên dưới."
                    )
                    del st.session_state.bulk_drafts

        if "last_batch_id" in st.session_state:
            st.divider()
            st.subheader("Tiến độ batch gần nhất")
            if st.button("🔄 Kiểm tra tiến độ", key="check_batch_btn"):
                status = get_batch_status(st.session_state.last_batch_id)
                st.write(
                    f"Đã xử lý: {status['total_logged']} — Thành công: {status['success']} — Thất bại: {status['failed']}")
                if status["details"]:
                    st.dataframe(status["details"], use_container_width=True)


# TAB 5 - Câu hỏi phỏng vấn
with tab_interview:
    st.caption(
        "Sinh câu hỏi phỏng vấn dựa CHỈ trên nội dung CV thật — mỗi câu kèm trích dẫn "
        "làm bằng chứng, đã tự động kiểm tra không phải AI bịa đặt."
    )

    interview_candidate_id = st.text_input("Candidate ID", key="interview_candidate_id")
    interview_max_questions = st.slider("Số lượng câu hỏi tối đa", 3, 15, value=8, key="interview_max_q")

    col_gen, col_del = st.columns(2)
    with col_gen:
        generate_clicked = st.button("🎲 Sinh câu hỏi mới (thay thế câu cũ)", type="primary", key="gen_questions_btn")
    with col_del:
        delete_clicked = st.button("🗑️ Xoá toàn bộ câu hỏi của ứng viên này", key="del_questions_btn")

    if generate_clicked:
        if not interview_candidate_id:
            st.warning("Cần nhập Candidate ID.")
        else:
            with st.spinner("Đang đọc CV và sinh câu hỏi..."):
                result = generate_questions_for_candidate(interview_candidate_id, max_questions=interview_max_questions)
            if result["error"]:
                st.error(result["error"])
            elif not result["questions"]:
                st.info("CV chưa đủ thông tin cụ thể để sinh câu hỏi đáng tin cậy.")
            else:
                st.success(f"Đã sinh {len(result['questions'])} câu hỏi.")

    if delete_clicked:
        if not interview_candidate_id:
            st.warning("Cần nhập Candidate ID.")
        else:
            result = delete_questions_for_candidate(interview_candidate_id)
            st.success(f"Đã xoá {result['deleted']} câu hỏi.")

    if interview_candidate_id:
        existing = get_questions_for_candidate(interview_candidate_id)
        questions = existing["questions"]

        if questions:
            st.divider()
            st.subheader(f"Câu hỏi hiện có ({len(questions)})")

            category_colors = {"Technical": "🔵", "System Design": "🟣", "Soft Skill": "🟢"}
            for q in questions:
                icon = category_colors.get(q["category"], "⚪")
                with st.expander(f"{icon} [{q['category']}] {q['question']}"):
                    st.markdown(f"**Mục CV liên quan:** {q['cv_section']}")
                    st.markdown(f"**Trích dẫn bằng chứng:** _{q['evidence_quote']}_")


# TAB 6 — Danh sách ứng viên
with tab_list:
    st.caption("Xem nhanh danh sách ứng viên, lọc theo kỹ năng nếu cần.")

    skill_filter = st.text_input("Lọc theo kỹ năng (để trống = xem tất cả gần đây)")

    if skill_filter:
        candidates = search_candidates_sql(skills=[skill_filter], limit=50)
    else:
        candidates = list_recent_candidates(limit=20)

    if not candidates:
        st.info("Không có ứng viên nào khớp.")
    else:
        st.dataframe(candidates, use_container_width=True)
        st.caption(f"Hiển thị {len(candidates)} ứng viên. Copy candidate_id để dùng ở các tab khác.")

        with st.expander("🖼️ Xem ảnh chân dung (nếu có)"):
            photo_candidate_id = st.selectbox(
                "Chọn candidate_id",
                options=[c["candidate_id"] for c in candidates],
                format_func=lambda cid: next(
                    c["full_name"] for c in candidates if c["candidate_id"] == cid
                ),
            )
            if st.button("Tải ảnh", key="load_photo_btn"):
                # Cần query full profile để lấy photo_object_key — danh sách
                # rút gọn ở trên không có field này.
                from src.db.models import Candidate
                from src.db.session import SessionLocal

                with SessionLocal() as session:
                    cand = session.get(Candidate, photo_candidate_id)
                    if cand and cand.photo_object_key:
                        try:
                            photo_bytes = MinioStorage().download_bytes(cand.photo_object_key)
                            st.image(photo_bytes, width=200)
                        except Exception as e:
                            st.warning(f"Không tải được ảnh: {e}")
                    else:
                        st.info("Ứng viên này không có ảnh chân dung được tách ra.")

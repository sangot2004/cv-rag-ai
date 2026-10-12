import streamlit as st
from src.auth.service import AccessDenied, login, logout, auth_scope, create_user, set_user_active
from src.db.models import AppUser, Department
from src.db.session import SessionLocal


def clear_session():
    st.session_state.clear()


def login_screen():
    st.title("Đăng nhập CV RAG")
    with st.form("login", clear_on_submit=True):
        username = st.text_input("Tài khoản")
        password = st.text_input("Mật khẩu", type="password")
        submitted = st.form_submit_button("Đăng nhập")
    if submitted:
        try:
            token = login(username, password)
            clear_session()
            st.session_state.auth_token = token
            st.rerun()
        except AccessDenied as exc:
            st.error(str(exc))
    st.stop()


def render_authenticated(render_app):
    token = st.session_state.get("auth_token")
    if not token:
        login_screen()
    try:
        with auth_scope(token) as user:
            with st.sidebar:
                st.caption(f"{user.username} · {user.role}")
                if st.button("Đăng xuất"):
                    logout(token)
                    clear_session()
                    st.rerun()
            render_app(user)
    except AccessDenied as exc:
        logout(token)
        clear_session()
        st.error(str(exc))
        if st.button("Về trang đăng nhập"):
            st.rerun()
        st.stop()


def render_user_admin():
    from src.auth.service import require_admin
    current = require_admin()
    with st.expander("Quản lý tài khoản"):
        with SessionLocal() as db:
            departments = {d.department_id: d.department_name for d in db.query(Department).all()}
            users = [{"user_id": u.user_id, "username": u.username, "role": u.role,
                      "active": u.is_active, "department_id": u.department_id}
                     for u in db.query(AppUser).all()]
        st.dataframe(users)
        with st.form("create_account", clear_on_submit=True):
            username = st.text_input("Tên tài khoản mới")
            password = st.text_input("Mật khẩu mới (ít nhất 12 ký tự)", type="password")
            role = st.selectbox("Quyền", ["tester", "admin"])
            department = st.selectbox("Phòng ban", [None, *departments],
                                      format_func=lambda k: departments.get(k, "Chọn phòng ban"))
            submitted = st.form_submit_button("Tạo tài khoản")
        if submitted:
            try:
                create_user(username, password, role, department)
                st.success("Đã tạo tài khoản.")
            except ValueError as exc:
                st.error(str(exc))
        targets = {u["user_id"]: u["username"] for u in users if u["user_id"] != current.user_id}
        if targets:
            selected = st.selectbox("Tài khoản cần khóa/mở", list(targets), format_func=targets.get)
            if st.button("Đổi trạng thái tài khoản"):
                selected_user = next(u for u in users if u["user_id"] == selected)
                set_user_active(selected, not selected_user["active"])
                st.rerun()

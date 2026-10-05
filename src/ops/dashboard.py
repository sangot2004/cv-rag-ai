import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st
from sqlalchemy import select

from src.db.models import LLMUsageLog, IngestionJob
from src.db.session import SessionLocal


def render_ops_dashboard():
    st.subheader("📊 System Ops")
    st.caption("Chi phí ước tính USD theo cấu hình giá; không phải hóa đơn. Thời gian UTC. Dashboard demo chưa có đăng nhập admin.")
    days = st.selectbox("Khoảng thời gian", [1, 7, 30], format_func=lambda n: f"{n} ngày", key="ops_days")
    if st.button("Làm mới", key="ops_refresh"):
        st.rerun()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with SessionLocal() as session:
            logs = session.execute(select(LLMUsageLog).where(LLMUsageLog.created_at >= since)).scalars().all()
            data = [{c.name: getattr(row, c.name) for c in LLMUsageLog.__table__.columns} for row in logs]
            indexed = {row.job_id for row in session.execute(
                select(IngestionJob).where(IngestionJob.status == "indexed")).scalars()}
            dlq_count = len(session.execute(select(IngestionJob.job_id).where(IngestionJob.status == "dlq")).all())
    except Exception:
        st.error("Không đọc được dữ liệu Ops. Kiểm tra MySQL và chạy alembic upgrade head.")
        return
    if not data:
        st.info("Chưa có usage trong khoảng đã chọn. Thực hiện xử lý CV hoặc hỏi agent để tạo dữ liệu.")
        return
    df = pd.DataFrame(data)
    modules = ["Tất cả"] + sorted(df.module_name.unique())
    module = st.selectbox("Module", modules, key="ops_module")
    if module != "Tất cả":
        df = df[df.module_name == module]
    model = st.selectbox("Model", ["Tất cả"] + sorted(df.model_name.unique()), key="ops_model")
    if model != "Tất cả":
        df = df[df.model_name == model]
    if df.empty:
        st.info("Không có dữ liệu khớp bộ lọc.")
        return
    cols = st.columns(4)
    cols[0].metric("Lần gọi AI", len(df))
    cols[1].metric("Token đã ghi nhận", int(df.input_tokens.fillna(0).sum()+df.output_tokens.fillna(0).sum()))
    priced = df.estimated_cost_usd.notna()
    cols[2].metric("Chi phí đã định giá (USD)",
                   f"{df.estimated_cost_usd.sum():.6f}" if priced.any() else "Chưa cấu hình")
    cols[3].metric("Tỷ lệ lỗi", f"{100*(df.status == 'error').mean():.1f}%")
    st.caption(f"{int((~priced).sum())} lần gọi chưa xác định chi phí; {int(df.input_tokens.isna().sum())} lần thiếu input usage. Không coi thiếu dữ liệu là 0.")
    st.metric("Calls ở lần failover tiếp theo", int((df.attempt > 1).sum()))
    cols = st.columns(3)
    cols[0].metric("Độ trễ median (ms)", f"{df.latency_ms.median():.0f}")
    cols[1].metric("Độ trễ p95 (ms)", f"{df.latency_ms.quantile(.95):.0f}")
    cols[2].metric("Job DLQ toàn hệ thống", dlq_count)
    # Summarize all observed calls of successful jobs within selected time/filter.
    cv = df[df.job_id.isin(indexed)]
    if not cv.empty:
        costs = cv.groupby("job_id").estimated_cost_usd.agg(lambda x: x.sum() if x.notna().all() else float('nan'))
        st.metric("Chi phí trung bình/CV có đủ giá (USD)",
                  f"{costs.mean():.6f}" if costs.notna().any() else "Chưa đủ dữ liệu")
        st.caption("Tính trên calls trong khoảng thời gian/bộ lọc hiện tại của job indexed, gồm calls lỗi đã ghi nhận; có thể thiếu calls ngoài khoảng thời gian.")
    st.write("Thống kê theo module")
    summary = df.groupby("module_name").agg(calls=("id", "count"), input_tokens=("input_tokens", "sum"), output_tokens=(
        "output_tokens", "sum"), estimated_cost_usd=("estimated_cost_usd", "sum"), median_ms=("latency_ms", "median"))
    st.dataframe(summary, use_container_width=True)
    st.bar_chart(summary[["input_tokens", "output_tokens"]])
    daily = df.assign(day=pd.to_datetime(df.created_at).dt.date).groupby("day")[["input_tokens", "output_tokens"]].sum()
    st.line_chart(daily)
    st.scatter_chart(df.dropna(subset=["input_tokens"]), x="input_tokens", y="latency_ms", color="module_name")
    slow = float(os.getenv("OPS_LATENCY_ALERT_MS", "15000"))
    token_limit = int(os.getenv("OPS_TOKEN_ALERT", "20000"))
    alerts = df[(df.latency_ms > slow) | ((df.input_tokens.fillna(
        0)+df.output_tokens.fillna(0)) > token_limit) | (df.status == "error")]
    st.write("Cảnh báo theo quy tắc")
    if alerts.empty:
        st.success("Không có call vượt ngưỡng hoặc lỗi.")
    else:
        st.warning(f"{len(alerts)} call lỗi hoặc vượt ngưỡng {slow:.0f} ms / {token_limit} tokens")
        st.dataframe(alerts[["created_at", "module_name", "model_name", "status", "error_type",
                     "latency_ms", "input_tokens", "output_tokens", "operation_id"]], use_container_width=True)
    st.write("Usage chi tiết (500 call gần nhất)")
    st.dataframe(df.sort_values("created_at", ascending=False).head(500), use_container_width=True)

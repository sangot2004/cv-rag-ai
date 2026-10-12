import json
import streamlit as st
from sqlalchemy import select

from src.ops.optimization import active_config, propose, approve, rollback, OptimizationConfig
from src.auth.service import admin_only


@admin_only
def render_optimization():
    st.subheader("Phase 3 + 4 — Optimization")
    current = active_config()
    st.json(current)
    st.caption("Proposals activate only after a passing experiment and admin approval.")
    if st.button("Analyze usage and create AI proposal"):
        try:
            from src.ops.optimization import analyze_usage
            st.json(analyze_usage())
        except Exception as exc:
            st.error(str(exc))
    with st.form("ops_propose"):
        model = st.text_input("Extraction model (empty = existing default)", value=current["extraction_model"] or "")
        prompt_version = st.text_input(
            "Extraction prompt commit (LangSmith)",
            value=current["extraction_prompt_version"],
            help="Use an immutable commit hash, not latest or a movable tag.",
        )
        cache = st.checkbox("Exact extraction cache (Redis, TTL)", value=current["cache_enabled"])
        multiplier = st.number_input("Retrieval overfetch multiplier", 2, 8, current["retrieval_multiplier"])
        if st.form_submit_button("Create proposal"):
            try:
                st.success(propose({
                    "extraction_model": model.strip() or None,
                    "extraction_prompt_version": prompt_version.strip(),
                    "cache_enabled": cache,
                    "retrieval_multiplier": int(multiplier),
                }))
            except ValueError as exc:
                st.error(str(exc))
    st.caption("Run from project root: python -m scripts.run_ops_experiment PROPOSAL_ID --dataset cv-extraction-eval --username ADMIN_USERNAME. Makes real model calls; costs apply. Dataset: inputs.raw_text and outputs matching CVSchema.")
    dataset = st.text_input("Golden dataset", value="cv-extraction-eval")
    try:
        from src.db.session import SessionLocal
        with SessionLocal() as session:
            rows = session.execute(select(OptimizationConfig).order_by(
                OptimizationConfig.created_at.desc())).scalars().all()
        for row in rows:
            with st.expander(row.id + " / " + row.status):
                st.json(json.loads(row.settings_json))
                if row.status != "approved" and st.button("Run paired experiment (real AI calls)", key="experiment"+row.id):
                    from src.ops.experiments import run_experiment
                    with st.spinner("Evaluating baseline and proposal..."):
                        st.json(run_experiment(row.id, dataset))
                if row.report_json:
                    st.json(json.loads(row.report_json))
                if st.button("Approve evaluated version", key="approve"+row.id):
                    approve(row.id)
                    st.rerun()
                if row.status == "approved" and st.button("Rollback to this version", key="rollback"+row.id):
                    rollback(row.id)
                    st.rerun()
        if st.button("Rollback to defaults"):
            rollback()
            st.rerun()
    except Exception as exc:
        st.error(str(exc))

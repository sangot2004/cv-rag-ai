import logging

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from src.ops.telemetry import UsageCallback

from src.agent.tools.candidate_detail_tool import get_candidate_detail
from src.agent.tools.certificate_project_tool import (
    find_candidates_by_certificate,
    find_candidates_by_project_tech,
)
from src.agent.tools.compare_tool import compare_candidates
from src.agent.tools.draft_email_tool import draft_interview_invitation
from src.agent.tools.bulk_email_tool import draft_bulk_interview_invitations
from src.agent.tools.evaluation_tool import evaluate_candidate_against_jd
from src.agent.tools.interview_question_tool import generate_interview_questions_for_candidate
from src.agent.tools.jd_matching_tool import find_top_candidates_for_jd
from src.agent.tools.recent_candidates_tool import list_recent_cvs
from src.agent.tools.search_tool import semantic_search_cv
from src.agent.tools.sql_filter_tool import filter_candidates_sql
from src.agent.tools.stats_tool import count_candidates
from src.config.settings import get_settings
from src.llm.prompt_store import get_prompt_text


logger = logging.getLogger(__name__)
settings = get_settings()

_tools = [
    filter_candidates_sql,
    semantic_search_cv,
    evaluate_candidate_against_jd,
    get_candidate_detail,
    compare_candidates,
    count_candidates,
    find_candidates_by_certificate,
    find_candidates_by_project_tech,
    list_recent_cvs,
    find_top_candidates_for_jd,
    draft_interview_invitation,
    draft_bulk_interview_invitations,
    generate_interview_questions_for_candidate,

]


class _ReadOnlyModel:
    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, *args, **kwargs):
        raise RuntimeError("History reader cannot execute the agent")


def build_agent_executor(api_key: str | None, checkpointer=None, role="admin", *, read_only=False):
    tools = _tools if role == "admin" else [tool for tool in _tools if tool not in (
        draft_interview_invitation, draft_bulk_interview_invitations,
        generate_interview_questions_for_candidate)]

    llm = _ReadOnlyModel() if read_only else ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key,
                                 callbacks=[UsageCallback(settings.GEMINI_LLM_MODEL)])
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=None if read_only else get_prompt_text("cv-rag-agent-system"),
        checkpointer=checkpointer,
    )

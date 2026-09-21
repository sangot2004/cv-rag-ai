from src.schemas.jd_schema import JDSchema
from src.agent.tools.jd_matching_tool import find_top_candidates_for_jd
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage
from langchain.agents import create_agent
import pytest
import sys
from unittest.mock import patch

sys.path.insert(0, ".")


class FakeModelCallsToolThenAnswers:
    """LLM giả lập: lần đầu luôn gọi find_top_candidates_for_jd ngay lập
    tức (mô phỏng đúng worst-case — LLM không tự hỏi lại HR trước khi gọi
    tool, để kiểm chứng cơ chế chặn kỹ thuật vẫn hoạt động dù LLM "quên"
    tự giác xác nhận).
    """

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        has_tool_result = any(getattr(m, "type", None) == "tool" for m in messages)
        if not has_tool_result:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "find_top_candidates_for_jd",
                        "args": {"jd_text": "Cần Data Engineer, 2 năm KN, biết Python", "top_k": 5},
                        "id": "call1",
                    }
                ],
            )
        return AIMessage(content="Đã hoàn tất theo yêu cầu.")


@pytest.fixture
def graph_with_checkpointer():
    checkpointer = InMemorySaver()
    return create_agent(model=FakeModelCallsToolThenAnswers(), tools=[find_top_candidates_for_jd], checkpointer=checkpointer)


class TestDoubleOptIn:
    def test_tool_stops_before_ranking_without_confirmation(self, graph_with_checkpointer):
        with patch("src.agent.tools.jd_matching_tool.extract_jd_data") as mock_extract, \
                patch("src.agent.tools.jd_matching_tool.rank_candidates_for_jd") as mock_rank:
            mock_extract.return_value = JDSchema(position_title="Data Engineer", raw_text="test")

            config = {"configurable": {"thread_id": "test-no-confirm"}}
            result = graph_with_checkpointer.invoke(
                {"messages": [{"role": "user", "content": "tìm ứng viên"}]}, config=config
            )

            assert "__interrupt__" in result
            mock_rank.assert_not_called()

    def test_interrupt_payload_contains_extracted_criteria(self, graph_with_checkpointer):
        with patch("src.agent.tools.jd_matching_tool.extract_jd_data") as mock_extract:
            mock_extract.return_value = JDSchema(
                position_title="Data Engineer",
                required_skills=["Python", "SQL"],
                min_years_experience=2.0,
                raw_text="test",
            )

            config = {"configurable": {"thread_id": "test-payload"}}
            result = graph_with_checkpointer.invoke(
                {"messages": [{"role": "user", "content": "tìm ứng viên"}]}, config=config
            )

            payload = result["__interrupt__"][0].value
            assert payload["position_title"] == "Data Engineer"
            assert payload["required_skills"] == ["Python", "SQL"]
            assert payload["min_years_experience"] == 2.0
            assert payload["top_k"] == 5

    def test_resume_confirmed_runs_ranking(self, graph_with_checkpointer):
        """Sau khi resume(confirmed=True), ranking PHẢI được gọi đúng 1 lần."""
        with patch("src.agent.tools.jd_matching_tool.extract_jd_data") as mock_extract, \
                patch("src.agent.tools.jd_matching_tool.rank_candidates_for_jd") as mock_rank:
            mock_extract.return_value = JDSchema(position_title="Data Engineer", raw_text="test")
            mock_rank.return_value = [{"candidate_id": "c1", "overall_score": 4.0, "summary": "ok"}]

            config = {"configurable": {"thread_id": "test-confirm"}}
            graph_with_checkpointer.invoke({"messages": [{"role": "user", "content": "tìm"}]}, config=config)

            result = graph_with_checkpointer.invoke(
                Command(resume={"confirmed": True, "edited_criteria": None}), config=config
            )

            mock_rank.assert_called_once()
            assert "__interrupt__" not in result

    def test_resume_cancelled_never_runs_ranking(self, graph_with_checkpointer):
        with patch("src.agent.tools.jd_matching_tool.extract_jd_data") as mock_extract, \
                patch("src.agent.tools.jd_matching_tool.rank_candidates_for_jd") as mock_rank:
            mock_extract.return_value = JDSchema(position_title="Data Engineer", raw_text="test")

            config = {"configurable": {"thread_id": "test-cancel"}}
            graph_with_checkpointer.invoke({"messages": [{"role": "user", "content": "tìm"}]}, config=config)
            graph_with_checkpointer.invoke(Command(resume={"confirmed": False, "edited_criteria": None}), config=config)

            mock_rank.assert_not_called()

    def test_resume_with_edited_criteria_overrides_original(self, graph_with_checkpointer):
        with patch("src.agent.tools.jd_matching_tool.extract_jd_data") as mock_extract, \
                patch("src.agent.tools.jd_matching_tool.rank_candidates_for_jd") as mock_rank:
            mock_extract.return_value = JDSchema(
                position_title="Data Engineer", required_skills=["Python"], raw_text="test"
            )
            mock_rank.return_value = []

            config = {"configurable": {"thread_id": "test-edited"}}
            graph_with_checkpointer.invoke({"messages": [{"role": "user", "content": "tìm"}]}, config=config)

            edited = {"position_title": "Senior Data Engineer", "required_skills": ["Python", "Spark"], "top_k": 8}
            graph_with_checkpointer.invoke(
                Command(resume={"confirmed": True, "edited_criteria": edited}), config=config
            )

            called_jd, called_kwargs = mock_rank.call_args
            called_jd_obj = called_jd[0]
            assert called_jd_obj.position_title == "Senior Data Engineer"
            assert called_jd_obj.required_skills == ["Python", "Spark"]
            assert called_kwargs.get("top_k") == 8 or mock_rank.call_args.kwargs.get("top_k") == 8

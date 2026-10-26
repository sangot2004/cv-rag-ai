from src.db.models import ChatFeedback
from src.chat.message_adapter import visible_messages
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def test_feedback_resolves_owned_displayed_message(api):
    thread = api.create()
    prefix = f"/api/conversations/{thread}"
    response = api.client.post(prefix + "/messages", headers=api.headers(), json={"question": "original"})
    answer = response.json()["message"]
    history = api.client.get(prefix + "/messages", headers=api.headers()).json()
    for message_id in ("invented", history["messages"][0]["id"]):
        assert api.client.post(prefix + "/feedback", headers=api.headers(),
                               json={"message_id": message_id, "feedback": "up"}).status_code == 404
    assert api.client.post(prefix + "/feedback", headers=api.headers(),
                           json={"message_id": answer["id"], "feedback": "up", "answer": "forged"}).status_code == 422
    for vote in ("up", "down"):
        response = api.client.post(prefix + "/feedback", headers=api.headers(),
                                   json={"message_id": answer["id"], "feedback": vote})
        assert response.status_code == 201
    with api.db() as db:
        votes = db.query(ChatFeedback).filter_by(thread_id=thread).all()
        assert len(votes) == 2
        assert all(v.question == "original" and v.answer == answer["content"] for v in votes)


def test_message_projection_legacy_ids_and_internal_blocks():
    messages = [
        HumanMessage(content="hi"),
        AIMessage(content="internal", tool_calls=[{"name": "test", "args": {}, "id": "t"}]),
        ToolMessage(content="internal", tool_call_id="t"),
        AIMessage(content=[{"type": "reasoning", "reasoning": "hidden"},
                           {"type": "text", "text": "also hidden", "thought": True},
                           {"type": "text", "text": "visible"}]),
    ]
    projected = visible_messages("thread", messages)
    assert projected == visible_messages("thread", messages)
    assert [m["content"] for m in projected] == ["hi", "visible"]
    assert projected[0]["id"].startswith("legacy-")


def test_arbitrary_tool_output_cannot_create_candidate_cards():
    messages=[HumanMessage(content="hi"),
      AIMessage(content="",tool_calls=[{"name":"scope_probe","args":{},"id":"t"}]),
      ToolMessage(content='{"candidate_id":"forged"}', tool_call_id="t",artifact={
        "kind":"candidate_ranking","title":"Fake","items":[]}),
      AIMessage(content="Normal answer")]
    assert "candidate_results" not in visible_messages("thread",messages)[-1]


def test_evaluation_tool_emits_structured_artifact(monkeypatch):
    import importlib
    from src.evaluation.rubric import EvaluationResult
    module=importlib.import_module("src.agent.tools.evaluation_tool")
    candidate_id="33333333-3333-4333-8333-000000000001"
    monkeypatch.setattr(module,"evaluate_candidate",lambda *args: EvaluationResult(
        candidate_id=candidate_id,overall_score=4,criteria=[],strengths=["Python"],concerns=[],summary="Phù hợp"))
    result=module.evaluate_candidate_against_jd.invoke({"type":"tool_call","id":"evaluation",
        "name":"evaluate_candidate_against_jd","args":{"candidate_id":candidate_id,"job_description":"Python"}})
    assert result.artifact["kind"]=="candidate_evaluation"
    assert result.artifact["items"][0]["candidate_id"]==candidate_id
    assert "Điểm tổng: 4.0/5" in result.content

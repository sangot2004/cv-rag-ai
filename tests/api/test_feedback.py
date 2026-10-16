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

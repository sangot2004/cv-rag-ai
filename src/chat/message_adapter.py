"""Only expose user text and final assistant text from the agent state."""
import hashlib
import json
from src.chat.criteria import Criteria


def display_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block if isinstance(block, str) else block["text"]
            for block in content
            if isinstance(block, str) or (
                isinstance(block, dict) and block.get("type") == "text"
                and not block.get("thought") and isinstance(block.get("text"), str)
            )
        )
    return ""


def visible_messages(thread_id: str, messages) -> list[dict]:
    visible = []
    for index, msg in enumerate(messages):
        kind = getattr(msg, "type", None)
        if kind not in ("human", "ai") or (kind == "ai" and getattr(msg, "tool_calls", None)):
            continue
        text = display_text(msg.content)
        if not text.strip():
            continue
        identifier = getattr(msg, "id", None)
        if not identifier:
            material = json.dumps([thread_id, index, kind, text], ensure_ascii=False)
            identifier = "legacy-" + hashlib.sha256(material.encode()).hexdigest()
        visible.append({"id": str(identifier), "role": "user" if kind == "human" else "assistant", "content": text})
    return visible


def pending_confirmations(state) -> list[dict]:
    result = {}
    for task in state.tasks:
        # LangGraph retains old interrupts on completed tasks until all sibling
        # tools finish. They must not be offered to the user a second time.
        if task.result is not None:
            continue
        for item in task.interrupts:
            payload = item.value
            if not isinstance(payload, dict) or payload.get("type") != "confirm_jd_criteria":
                raise RuntimeError("Unsupported pending confirmation")
            result[item.id] = {
                "confirmation_id": item.id, "type": payload["type"],
                "criteria": Criteria.model_validate(
                    {key: value for key, value in payload.items() if key != "type"}
                ).model_dump(),
            }
    return list(result.values())

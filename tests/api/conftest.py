import importlib
import json
from types import SimpleNamespace
from threading import Event

import pytest
from fastapi.testclient import TestClient
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.app import create_app
from src.auth import service as auth
from src.chat import checkpoints, conversation_store, feedback_store
from src.db.models import Base, Department
from src.schemas.jd_schema import JDSchema
from src.retrieval.access_scope import current_department_id

PASSWORD = "test-password-123!"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("OPS_ENABLED", "false")
    engine = create_engine("sqlite:///" + str(tmp_path / "metadata.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    from src.db import session
    for module in (auth, conversation_store, feedback_store, session):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add_all([Department(department_id="dept-a", department_name="A"),
                    Department(department_id="dept-b", department_name="B")])
        db.commit()
    users = {name: auth._create_user(name, PASSWORD, role, dept)
             for name, role, dept in [("admin", "admin", None), ("alice", "tester", "dept-a"),
                                      ("bobby", "tester", "dept-a"), ("carol", "tester", "dept-b")]}
    tokens = {name: auth.login(name, PASSWORD) for name in users}
    started, release = Event(), Event()
    observations, extracted, ranked = [], [], []
    failure = []

    @tool
    def scope_probe() -> str:
        """Return the authenticated scope for the offline test."""
        user = auth.require_user()
        value = (user.username, user.role, current_department_id.get())
        observations.append(value)
        return json.dumps(value)

    class Model:
        def bind_tools(self, *args, **kwargs):
            return self

        def invoke(self, messages, **kwargs):
            question_index = max(i for i, msg in enumerate(messages) if msg.type == "human")
            question = messages[question_index].content
            tools = [m for m in messages[question_index + 1:] if m.type == "tool"]
            if tools:
                return AIMessage(content=[{"type": "text", "text": tools[-1].content},
                                          {"type": "reasoning", "reasoning": "hidden"}])
            if question == "wait":
                started.set()
                assert release.wait(10), "Test failed to release model"
            if question == "fail":
                raise failure[0] if failure else RuntimeError("private-key=SECRET")
            if question.startswith("rank"):
                count = 2 if question == "rank two" else 1
                return AIMessage(content="", tool_calls=[
                    {"name": "find_top_candidates_for_jd", "args": {"jd_text": "Python"}, "id": f"call-{i}"}
                    for i in range(count)])
            return AIMessage(content="", tool_calls=[{"name": "scope_probe", "args": {}, "id": "scope"}])

    jd_module = importlib.import_module("src.agent.tools.jd_matching_tool")
    def extract(text):
        extracted.append(text)
        return JDSchema(position_title="Data Engineer", required_skills=["Python"],
                        min_years_experience=1, preferred_education="Bachelor", raw_text=text)
    def rank(jd, top_k=5):
        ranked.append((jd.model_copy(deep=True), top_k, auth.require_user().username, current_department_id.get()))
        return []
    monkeypatch.setattr(jd_module, "extract_jd_data", extract)
    monkeypatch.setattr(jd_module, "rank_candidates_for_jd", rank)
    router = importlib.import_module("src.agent.router")

    with SqliteSaver.from_conn_string(str(tmp_path / "checkpoints.db")) as saver:
        monkeypatch.setattr(checkpoints, "get_checkpointer", lambda: saver)
        def build():
            return create_agent(model=Model(), tools=[scope_probe, jd_module.find_top_candidates_for_jd],
                                checkpointer=saver)
        graph = build()
        monkeypatch.setattr(router, "_get_graph", lambda: graph)
        # read_state intentionally uses the production read-only graph, not this mock.
        with TestClient(create_app()) as client:
            yield SimpleNamespace(client=client, db=factory, users=users, tokens=tokens, saver=saver,
                                  graph=graph, build=build, router=router, started=started, release=release,
                                  observations=observations, extracted=extracted, ranked=ranked, failure=failure,
                                  headers=lambda name="alice": {"Authorization": "Bearer " + tokens[name]},
                                  create=lambda name="alice": client.post("/api/conversations",
                                      headers={"Authorization": "Bearer " + tokens[name]}, json={}).json()["thread_id"])
        release.set()
    engine.dispose()

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import importlib
import sys
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth import service as auth
from src.chat import conversation_store as chats
from src.chat import feedback_store as feedback
from src.db.models import Base, Department, AppUser, AuthSession, ChatConversation, ChatFeedback

PASSWORD = "test-password-123!"


@pytest.fixture
def accounts(monkeypatch, tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    for module in (auth, chats, feedback):
        monkeypatch.setattr(module, "SessionLocal", factory)

    from src.db import session

    monkeypatch.setattr(session, "SessionLocal", factory)

    with factory() as db:
        db.add_all([Department(department_id="dept-a", department_name="Demo A"),
                    Department(department_id="dept-b", department_name="Demo B")])
        db.commit()

    ids = {name: auth._create_user(name, PASSWORD, role, department)
           for name, role, department in [("admin", "admin", None), ("alice", "tester", "dept-a"),
                                          ("bobby", "tester", "dept-b")]}
    tokens = {name: auth.login(name, PASSWORD) for name in ids}

    from src.chat import checkpoints
    from langgraph.checkpoint.sqlite import SqliteSaver

    with SqliteSaver.from_conn_string(str(tmp_path / "history.db")) as saver:
        monkeypatch.setattr(checkpoints, "get_checkpointer", lambda: saver)
        yield SimpleNamespace(ids=ids, tokens=tokens, db=factory, saver=saver)

    engine.dispose()


def test_passwords_and_login_lock(accounts):
    encoded = auth.hash_password(PASSWORD)
    assert encoded != auth.hash_password(PASSWORD)
    assert auth.verify_password(PASSWORD, encoded)
    assert not auth.verify_password("wrong", encoded)

    for _ in range(5):
        with pytest.raises(auth.AccessDenied):
            auth.login("alice", "incorrect")

    with pytest.raises(auth.AccessDenied):
        auth.login("alice", PASSWORD)

    with accounts.db() as db:
        user = db.get(AppUser, accounts.ids["alice"])
        user.locked_until = datetime.utcnow() - timedelta(seconds=1)
        db.commit()

    assert auth.login("alice", PASSWORD)


def test_ownership_all_store_operations(accounts):
    with auth.auth_scope(accounts.tokens["alice"]):
        thread = chats.create_conversation()
        chats.touch_conversation(thread, "My private question")
        feedback.save_feedback(thread, "q", "a", "up")
        assert len(chats.list_conversations()) == 1

    for name in ("bobby", "admin"):
        with auth.auth_scope(accounts.tokens[name]):
            assert chats.list_conversations() == []
            for action in (lambda: chats.require_conversation(thread),
                           lambda: chats.touch_conversation(thread, "overwrite"),
                           lambda: chats.delete_conversation(thread),
                           lambda: feedback.save_feedback(thread, "q", "a", "up")):
                with pytest.raises(auth.AccessDenied):
                    action()

    with pytest.raises(auth.AccessDenied):
        chats.create_conversation()

    with auth.auth_scope(accounts.tokens["alice"]):
        with pytest.raises(auth.AccessDenied):
            chats.touch_conversation("invented-thread")


def test_logout_expiration_and_disabled_account(accounts):
    token = accounts.tokens["alice"]
    auth.logout(token)

    with pytest.raises(auth.AccessDenied):
        with auth.auth_scope(token):
            pass

    with accounts.db() as db:
        db.get(AuthSession, auth._digest(accounts.tokens["bobby"])
               ).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.get(AppUser, accounts.ids["admin"]).is_active = False
        db.commit()

    for name in ("admin", "bobby"):
        with pytest.raises(auth.AccessDenied):
            with auth.auth_scope(accounts.tokens[name]):
                pass


def test_roles_and_department_cannot_be_overridden(accounts):
    with auth.auth_scope(accounts.tokens["alice"]):
        assert auth.resolve_department() == "dept-a"
        with pytest.raises(auth.AccessDenied):
            auth.resolve_department("dept-b")
        with pytest.raises(auth.AccessDenied):
            auth.create_user("newuser", PASSWORD, "admin")
        with pytest.raises(auth.AccessDenied):
            feedback.get_negative_feedback_examples()

    with auth.auth_scope(accounts.tokens["admin"]):
        assert auth.resolve_department() is None
        with pytest.raises(ValueError):
            auth.create_user("tester3", PASSWORD)
        with pytest.raises(ValueError):
            auth.create_user("tester3", PASSWORD, department_id="unknown")
        assert auth.create_user("tester3", PASSWORD, department_id="dept-a")


def test_legacy_is_hidden_even_from_admin(accounts):
    with accounts.db() as db:
        db.add(ChatConversation(thread_id="legacy"))
        db.commit()

    with auth.auth_scope(accounts.tokens["admin"]):
        assert chats.list_conversations() == []
        with pytest.raises(auth.AccessDenied):
            chats.require_conversation("legacy")


def test_delete_removes_checkpoints_feedback_and_prevents_resurrection(accounts):
    from langgraph.checkpoint.base import empty_checkpoint

    with auth.auth_scope(accounts.tokens["alice"]):
        thread = chats.create_conversation()
        feedback.save_feedback(thread, "q", "a", "down")
        config = {"configurable": {"thread_id": thread, "checkpoint_ns": ""}}
        accounts.saver.put(config, empty_checkpoint(), {}, {})
        assert accounts.saver.get_tuple(config)
        chats.delete_conversation(thread)
        assert accounts.saver.get_tuple(config) is None
        assert chats.list_conversations() == []

        with pytest.raises(auth.AccessDenied):
            chats.touch_conversation(thread)

    with accounts.db() as db:
        assert db.get(ChatConversation, thread).deleted_at is not None
        assert db.query(ChatFeedback).count() == 0


def test_cleanup_failure_still_denies_access(accounts, monkeypatch):

    from src.chat import checkpoints
    monkeypatch.setattr(checkpoints, "delete_checkpoints", Mock(side_effect=RuntimeError("disk error")))

    with auth.auth_scope(accounts.tokens["alice"]):
        thread = chats.create_conversation()
        with pytest.raises(RuntimeError):
            chats.delete_conversation(thread)
        with pytest.raises(auth.AccessDenied):
            chats.require_conversation(thread)
        assert chats.list_conversations() == []


def test_router_rejects_other_owner_before_graph(accounts, monkeypatch):
    monkeypatch.setitem(sys.modules, "src.agent.agent_executor", SimpleNamespace(build_agent_executor=Mock()))
    sys.modules.pop("src.agent.router", None)
    router = importlib.import_module("src.agent.router")
    graph = Mock()
    monkeypatch.setattr(router, "_get_graph", graph)

    with auth.auth_scope(accounts.tokens["alice"]):
        thread = chats.create_conversation()

    with auth.auth_scope(accounts.tokens["bobby"]):
        for action in (lambda: router.get_conversation_messages(thread),
                       lambda: router.has_pending_confirmation(thread),
                       lambda: router.ask("hello", thread),
                       lambda: router.resume(thread, True)):
            with pytest.raises(auth.AccessDenied):
                action()

    graph.assert_not_called()
    sys.modules.pop("src.agent.router", None)


def test_admin_operations_fail_before_side_effects(accounts):
    from src.ops.optimization import propose, approve, rollback
    from src.ops.experiments import run_experiment
    from src.interfaces.notification_interface import dispatch_bulk_emails, get_batch_status

    with auth.auth_scope(accounts.tokens["alice"]):
        for action in (lambda: propose({}), lambda: approve("id"), lambda: rollback(),
                       lambda: run_experiment("id", "dataset"),
                       lambda: dispatch_bulk_emails([]), lambda: get_batch_status("id")):
            with pytest.raises(auth.AccessDenied):
                action()


def test_auth_context_is_reset_after_error(accounts):
    with pytest.raises(RuntimeError):
        with auth.auth_scope(accounts.tokens["alice"]):
            raise RuntimeError()

    with pytest.raises(auth.AccessDenied):
        auth.require_user()


def test_migration_retains_legacy_and_downgrades(tmp_path):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util
    from pathlib import Path

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE departments (department_id CHAR(36) PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE chat_conversations (thread_id CHAR(36) PRIMARY KEY, title VARCHAR(255))")
        connection.exec_driver_sql("INSERT INTO chat_conversations VALUES ('old', 'Old chat')")
        spec = importlib.util.spec_from_file_location("auth_migration", Path(
            __file__).parents[1] / "alembic/versions/add_auth_ownership.py")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.exec_driver_sql(
                "SELECT owner_user_id FROM chat_conversations WHERE thread_id='old'").scalar() is None
            migration.downgrade()
        assert connection.exec_driver_sql(
            "SELECT title FROM chat_conversations WHERE thread_id='old'").scalar() == "Old chat"


def test_router_uses_authenticated_department(accounts, monkeypatch):
    from src.retrieval.access_scope import current_department_id

    monkeypatch.setitem(sys.modules, "src.agent.agent_executor", SimpleNamespace(build_agent_executor=Mock()))
    sys.modules.pop("src.agent.router", None)
    router = importlib.import_module("src.agent.router")
    scopes = []

    def invoke(*args, **kwargs):
        scopes.append(current_department_id.get())
        return {"messages": [SimpleNamespace(content="answer")]}

    monkeypatch.setattr(router, "_get_graph", lambda: SimpleNamespace(invoke=invoke))
    monkeypatch.setattr(router, "get_key_manager", lambda: SimpleNamespace(num_keys=1))

    with auth.auth_scope(accounts.tokens["alice"]):
        thread = chats.create_conversation()
        assert router.ask("hello", thread)["content"] == "answer"
        assert router.resume(thread, True)["content"] == "answer"
        with pytest.raises(auth.AccessDenied):
            router.ask("hello", thread, department_id="dept-b")

    assert scopes == ["dept-a", "dept-a"]
    assert current_department_id.get() is None
    sys.modules.pop("src.agent.router", None)


def test_admin_disable_revokes_sessions_and_cannot_disable_self(accounts):
    with auth.auth_scope(accounts.tokens["alice"]):
        with pytest.raises(auth.AccessDenied):
            auth.set_user_active(accounts.ids["bobby"], False)

    with auth.auth_scope(accounts.tokens["admin"]):
        with pytest.raises(ValueError):
            auth.set_user_active(accounts.ids["admin"], False)
        auth.set_user_active(accounts.ids["alice"], False)

    with pytest.raises(auth.AccessDenied):
        with auth.auth_scope(accounts.tokens["alice"]):
            pass

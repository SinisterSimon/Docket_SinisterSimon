from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.db import Base


def _client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    local = sessionmaker(engine, expire_on_commit=False)

    def session():
        with local() as s:
            yield s

    main.app.dependency_overrides[main.get_session] = session
    return TestClient(main.app)


def test_health():
    assert _client().get("/health").json() == {"ok": True}


def test_add_and_list_a_message():
    c = _client()
    c.post("/messages", data={"sender": "a@example.com", "subject": "Where is my order?", "body": "Hi"})
    page = c.get("/").text
    assert "Where is my order?" in page and "new" in page


def test_offline_llm_is_free_and_deterministic():
    from app.llm.client import OfflineLLM

    a = OfflineLLM().complete(system="x", messages=[], model="claude-haiku-5-5")
    b = OfflineLLM().complete(system="x", messages=[], model="claude-haiku-5-5")
    assert a == b


def test_draft_button_saves_a_reply_with_sources():
    from app import knowledge
    from app.llm.embeddings import OfflineEmbedder

    c = _client()
    session = next(main.app.dependency_overrides[main.get_session]())
    knowledge.rebuild(session, knowledge.load_sample_store(), OfflineEmbedder())
    c.post("/messages", data={"sender": "kati@example.com", "subject": "Order", "body": "Where is #1001?"})
    c.post("/messages/1/draft")
    page = c.get("/").text
    assert "drafted" in page and "Order #1001" in page

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import knowledge
from app.agent import answer, parse_action
from app.db import Base
from app.llm.client import LLMReply, OfflineLLM
from app.llm.embeddings import OfflineEmbedder
from app.store import SampleStore
from app.tools import ToolBox


def _tools(sender="kati@example.com"):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = Session(engine)
    knowledge.rebuild(s, knowledge.load_sample_store(), OfflineEmbedder())
    return ToolBox(s, OfflineEmbedder(), SampleStore(), sender)


def test_order_status_only_for_the_orders_owner():
    assert "Omniva" in _tools().order_status("1001").text
    assert "No order" in _tools(sender="stranger@example.com").order_status("1001").text


def test_stock_says_in_stock_or_sold_out_never_counts():
    text = _tools().check_stock("oxygen").text
    assert "160 cm: in stock" in text and "156 cm: sold out" in text and "2" not in text.split(".", 1)[1]


def test_agent_looks_up_the_order_then_replies_with_sources():
    r = answer(OfflineLLM(), _tools(), "Where is my board?", "Hi, where is order #1001?")
    assert [s.tool for s in r.steps][0] == "order_status"
    assert "CE123456789EE" in r.reply and not r.handoff and "Order #1001" in r.sources


def test_agent_hands_off_complaints_without_tools():
    r = answer(OfflineLLM(), _tools(), "Broken", "My board arrived cracked, this is terrible")
    assert r.handoff and r.steps == []


def test_policy_question_uses_the_knowledge_base():
    r = answer(OfflineLLM(), _tools(), "Shipping", "How long does delivery to Latvia take?")
    assert r.steps[-1].tool == "search_knowledge" and "Shipping · Delivery times" in r.sources


def test_parse_action_tolerates_fences_and_rejects_junk():
    assert parse_action('```json\n{"tool": "check_stock", "args": {"product": "x"}}\n```')["tool"] == "check_stock"
    with pytest.raises(ValueError):
        parse_action("Sure, happy to help!")


class Garbled:
    def complete(self, **kw):
        return LLMReply("not json", "fake", 1, 1)


def test_a_model_that_never_answers_in_json_ends_in_a_handoff():
    r = answer(Garbled(), _tools(), "Hi", "Hello")
    assert r.handoff and "ran out of steps" in r.reply

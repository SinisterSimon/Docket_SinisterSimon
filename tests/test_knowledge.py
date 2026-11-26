from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import knowledge
from app.db import Base
from app.llm.embeddings import OfflineEmbedder, cosine


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_policies_split_into_one_chunk_per_section():
    pieces = knowledge.split_policy("x.md", "# Shipping\n\n## Costs\nA.\n\n## Tracking\nB.")
    assert [p.title for p in pieces] == ["Shipping · Costs", "Shipping · Tracking"]


def test_long_sections_are_split_by_paragraph():
    body = "\n\n".join(["word " * 100] * 5)
    pieces = knowledge.split_policy("x.md", f"# Doc\n\n## Long\n{body}")
    assert len(pieces) > 1 and all(len(p.text) <= knowledge.MAX_CHARS + 600 for p in pieces)


def test_sample_store_loads_policies_and_products():
    pieces = knowledge.load_sample_store()
    assert {p.source for p in pieces} == {"policy", "product"}
    assert any("159W cm" in p.text for p in pieces)


def test_offline_embedder_is_deterministic_and_normalised():
    a, b = OfflineEmbedder().embed(["free shipping", "free shipping"])
    assert a == b and abs(cosine(a, a) - 1) < 1e-9


def test_search_finds_the_right_policy():
    s, emb = _session(), OfflineEmbedder()
    knowledge.rebuild(s, knowledge.load_sample_store(), emb)
    top = knowledge.search(s, "how long does delivery to Latvia take", emb)[0]
    assert top.chunk.title == "Shipping · Delivery times"
    assert "Returns" in knowledge.search(s, "can I return a waxed board", emb)[0].chunk.title


def test_rebuild_replaces_and_other_embed_models_are_ignored():
    s, emb = _session(), OfflineEmbedder()
    n = knowledge.rebuild(s, knowledge.load_sample_store(), emb)
    assert knowledge.rebuild(s, knowledge.load_sample_store(), emb) == n

    class Other(OfflineEmbedder):
        model = "other"

    assert knowledge.search(s, "shipping", Other()) == []

"""The store's knowledge base: load products and policies, split them, embed them, search them."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.llm.embeddings import Embedder, cosine
from app.models import KnowledgeChunk

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_store"
MAX_CHARS = 900  # long sections are split so one chunk stays on one topic


@dataclass(frozen=True)
class Piece:
    source: str
    ref: str
    title: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: KnowledgeChunk
    score: float


def split_policy(ref: str, markdown: str) -> list[Piece]:
    """One piece per `##` section, titled "Doc · Section"; oversized sections split by paragraph."""
    doc_title = next((ln[2:].strip() for ln in markdown.splitlines() if ln.startswith("# ")), ref)
    pieces = []
    for block in re.split(r"^## ", markdown, flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        title, buf = f"{doc_title} · {heading.strip()}", ""
        for para in [p.strip() for p in body.split("\n\n") if p.strip()]:
            if buf and len(buf) + len(para) > MAX_CHARS:
                pieces.append(Piece("policy", ref, title, buf))
                buf = ""
            buf = f"{buf}\n\n{para}".strip()
        if buf:
            pieces.append(Piece("policy", ref, title, buf))
    return pieces


def product_piece(p: dict) -> Piece:
    price = f"{p['price_cents'] / 100:.2f} {p.get('currency', 'EUR')}"
    lines = [p["title"], p.get("description", ""), f"Price: {price}"]
    if p.get("variants"):
        lines.append("Options: " + ", ".join(p["variants"]))
    return Piece("product", p["handle"], p["title"], "\n".join(x for x in lines if x))


def load_sample_store(directory: Path = SAMPLE_DIR) -> list[Piece]:
    pieces = []
    for md in sorted(directory.glob("*.md")):
        pieces += split_policy(md.name, md.read_text())
    products = directory / "products.json"
    if products.exists():
        pieces += [product_piece(p) for p in json.loads(products.read_text())]
    return pieces


def rebuild(session: Session, pieces: list[Piece], embedder: Embedder) -> int:
    """Replace the whole knowledge base. Embeds every piece in one batch call."""
    vectors = embedder.embed([f"{p.title}\n{p.text}" for p in pieces]) if pieces else []
    session.execute(delete(KnowledgeChunk))
    session.add_all(
        KnowledgeChunk(source=p.source, ref=p.ref, title=p.title, text=p.text,
                       embed_model=embedder.model, embedding=v)
        for p, v in zip(pieces, vectors, strict=True)
    )
    session.commit()
    return len(pieces)


def search(session: Session, query: str, embedder: Embedder, k: int = 4) -> list[Hit]:
    """The k chunks closest in meaning to the query. Chunks from another embed model are skipped,
    because vectors from different models can't be compared."""
    q = embedder.embed([query])[0]
    chunks = session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.embed_model == embedder.model)).all()
    hits = sorted((Hit(c, cosine(q, c.embedding)) for c in chunks), key=lambda h: h.score, reverse=True)
    return hits[:k]

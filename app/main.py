"""Docket web app. Phase 0: list customer messages and add one by hand."""
from html import escape

from fastapi import Depends, FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import knowledge
from app.db import Base, SessionLocal, engine
from app.llm.embeddings import get_embedder
from app.models import CustomerMessage, KnowledgeChunk

app = FastAPI(title="Docket")
Base.metadata.create_all(engine)  # Alembic migrations arrive with the first schema change


def get_session():
    with SessionLocal() as session:
        yield session


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def inbox(session: Session = Depends(get_session)):
    rows = session.scalars(select(CustomerMessage).order_by(CustomerMessage.received_at.desc())).all()
    items = "".join(
        f"<li><strong>{escape(m.sender)}</strong> · {escape(m.subject or '-')} · <em>{m.status.value}</em></li>"
        for m in rows
    ) or "<li>No messages yet.</li>"
    return f"""<!doctype html><title>Docket</title><h1>Docket</h1><ul>{items}</ul>
<form method=post action=/messages><input name=sender placeholder=From required>
<input name=subject placeholder=Subject><textarea name=body required></textarea><button>Add</button></form>"""


@app.post("/messages")
def add_message(sender: str = Form(), body: str = Form(), subject: str = Form(""),
                session: Session = Depends(get_session)):
    session.add(CustomerMessage(sender=sender, subject=subject, body=body))
    session.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/knowledge/rebuild")
def rebuild_knowledge(session: Session = Depends(get_session)):
    knowledge.rebuild(session, knowledge.load_sample_store(), get_embedder())
    return RedirectResponse("/knowledge", status_code=303)


@app.get("/knowledge", response_class=HTMLResponse)
def knowledge_page(q: str = Query(""), session: Session = Depends(get_session)):
    count = session.query(KnowledgeChunk).count()
    hits = knowledge.search(session, q, get_embedder()) if q and count else []
    results = "".join(
        f"<li><strong>{escape(h.chunk.title)}</strong> <small>{h.score:.2f} · {h.chunk.source}</small>"
        f"<p>{escape(h.chunk.text)}</p></li>"
        for h in hits
    )
    return f"""<!doctype html><title>Knowledge · Docket</title><h1>Knowledge base</h1>
<p>{count} chunks.</p>
<form method=post action=/knowledge/rebuild><button>Rebuild from sample store</button></form>
<form><input name=q value="{escape(q)}" placeholder="Ask like a customer would" size=50><button>Search</button></form>
<ol>{results}</ol>"""

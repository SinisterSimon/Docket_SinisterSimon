"""Docket web app. Phase 0: list customer messages and add one by hand."""
from html import escape

from fastapi import Depends, FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import agent, knowledge
from app.db import Base, SessionLocal, engine
from app.llm import get_llm
from app.llm.embeddings import get_embedder
from app.models import CustomerMessage, Draft, KnowledgeChunk, Status
from app.shopify.client import client_from_env
from app.shopify_knowledge import load_from_shopify
from app.store import get_store
from app.tools import ToolBox

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
    def row(m: CustomerMessage) -> str:
        d = m.drafts[-1] if m.drafts else None
        draft = (f"<blockquote>{escape(d.text)}<br><small>{'HAND OFF · ' if d.handoff else ''}"
                 f"sources: {escape(', '.join(d.sources) or 'none')} · {escape(d.model)}</small></blockquote>"
                 if d else f"<form method=post action=/messages/{m.id}/draft><button>Draft reply</button></form>")
        return (f"<li><strong>{escape(m.sender)}</strong> · {escape(m.subject or '-')} · <em>{m.status.value}</em>"
                f"<p>{escape(m.body)}</p>{draft}</li>")

    items = "".join(row(m) for m in rows) or "<li>No messages yet.</li>"
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
    client = client_from_env()
    pieces = load_from_shopify(client) if client else knowledge.load_sample_store()
    knowledge.rebuild(session, pieces, get_embedder())
    return RedirectResponse("/knowledge", status_code=303)


@app.get("/knowledge", response_class=HTMLResponse)
def knowledge_page(q: str = Query(""), session: Session = Depends(get_session)):
    count = session.query(KnowledgeChunk).count()
    source = "Shopify" if client_from_env() else "sample store (test data)"
    hits = knowledge.search(session, q, get_embedder()) if q and count else []
    results = "".join(
        f"<li><strong>{escape(h.chunk.title)}</strong> <small>{h.score:.2f} · {h.chunk.source}</small>"
        f"<p>{escape(h.chunk.text)}</p></li>"
        for h in hits
    )
    return f"""<!doctype html><title>Knowledge · Docket</title><h1>Knowledge base</h1>
<p>{count} chunks.</p>
<form method=post action=/knowledge/rebuild><button>Rebuild from {source}</button></form>
<form><input name=q value="{escape(q)}" placeholder="Ask like a customer would" size=50><button>Search</button></form>
<ol>{results}</ol>"""


@app.post("/messages/{message_id}/draft")
def draft_reply(message_id: int, session: Session = Depends(get_session)):
    m = session.get(CustomerMessage, message_id)
    tools = ToolBox(session, get_embedder(), get_store(), m.sender)
    r = agent.answer(get_llm(), tools, m.subject, m.body)
    session.add(Draft(message_id=m.id, model=r.model, text=r.reply, handoff=r.handoff, sources=r.sources,
                      steps=[s.__dict__ for s in r.steps], input_tokens=r.input_tokens, output_tokens=r.output_tokens))
    m.status = Status.handed_off if r.handoff else Status.drafted
    session.commit()
    return RedirectResponse("/", status_code=303)

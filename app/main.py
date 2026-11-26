"""Docket web app. Phase 0: list customer messages and add one by hand."""
from html import escape

from fastapi import Depends, FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import CustomerMessage

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

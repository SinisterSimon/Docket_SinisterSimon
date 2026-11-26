"""Database setup. SQLite in tests and by default, Postgres (Neon) via DATABASE_URL."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///docket.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


engine = make_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)

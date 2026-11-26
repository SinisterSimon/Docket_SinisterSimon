"""Customer messages and the replies Inbox drafts for them."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Channel(str, enum.Enum):
    email = "email"


class Status(str, enum.Enum):
    new = "new"            # not drafted yet
    drafted = "drafted"    # a reply is waiting for a human
    sent = "sent"
    handed_off = "handed_off"  # the agent decided a person should answer


class CustomerMessage(Base):
    __tablename__ = "customer_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[Channel] = mapped_column(Enum(Channel), default=Channel.email)
    sender: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.new, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    drafts: Mapped[list["Draft"]] = relationship(back_populates="message", order_by="Draft.id")


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("customer_messages.id"), index=True)
    model: Mapped[str] = mapped_column(String(60))
    text: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    message: Mapped[CustomerMessage] = relationship(back_populates="drafts")

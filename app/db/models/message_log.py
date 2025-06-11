"""
SQLAlchemy model for logging messages within sessions.

This model captures details about each message, including its sender, content,
associated mood and tone tags, and the type of response it represents.
It maintains a relationship with the Session model.
"""

from uuid import uuid4
from app.db.base import Base
from sqlalchemy import Column, String, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.enums import SenderEnum, ResponseTypeEnum

class MessageLog(Base):
    __tablename__ = "message_logs"

    message_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("sessions.session_id"))
    sender = Column(Enum(SenderEnum))
    content = Column(Text)
    mood_tag = Column(String, nullable=True)
    tone_tag = Column(String, nullable=True)
    response_type = Column(Enum(ResponseTypeEnum), nullable=True)

    session = relationship("Session", back_populates="messages")

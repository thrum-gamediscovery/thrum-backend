"""
SQLAlchemy model for tracking user sessions.

This model stores session-specific information such as start and end times,
user mood upon entry and exit, a record of game recommendations sent,
and any user feedback. It maintains relationships with both the User
and MessageLog models.
"""

from uuid import uuid4
from datetime import datetime
from app.db.base import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, ForeignKey, TIMESTAMP, JSON

class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"))
    start_time = Column(TIMESTAMP, default=datetime.utcnow)
    end_time = Column(TIMESTAMP, nullable=True)
    entry_mood = Column(String)
    exit_mood = Column(String)
    game_recs_sent = Column(JSON, default=list)
    user_feedback = Column(String)

    user = relationship("User", back_populates="sessions")
    messages = relationship("MessageLog", back_populates="session")

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
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey, TIMESTAMP, DateTime, Enum, Boolean
from app.db.models.enums import SessionTypeEnum
from sqlalchemy.dialects.postgresql import JSON

class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.user_id"))
    start_time = Column(TIMESTAMP(timezone=False), server_default=func.now())
    end_time = Column(TIMESTAMP(timezone=False), server_default=func.now())
    entry_mood = Column(String)
    exit_mood = Column(String)
    state = Column(Enum(SessionTypeEnum), default=SessionTypeEnum.ONBOARDING)
    awaiting_reply = Column(Boolean, default=False)
    last_thrum_timestamp = Column(DateTime, nullable=True)
    user = relationship("UserProfile", back_populates="sessions")
    interactions = relationship("Interaction", back_populates="session", cascade="all, delete-orphan")
    game_recommendations = relationship("GameRecommendation", back_populates="session", cascade="all, delete-orphan")
    meta_data = Column(JSON, nullable=True)

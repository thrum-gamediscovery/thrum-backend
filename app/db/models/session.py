"""
SQLAlchemy model for tracking user sessions.

This model stores session-specific information such as start and end times,
user mood upon entry and exit, a record of game recommendations sent,
current conversation phase, rejection history, and short-term memory.
It maintains relationships with both the UserProfile and Interaction models.
"""

from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, ForeignKey, TIMESTAMP, DateTime,
    Boolean, Integer, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import Enum as SQLAlchemyEnum
from sqlalchemy.ext.mutable import MutableDict
from app.db.base import Base
from app.db.models.enums import SessionTypeEnum, PhaseEnum

class Session(Base):
    __tablename__ = "sessions"

    # Primary identity
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.user_id"))

    # Timestamps
    start_time = Column(TIMESTAMP(timezone=False), server_default=func.now())
    end_time = Column(TIMESTAMP(timezone=False), server_default=func.now())
    awaiting_reply = Column(Boolean, default=False)
    last_thrum_timestamp = Column(DateTime, nullable=True)

    # Phase control
    phase = Column(SQLAlchemyEnum(PhaseEnum), default=PhaseEnum.INTRO)
    discovery_questions_asked = Column(Integer, default=0)

    # Mood / vibe / memory tracking
    entry_mood = Column(String, nullable=True)
    exit_mood = Column(String, nullable=True)
    genre = Column(ARRAY(String), nullable=True)
    platform_preference = Column(ARRAY(String), nullable=True)
    last_recommended_game = Column(String, nullable=True)
    rejected_games = Column(ARRAY(String), default=[]) 
    story_preference = Column(Boolean, nullable=True)

    # Flow control flags — these help manage session dynamics, tone shifts, and user engagement
    # All of these are reset per session and used by the dialog engine to track behavioral shifts

    state = Column(SQLAlchemyEnum(SessionTypeEnum), default=SessionTypeEnum.ONBOARDING)
    # Example: ONBOARDING, ACTIVE, CLOSED — used to segment session state in analytics or trigger logic

    intent_override_triggered = Column(Boolean, default=False)
    followup_triggered = Column(Boolean, default=False)
    # Example: Set to True if user says "just give me a game" and bot skips to direct delivery

    game_rejection_count = Column(Integer, default=0)
    
    shared_with_friend = Column(Boolean, default=False)
    # Example: Set to True if user responds positively to "Send this to your friends: ..."

    tone_shift_detected = Column(Boolean, default=False)
    # Example: True if bot detects frustration or sarcasm and adjusts tone/length accordingly

    engagement_level = Column(String, nullable=True)
    # Example: Values like 'low', 'medium', or 'high' — helps tailor future reply length or pacing

    # Flexible metadata field (for debug logs, GPT traces, etc.)
    meta_data = Column(MutableDict.as_mutable(JSON), nullable=True)

    memory = Column(MutableDict.as_mutable(JSON), default=dict)

    # Relationships
    user = relationship("UserProfile", back_populates="sessions")
    interactions = relationship("Interaction", back_populates="session", cascade="all, delete-orphan")
    game_recommendations = relationship("GameRecommendation", back_populates="session", cascade="all, delete-orphan")

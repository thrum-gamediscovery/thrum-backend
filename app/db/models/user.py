"""
SQLAlchemy model for the User entity.

This model defines the database schema for users, including their unique ID, platform,
timestamps for activity, trust score, and preference profiles. It also establishes
a relationship with the Session model.
"""

from uuid import uuid4
from app.db.base import Base
from datetime import datetime
from app.db.models.enums import PlatformEnum
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, Float, Enum, JSON, TIMESTAMP
from sqlalchemy.ext.mutable import MutableDict


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=True)
    phone_number = Column(String, unique=True, nullable=False)
    platform = Column(Enum(PlatformEnum))
    first_seen = Column(TIMESTAMP, default=datetime.utcnow)
    last_seen = Column(TIMESTAMP, default=datetime.utcnow)
    trust_score = Column(Float, default=0.5)
    genre_interest = Column(MutableDict.as_mutable(JSON), default=dict)
    platform_preference = Column(String, nullable=True)
    game_vibe = Column(MutableDict.as_mutable(JSON), default=dict)
    mood_history = Column(MutableDict.as_mutable(JSON), default={})
    sessions = relationship("Session", back_populates="user")

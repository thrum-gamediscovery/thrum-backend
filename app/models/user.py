"""
SQLAlchemy model for the User entity.

This model defines the database schema for users, including their unique ID, platform,
timestamps for activity, trust score, and preference profiles. It also establishes
a relationship with the Session model.
"""

from uuid import uuid4
from app.db.base import Base
from datetime import datetime
from app.models.enums import PlatformEnum
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, Float, Enum, JSON, TIMESTAMP


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    platform = Column(Enum(PlatformEnum))
    first_seen = Column(TIMESTAMP, default=datetime.utcnow)
    last_seen = Column(TIMESTAMP, default=datetime.utcnow)
    trust_score = Column(Float, default=0.5)
    genre_rejects = Column(JSON, default=dict)
    mood_profile = Column(JSON, default=dict)

    sessions = relationship("Session", back_populates="user")

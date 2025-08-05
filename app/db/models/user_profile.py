"""
SQLAlchemy model for the User entity.

This model defines the database schema for users, including their unique ID, platform,
timestamps for activity, trust score, and preference profiles. It also establishes
a relationship with the Session model.
"""

from uuid import uuid4
from app.db.base import Base
from app.db.models.enums import PlatformEnum
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, Enum, JSON, Boolean, Integer, ARRAY, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.mutable import MutableDict


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)  
    name = Column(String, nullable=True)
    phone_number = Column(String, unique=True, nullable=False)
    platform = Column(Enum(PlatformEnum))
    genre_prefs = Column(MutableDict.as_mutable(JSON), default=dict)
    platform_prefs = Column(MutableDict.as_mutable(JSON), default=dict)
    # Optional: user’s region (e.g., "UK", "US") — helps with region-based recommendations
    region = Column(String, nullable=True)
    # Optional: user’s timezone (e.g., "Europe/London") — helps with sending timely recs
    timezone = Column(String, nullable=True)
    # Optional: age range (e.g., "18-25") — only used for age-restricted content
    age_range = Column(String, nullable=True)
    # List of game IDs or titles the user has liked
    likes = Column(MutableDict.as_mutable(JSON), default=dict)
    # List of game IDs, titles, or genres the user has disliked or rejected
    dislikes = Column(MutableDict.as_mutable(JSON), default=dict)
    # Inferred mood tags based on conversation (e.g., ["relaxed", "playful"])
    mood_tags = Column(MutableDict.as_mutable(JSON), default=dict)
    # Tags to avoid in future recs (e.g., ["realistic FPS", "horror"])
    reject_tags = Column(MutableDict.as_mutable(JSON), default=dict)
    # Whether user prefers games with story (True/False)
    story_pref = Column(Boolean, nullable=True)
    # When the user usually plays (e.g., "evenings", "weekends")
    playtime = Column(String, nullable=True)
    favourite_games = Column(ARRAY(String), nullable=True)
    # Timestamp dictionary — tracks when each field was last updated
    # Example: {"platform": "2025-06-23T17:35", "genre_prefs": "2025-06-21T09:20"}
    last_updated = Column(MutableDict.as_mutable(JSON), default={})
    silence_count = Column(Integer, default=0) 

    awaiting_reply = Column(Boolean, default=False)
    last_thrum_timestamp = Column(DateTime, nullable=True)

    sessions = relationship("Session", back_populates="user")
    game_recommendation = relationship("GameRecommendation", back_populates="users")

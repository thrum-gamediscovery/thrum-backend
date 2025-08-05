from uuid import uuid4
from app.db.base import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableDict

class GameRecommendation(Base):
    __tablename__ = 'game_recommendations'

    game_rec_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)  
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.session_id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.user_id"))
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.game_id"), index=True)
    platform = Column(String, nullable=True)
    genre = Column(ARRAY(String), nullable=True)
    tone = Column(String, nullable=True)
    keywords = Column(MutableDict.as_mutable(JSON), default=dict)  # Keywords for the game
    mood_tag = Column(String, nullable=True)
    accepted = Column(Boolean, default=None)  # True = liked, False = rejected, None = not answered yet
    reason = Column(String, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="game_recommendations")
    users = relationship("UserProfile", back_populates="game_recommendation")
    game = relationship("Game", back_populates="recommendations")
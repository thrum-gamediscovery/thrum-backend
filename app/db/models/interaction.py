"""
SQLAlchemy model for logging messages within sessions.

This model captures details about each message, including its sender, content,
associated mood and tone tags, and the type of response it represents.
It maintains a relationship with the Session model.
"""

from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Text, Enum, ForeignKey, TIMESTAMP, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from app.db.base import Base
from app.db.models.enums import SenderEnum, ResponseTypeEnum, SessionTypeEnum

class Interaction(Base):
    __tablename__ = "interactions"

    interaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4) 
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.session_id"))
    sender = Column(Enum(SenderEnum))
    content = Column(Text)

    mood_tag = Column(String, nullable=True)
    tone_tag = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    response_type = Column(Enum(ResponseTypeEnum), nullable=True)

    session_type = Column(Enum(SessionTypeEnum), nullable=True)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.game_id"), nullable=True)
    bot_response_metadata = Column(MutableDict.as_mutable(JSON), default=dict)

    timestamp = Column(TIMESTAMP, default=datetime.utcnow)

    session = relationship("Session", back_populates="interactions")
    game = relationship("Game", back_populates="interactions")
    
    classification = Column(JSON, nullable=True)


# app/db/models/game.py
"""
SQLAlchemy model for storing game data used in AI recommendations.
This model caches metadata and vector embeddings of games fetched from a third-party API.
Each game's name, description, genre, and tags are stored alongside its MiniLM-based vector embedding.
These embeddings enable efficient similarity search using pgvector to power personalized game recommendations.
"""

from uuid import uuid4
from sqlalchemy import Column, String, Text, JSON, ARRAY, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.base import Base

# Game Table
class Game(Base):
    __tablename__ = "games"

    game_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4) 
    title = Column(String, nullable=False)
    description = Column(Text)
    genre = Column(ARRAY(String))
    game_vibes = Column(ARRAY(String))
    mechanics = Column(String)
    visual_style = Column(String)
    age_rating = Column(String, nullable=True)
    region = Column(String, nullable=True)  # e.g., "US", "UK"
    has_story = Column(Boolean, default=False)  # Flag if game is story-driven
    emotional_fit = Column(String)
    mood_tags = Column(JSON)
    game_embedding = Column(Vector(384))
    mood_embedding = Column(Vector(384))

    interactions = relationship("Interaction", back_populates="game")
    platforms = relationship("GamePlatform", back_populates="game")
    recommendations = relationship("GameRecommendation", back_populates="game")
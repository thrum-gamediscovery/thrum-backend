# app/db/models/game.py
"""
SQLAlchemy model for storing game data used in AI recommendations.
This model caches metadata and vector embeddings of games fetched from a third-party API.
Each game's name, description, genre, and tags are stored alongside its MiniLM-based vector embedding.
These embeddings enable efficient similarity search using pgvector to power personalized game recommendations.
"""

from uuid import uuid4
from sqlalchemy import Column, String, Text, JSON, ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.base import Base

# Game Table
class Game(Base):
    __tablename__ = "games"

    game_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    title = Column(String, nullable=False)
    description = Column(Text)
    genre = Column(ARRAY(String))
    game_vibes = Column(ARRAY(String))
    mechanics = Column(String)
    visual_style = Column(String)
    emotional_fit = Column(String)
    mood_tags = Column(JSON)
    game_embedding = Column(Vector(384))
    mood_embedding = Column(Vector(384))

    interactions = relationship("Interaction", back_populates="game")
    platforms = relationship("GamePlatform", back_populates="game")
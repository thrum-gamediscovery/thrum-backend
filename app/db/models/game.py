"""
SQLAlchemy model for storing game data used in AI recommendations.

This model caches metadata and vector embeddings of games fetched from a third-party API.
Each game's name, description, genre, and tags are stored alongside its MiniLM-based vector embedding.
These embeddings enable efficient similarity search using pgvector to power personalized game recommendations.
"""


from uuid import uuid4
from sqlalchemy import Column, String, Text, JSON
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class Game(Base):
    __tablename__ = "games"

    game_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    title = Column(String, nullable=False)
    description = Column(Text)
    genre = Column(String)
    platform = Column(String)
    visual_style = Column(String)
    mechanics = Column(String)
    emotional_fit = Column(String)  # e.g., chill, intense
    mood_tags = Column(JSON)  # e.g., {"cluster": "cozy", "vibe": "low_challenge"}
    embedding = Column(Vector(384))
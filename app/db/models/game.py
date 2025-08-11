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
    description = Column(Text, nullable=True)
    genre = Column(ARRAY(String), nullable=True, default=[])
    game_vibes = Column(ARRAY(String), nullable=True, default=[])
    complexity = Column(ARRAY(String), nullable=True, default=[])
    graphical_visual_style = Column(ARRAY(String), nullable=True, default=[]) # graphical_visual_style
    age_rating = Column(String, nullable=True)
    region = Column(String, nullable=True)  # e.g., "US", "UK"
    has_story = Column(Boolean, default=False)  # Flag if game is story-driven
    emotional_fit = Column(String, nullable=True)
    mood_tag = Column(ARRAY(String), default=[])
    gameplay_embedding = Column(Vector(768))
    preference_embedding = Column(Vector(768))
    
    alternative_titles = Column(ARRAY(String), nullable=True, default=[])  # List of alternative game titles
    release_date = Column(String, nullable=True)  # Release date (e.g., "05-02-2013")
    editions = Column(String, nullable=True)  # Game edition (e.g., "Standard")
    subgenres = Column(ARRAY(String), nullable=True, default=[])  # Game subgenres
    story_setting_realism = Column(JSON, nullable=True, default={})  # Story setting and realism (e.g., realistic, sci-fi)
    main_perspective = Column(ARRAY(String), nullable=True, default=[])  # Main perspective (e.g., first-person)
    keywords = Column(ARRAY(String), nullable=True, default=[])  # Keywords related to the game
    gameplay_elements = Column(ARRAY(String), nullable=True, default=[])  # Gameplay elements (e.g., combat, exploration)
    advancement = Column(ARRAY(String), nullable=True, default=[])  # Progression type (e.g., linear, skill tree)
    linearity = Column(ARRAY(String), nullable=True, default=[])  # Level of linearity (e.g., linear, non-linear)
    themes = Column(ARRAY(String), nullable=True, default=[])  # Themes the game covers (e.g., survival, fantasy)
    replay_value = Column(ARRAY(String), nullable=True, default=[])  # Replayability value (e.g., high, medium)
    developers = Column(ARRAY(String), nullable=True, default=[])  # List of developers
    publishers = Column(ARRAY(String), nullable=True, default=[])  # List of publishers
    discord_id = Column(ARRAY(String), nullable=True, default=[])  # Discord community or server ID
    igdb_id = Column(ARRAY(String), nullable=True, default=[])  # IGDB ID for external game database reference
    sku = Column(String, nullable=True)  # Stock Keeping Unit
    
    key_features = Column(ARRAY(String), nullable=True, default=[])  # key_features related to the game

    interactions = relationship("Interaction", back_populates="game")
    platforms = relationship("GamePlatform", back_populates="game")
    recommendations = relationship("GameRecommendation", back_populates="game")

    ratings = Column(JSON, nullable=True, default={})

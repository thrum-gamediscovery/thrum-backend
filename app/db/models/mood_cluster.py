# app/db/models/mood_cluster.py

from sqlalchemy import ARRAY, Column, String
from pgvector.sqlalchemy import Vector
from app.db.base import Base

class MoodCluster(Base):
    __tablename__ = "mood_cluster"

    mood = Column(String, primary_key=True, index=True)
    game_tags = Column(ARRAY(String))  # fix: ARRAY needs type
    game_vibe = Column(ARRAY(String))  # fix: ARRAY needs type
    embedding = Column(Vector(384))
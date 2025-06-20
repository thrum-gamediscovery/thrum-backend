# app/db/models/game_platforms.py

from uuid import uuid4
from sqlalchemy import Column, String, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base

# GamePlatform Table
class GamePlatform(Base):
    __tablename__ = "game_platforms"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    game_id = Column(String, ForeignKey("games.game_id"), nullable=False)
    platform = Column(String, nullable=False)

    game = relationship("Game", back_populates="platforms")
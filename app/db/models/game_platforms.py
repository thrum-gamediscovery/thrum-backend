# app/db/models/game_platforms.py

from uuid import uuid4
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

# GamePlatform Table
class GamePlatform(Base):
    __tablename__ = "game_platforms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)  
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.game_id"), nullable=False)
    platform = Column(String, nullable=False)
    link = Column(String, nullable=True)

    game = relationship("Game", back_populates="platforms")
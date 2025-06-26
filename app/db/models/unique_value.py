from uuid import uuid4
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.db.base import Base

class UniqueValue(Base):
    __tablename__ = "unique_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    field = Column(String, nullable=False, unique=True)  # genre, platform, game_vibes
    unique_values = Column(ARRAY(String), nullable=False)  # Stored as actual array of strings

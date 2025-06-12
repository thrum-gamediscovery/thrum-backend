"""
Provides a dependency for FastAPI routes to get a DB session.

Ensures session is opened and closed cleanly per request.
"""

from .user import User
from .game_metadata import GameMetadata
from .interaction_history import InteractionHistory
from .session import Session

# Dependency that creates and closes a database session per request
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
Provides a dependency for FastAPI routes to get a DB session.

Ensures session is opened and closed cleanly per request.
"""

from app.db.session import SessionLocal
from typing import Generator

# Dependency that creates and closes a database session per request
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

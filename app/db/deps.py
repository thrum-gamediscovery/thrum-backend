"""
Provides a dependency for FastAPI routes to get a DB session.

Ensures session is opened and closed cleanly per request.
"""


from typing import Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

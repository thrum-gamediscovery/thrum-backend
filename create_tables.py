"""
create_tables.py

Run this script once to create all database tables defined in SQLAlchemy models.
This uses the Base.metadata.create_all method with the configured engine.

You should run this after setting up your database URL in `.env` and creating models.
"""

from app.db.base import Base
from app.db.session import engine

# Ensure all models are imported before calling create_all
from app.db import models

def init_db():
    print("📦 Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Done.")

if __name__ == "__main__":
    init_db()
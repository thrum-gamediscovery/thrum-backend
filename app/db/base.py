"""
Defines the SQLAlchemy declarative base class.

All ORM models will inherit from this base.
"""

# app/db/base.py
from sqlalchemy.orm import declarative_base

Base = declarative_base()

"""
Handles user-related endpoints: create user, ping, etc.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.deps import get_db

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "pong"}

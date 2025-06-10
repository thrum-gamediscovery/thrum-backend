"""
Handles user-related endpoints: create user, ping, etc.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.models import schemas
from app.db import models

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "pong"}

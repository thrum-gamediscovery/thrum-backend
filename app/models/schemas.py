"""
Defines Pydantic models for validation of requests and responses.

Includes schemas for User, GameMetadata, and Interaction creation/output.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    name: Optional[str]
    platform: Optional[str]
    genres: Optional[List[str]]

class UserCreate(UserBase):
    pass

class UserOut(UserBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

class GameMetadataOut(BaseModel):
    id: int
    title: str
    genre: Optional[str]
    platform: Optional[str]
    emotional_fit: Optional[str]
    mood_tags: Optional[List[str]]
    class Config:
        orm_mode = True

class InteractionCreate(BaseModel):
    user_id: int
    mood_input: str
    response_text: Optional[str]
    confidence_score: Optional[str]
    sentiment: Optional[str]

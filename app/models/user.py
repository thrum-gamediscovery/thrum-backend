from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    name: Optional[str]
    platform: Optional[str]
    genres: Optional[List[str]]

class UserOut(UserCreate):
    user_id: str
    trust_score: Optional[float]
    created_at: datetime

    class Config:
        orm_mode = True
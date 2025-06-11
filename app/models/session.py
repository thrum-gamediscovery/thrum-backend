from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SessionBase(BaseModel):
    entry_mood: Optional[str]
    exit_mood: Optional[str]
    recommended_games: Optional[List[str]]
    feedback: Optional[str]

class SessionOut(SessionBase):
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]

    class Config:
        orm_mode = True
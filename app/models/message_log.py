from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MessageLogBase(BaseModel):
    sender: str
    message: str
    timestamp: Optional[datetime]

class MessageLogOut(MessageLogBase):
    id: int
    session_id: str

    class Config:
        orm_mode = True
from fastapi import APIRouter, Depends, Request, HTTPException,Header
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from app.db.deps import get_db
from app.db.models.enums import SenderEnum, ResponseTypeEnum
from app.db.models.interaction import Interaction
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    user_input: str

@router.post("/", tags=["Chat"])
def chat_with_thrum(request: Request, payload: ChatRequest, db: DBSession = Depends(get_db)):
    # Get session_id injected by session_middleware
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not initialized.")
    
    # Log user message
    user_msg = Interaction(
        session_id=session_id,
        sender=SenderEnum.User,
        content=payload.user_input,
    )
    
    bot_reply = "Hey.. how are you?"
    
    # Log bot reply
    bot_msg = Interaction(
        session_id=session_id,
        sender=SenderEnum.Thrum,
        content=bot_reply,
        response_type=ResponseTypeEnum.GameRec,
        confidence_score=0.92
    )
    
    try:
        db.add(user_msg)
        db.add(bot_msg)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="DB error: " + str(e))

    
    return {
        "reply": bot_reply,
        "session_id": session_id,
    }
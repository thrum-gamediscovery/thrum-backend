from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from datetime import datetime

# DB models and dependencies
from app.db.deps import get_db
from app.db.models.enums import SenderEnum, ResponseTypeEnum
from app.services.interactions import create_interaction
from app.db.models.interaction import Interaction
from app.db.models.session import Session
from app.services.tone_engine import detect_tone_cluster

router = APIRouter()

# Request body model for user input
class ChatRequest(BaseModel):
    user_input: str


# 🔒 Helper to get safe last item from list/array
def safe_last(arr):
    return arr[-1] if isinstance(arr, list) and arr else None


# 📩 User sends message to Thrum
@router.post("/user_chat", tags=["User_Chat"])
async def user_chat_with_thrum(
    request: Request,
    payload: ChatRequest,
    db: DBSession = Depends(get_db)
):
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not initialized.")
    
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    tone = await detect_tone_cluster(db, session, payload.user_input)

    interaction = create_interaction(
        session = session,
        session_id=session_id,
        sender=SenderEnum.User,
        content=payload.user_input,
        tone_tag=tone,
        session_type=getattr(session, "session_type", None),
        mood_tag=getattr(session, "exit_mood", None),
        bot_response_metadata={"phase": getattr(session, "phase", None)}
    )

    try:
        db.add(interaction)
        db.commit()
        print(f"✅ User message stored: {interaction.content} | tone = {tone}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="DB error: " + str(e))

    return session


# 🤖 Bot sends reply to user
@router.post("/bot_chat", tags=["Bot_Chat"])
async def bot_chat_with_thrum(
    request: Request,
    bot_reply: str,
    db: DBSession = Depends(get_db)
):
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not initialized.")
    
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    tone = await detect_tone_cluster(db, session, bot_reply)

    interaction = create_interaction(
        session=session,
        session_id=session_id,
        sender=SenderEnum.Thrum,
        content=bot_reply,
        mood_tag=getattr(session, "exit_mood", None),
        tone_tag=tone,
        confidence_score=0.92,
        game_id=getattr(session, "last_game_id", None),
        session_type=getattr(session, "session_type", None),
        bot_response_metadata={
            "phase": getattr(session, "phase", None),
            "platform": safe_last(getattr(session, "platform_preference", [])),
            "genre": safe_last(getattr(session, "genre", [])),
            "mood": getattr(session, "exit_mood", None)
        }
    )

    try:
        db.add(interaction)
        db.commit()
        print(f"✅ Bot reply stored: {interaction.content} | tone = {tone}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="DB error: " + str(e))

    return session

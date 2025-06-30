from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from datetime import datetime

# DB models and dependencies
from app.db.deps import get_db
from app.db.models.enums import SenderEnum, ResponseTypeEnum
from app.db.models.interaction import Interaction
from app.db.models.session import Session
from app.services.tone_engine import detect_tone_cluster

router = APIRouter()

# Request body model for user input
class ChatRequest(BaseModel):
    user_input: str

# 📩 User sends message to Thrum
@router.post("/user_chat", tags=["User_Chat"])
async def user_chat_with_thrum(
    request: Request,
    payload: ChatRequest,
    db: DBSession = Depends(get_db)
):
    # 🧠 Get session ID from middleware
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not initialized.")
    
    # 🔎 Fetch session object
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    # ⏰ Update session timestamp
    session.end_time = datetime.utcnow()
    
    # 🎯 Detect tone from user input
    tone = await detect_tone_cluster(db, session, payload.user_input)
    
    # 📝 Create new user interaction record
    user_msg = Interaction(
        session_id=session_id,
        sender=SenderEnum.User,
        content=payload.user_input,
        tone_tag=tone,
    )
    
    try:
        db.add(user_msg)
        db.commit()
        print(f"✅ User message stored: {user_msg.content} | tone = {tone}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="DB error: " + str(e))
    
    return session
# 🤖 Bot sends reply to user
@router.post("/bot_chat", tags=["Bot_Chat"])
async def bot_chat_with_thrum(request: Request, bot_reply: str, db: DBSession = Depends(get_db)):
    # 🔑 Get session_id from middleware
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not initialized.")
    
    # 📦 Fetch session from DB
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    # 🕓 Update session's end time
    session.end_time = datetime.utcnow()
    tone = await detect_tone_cluster(db, session, bot_reply)
    # 📝 Create interaction object for bot reply
    bot_msg = Interaction(
        session_id=session_id,
        sender=SenderEnum.Thrum,
        content=bot_reply,
        response_type=ResponseTypeEnum.GameRec,  # 📌 default response type
        confidence_score=0.92,                   # 📊 default confidence
        tone_tag=tone,
    )
    
    try:
        # 💾 Save interaction and update session
        db.add(bot_msg)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="DB error: " + str(e))
    
    return session
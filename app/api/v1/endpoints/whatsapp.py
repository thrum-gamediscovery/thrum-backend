# 📄 File: app/api/v1/endpoints/whatsapp.py (updated to ask mood first, then continue based on mood)

from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.models.user_profile import UserProfile
from app.db.deps import get_db
from app.db.models.enums import PlatformEnum
from app.api.v1.endpoints.chat import user_chat_with_thrum, bot_chat_with_thrum, ChatRequest
from app.services.session_manager import update_or_create_session
from app.services.create_reply import generate_thrum_reply

router = APIRouter()

# 🔁 Handles session update and sends the bot reply to chat processor
async def user_chat(request, db, user, Body):
    session = update_or_create_session(db, user)
    request.scope["headers"] = list(request.scope["headers"]) + [
        (b"x-user-id", str(user.user_id).encode())
    ]
    request.state.session_id = session.session_id
    payload = ChatRequest(user_input=Body)
    session = await user_chat_with_thrum(request=request, payload=payload, db=db)
    return session

async def bot_reply(request, db, user, reply):
    session = update_or_create_session(db, user)
    request.scope["headers"] = list(request.scope["headers"]) + [
        (b"x-user-id", str(user.user_id).encode())
    ]
    request.state.session_id = session.session_id
    session = await bot_chat_with_thrum(request=request, bot_reply=reply, db=db)

# 📲 Main WhatsApp webhook endpoint to process user messages
@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(request: Request, From: str = Form(...), Body: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.phone_number == From).first()
    user_input = Body

    # ✅ Step 1: Create new user if not found in DB
    if not user:
        user = UserProfile(
            phone_number=From,
            platform=PlatformEnum.WhatsApp
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    session = await user_chat(request=request, db=db, user=user, Body=Body)

    reply = await generate_thrum_reply(user=user, session=session, user_input=Body, db=db)

    # 📤 Send response and maintain session state
    await bot_reply(request=request, db=db, user=user, reply=reply)
    
    # 📩 Return final reply to WhatsApp
    return reply

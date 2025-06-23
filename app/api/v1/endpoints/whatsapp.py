# 📄 File: app/api/v1/endpoints/whatsapp.py (updated to ask mood first, then continue based on mood)

from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.models.user import User
from app.db.deps import get_db
from app.db.models.enums import PlatformEnum
from app.api.v1.endpoints.chat import chat_with_thrum, ChatRequest
from app.services.session_manager import update_or_create_session
from app.services.input_classifier import classify_user_input, update_user_from_classification
from app.services.create_reply import generate_thrum_reply

router = APIRouter()

# 🔁 Handles session update and sends the bot reply to chat processor
async def handle_session_and_chat(request, db, user, Body, reply):
    session = update_or_create_session(db, user)
    request.scope["headers"] = list(request.scope["headers"]) + [
        (b"x-user-id", user.user_id.encode())
    ]
    request.state.session_id = session.session_id
    payload = ChatRequest(user_input=Body)
    chat_with_thrum(request=request, payload=payload, bot_reply=reply, db=db)

# 📲 Main WhatsApp webhook endpoint to process user messages
@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(request: Request, From: str = Form(...), Body: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone_number == From).first()
    user_input = Body

    # ✅ Step 1: Create new user if not found in DB
    if not user:
        user = User(
            phone_number=From,
            name="Anonymous",
            platform=PlatformEnum.WhatsApp,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            genre_interest={},
            mood_history={},
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
    # 🧠 Classify input to detect mood, vibe, genre, platform
    classification = classify_user_input(user_input)

    # 🔄 Update user profile based on classification result
    if isinstance(classification, dict):
        update_user_from_classification(db,user,user_input,classification)
        db.commit()
    else:
        print(classification)

    # 💬 Generate response (question or game suggestion)
    reply = generate_thrum_reply(db=db,user=user,user_input=user_input)

    # 📤 Send response and maintain session state
    await handle_session_and_chat(request=request, db=db, user=user, Body=Body, reply=reply)
    
    # 📩 Return final reply to WhatsApp
    return reply

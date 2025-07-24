# 📄 File: app/api/v1/endpoints/whatsapp.py (updated to ask mood first, then continue based on mood)
import asyncio
from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hashlib
from app.db.models.user_profile import UserProfile
from app.db.deps import get_db
from app.db.models.enums import PlatformEnum
from app.api.v1.endpoints.chat import user_chat_with_thrum, bot_chat_with_thrum, ChatRequest
from app.services.session_manager import update_or_create_session, is_session_idle
from app.services.create_reply import generate_thrum_reply
from app.utils.region_utils import infer_region_from_phone, get_timezone_from_region
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply


router = APIRouter()

# In-memory cache for recent messages (phone_number -> {message_hash: timestamp})
recent_messages = {}

# Track pending responses to cancel outdated ones
pending_responses = {}  # phone_number -> latest_message_timestamp

# 🔁 Handles session update and sends the bot reply to chat processor
async def user_chat(request, db, user, Body):
    session = await update_or_create_session(db, user)
    request.scope["headers"] = list(request.scope["headers"]) + [
        (b"x-user-id", str(user.user_id).encode())
    ]
    request.state.session_id = session.session_id
    payload = ChatRequest(user_input=Body)
    session, intrection = await user_chat_with_thrum(request=request, payload=payload, db=db)
    return session, intrection

async def bot_reply(request, db, user, reply):
    session = await update_or_create_session(db, user)
    request.scope["headers"] = list(request.scope["headers"]) + [
        (b"x-user-id", str(user.user_id).encode())
    ]
    request.state.session_id = session.session_id
    session = await bot_chat_with_thrum(request=request, bot_reply=reply, db=db)

# 📲 Main WhatsApp webhook endpoint to process user messages
@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(request: Request, From: str = Form(...), Body: str = Form(...), db: Session = Depends(get_db)):
    # Create message hash for deduplication
    message_hash = hashlib.md5(f"{From}:{Body}".encode()).hexdigest()
    now = datetime.utcnow()
    
    # Check for duplicate message within last 10 seconds
    if From in recent_messages:
        if message_hash in recent_messages[From]:
            if now - recent_messages[From][message_hash] < timedelta(seconds=10):
                return  # Ignore duplicate - no response
        # Clean old messages (older than 30 seconds)
        recent_messages[From] = {h: t for h, t in recent_messages[From].items() 
                               if now - t < timedelta(seconds=30)}
    else:
        recent_messages[From] = {}
    
    # Store current message
    recent_messages[From][message_hash] = now
    
    # Track this as the latest message for this user
    pending_responses[From] = now
    
    user = db.query(UserProfile).filter(UserProfile.phone_number == From).first()
    user_input = Body
    
    # ✅ Step 1: Create new user if not found in DB
    if not user:
        region = await infer_region_from_phone(From)
        timezone_str = await get_timezone_from_region(region)
        user = UserProfile(
            phone_number=From,
            region=region,
            timezone=timezone_str,
            platform=PlatformEnum.WhatsApp
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    session, intrection = await user_chat(request=request, db=db, user=user, Body=user_input)
    session.followup_triggered= False
    session.intent_override_triggered = False
    if session.awaiting_reply:
        now = datetime.utcnow()
        if session.last_thrum_timestamp and now - session.last_thrum_timestamp < timedelta(seconds=180):
            if session.user.silence_count <= 3: #  User replied promptly
                session.user.silence_count = 0
        # Always stop waiting after any reply
        session.awaiting_reply = False
    db.commit()

    response_prompt = await generate_thrum_reply(db=db,user=user, session=session, user_input=user_input, intrection = intrection)
    reply = await format_reply(session=session,user_input=user_input, user_prompt=response_prompt)
    if len(session.interactions) == 0 or is_session_idle(session):
        await asyncio.sleep(5)

    # Check if user sent additional messages while processing
    if From in pending_responses and pending_responses[From] > now:
        return  # Skip sending response - user sent newer message
    
    # 📩 Return final reply to WhatsApp
    await send_whatsapp_message(
        phone_number=user.phone_number,
        message=reply,
        sent_from_thrum=False
    )
    # 📤 Send response and maintain session state
    await bot_reply(request=request, db=db, user=user, reply=reply)
    session.awaiting_reply = True
    session.last_thrum_timestamp = datetime.utcnow()
    db.commit()
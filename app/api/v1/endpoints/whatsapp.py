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
from app.services.session_manager import update_or_create_session, is_session_idle, update_user_pacing
from app.services.create_reply import generate_thrum_reply
from app.utils.region_utils import infer_region_from_phone, get_timezone_from_region
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply


router = APIRouter()

# In-memory cache for recent messages (phone_number -> {message_hash: timestamp})
recent_messages = {}

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
user_message_buffer = {}     # phone_number -> [msg1, msg2, ...]
is_reply_in_progress = {} 
# 📲 Main WhatsApp webhook endpoint to process user messages
@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db)
):
    # ---------- 1. Message Deduplication ----------
    message_hash = hashlib.md5(f"{From}:{Body}".encode()).hexdigest()
    now = datetime.utcnow()
    if From in recent_messages:
        if message_hash in recent_messages[From]:
            if now - recent_messages[From][message_hash] < timedelta(seconds=10):
                return  # Ignore duplicate - no response
        # Clean old hashes
        recent_messages[From] = {h: t for h, t in recent_messages[From].items()
                                 if now - t < timedelta(seconds=30)}
    else:
        recent_messages[From] = {}
    recent_messages[From][message_hash] = now

    # ---------- 2. Get or Create User ----------
    user = db.query(UserProfile).filter(UserProfile.phone_number == From).first()
    if not user:
        region = await infer_region_from_phone(From)
        timezone_str = await get_timezone_from_region(From)
        user = UserProfile(
            phone_number=From,
            region=region,
            timezone=timezone_str,
            platform=PlatformEnum.WhatsApp
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # ---------- 3. Buffer logic: If reply in progress, buffer message ----------
    if is_reply_in_progress.get(From, False):
        user_message_buffer.setdefault(From, []).append(Body)
        return  # Do not process, just buffer

    # ---------- 4. Start reply-in-progress state ----------
    is_reply_in_progress[From] = True

    # ---------- 5. Join buffered messages (if any) + this one ----------
    all_msgs = user_message_buffer.pop(From, []) + [Body]
    user_input = " ".join(all_msgs).strip()

    # ---------- 6. Load/Create Session ----------
    session = await update_or_create_session(db, user)
    request.scope["headers"] = list(request.scope["headers"]) + [
        (b"x-user-id", str(user.user_id).encode())
    ]
    request.state.session_id = session.session_id

    # ---------- 7. Process User Chat ----------
    payload = ChatRequest(user_input=user_input)
    session, intrection = await user_chat_with_thrum(request=request, payload=payload, db=db)
    
    # ---------- 7.1. Update User Pacing ----------
    update_user_pacing(session)
    db.commit()
    session.followup_triggered = False
    session.intent_override_triggered = False
    if session.awaiting_reply:
        now = datetime.utcnow()
        if session.last_thrum_timestamp and now - session.last_thrum_timestamp < timedelta(seconds=180):
            if session.user.silence_count <= 3:
                session.user.silence_count = 0
        session.awaiting_reply = False
    db.commit()

    # ---------- 8. Generate and Send Bot Reply ----------
    response_prompt = await generate_thrum_reply(
        db=db, user=user, session=session, user_input=user_input, intrection=intrection
    )
    print('response_prompt........................................', response_prompt)
    reply = await format_reply(db=db, session=session, user_input=user_input, user_prompt=response_prompt)
    if len(session.interactions) == 0 or is_session_idle(session):
        await asyncio.sleep(5)  # Optional: pause if new session

    await send_whatsapp_message(
        phone_number=user.phone_number,
        message=reply,
        sent_from_thrum=False
    )

    # ---------- 9. Update Bot Chat State ----------
    # (Register bot reply in chat memory)
    session = await bot_chat_with_thrum(request=request, bot_reply=reply,db=db)
    session.awaiting_reply = True
    session.last_thrum_timestamp = datetime.utcnow()
    db.commit()

    # ---------- 10. Clear reply-in-progress flag ----------
    is_reply_in_progress[From] = False

    # ---------- 11. After reply: If user sent MORE messages while bot was replying, process them immediately ----------
    # (Handle rapid multi-message scenarios: join all, process recursively)
    if From in user_message_buffer and user_message_buffer[From]:
        # Recursively process all new buffered messages as one input
        # (prevents missed messages if user types even more before receiving bot reply)
        all_msgs = user_message_buffer.pop(From, [])
        joined_input = " ".join(all_msgs).strip()
        # Recurse by calling webhook handler directly (safe for simple flows)
        # Or you can schedule as a background task if needed for concurrency
        await whatsapp_webhook(
            request=request,
            From=From,
            Body=joined_input,
            db=db
        )

# Fast WhatsApp webhook with minimal overhead
import asyncio
from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.models.user_profile import UserProfile
from app.db.deps import get_db
from app.db.models.enums import PlatformEnum
from app.utils.region_utils import infer_region_from_phone, get_timezone_from_region
from app.utils.whatsapp import send_whatsapp_message
from app.services.session_manager import update_or_create_session
from app.services.dynamic_response_engine import generate_dynamic_response

router = APIRouter()

def generate_static_response(user_input: str) -> str:
    """Generate static responses based on user input"""
    user_input_lower = user_input.lower().strip()
    
    if "hello" in user_input_lower or "hi" in user_input_lower:
        return "Hey there! 😊 What kind of game are you in the mood for today?"
    elif "game" in user_input_lower:
        return "I'd recommend trying Stardew Valley for a chill vibe or Hades for some action! 🎮"
    elif "mood" in user_input_lower:
        return "Tell me more about how you're feeling - relaxed, excited, or maybe something else? 🌈"
    elif "thanks" in user_input_lower or "thank" in user_input_lower:
        return "You're welcome! Happy gaming! 🎆"
    else:
        return "I'm Thrum, your game buddy! Tell me your mood and I'll suggest the perfect game for you! 🎲"


@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(request: Request, From: str = Form(...), Body: str = Form(...), db: Session = Depends(get_db)):
    # [START-POINT] User input received from WhatsApp
    user_input = Body
    print(f"📥 [START-POINT] User input received: {user_input} from {From}")
    
    # Fast user lookup/creation
    user = db.query(UserProfile).filter(UserProfile.phone_number == From).first()
    
    if not user:
        # Fast new user creation
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
    
    # Fast session update
    session = await update_or_create_session(db, user)
    
    # Generate dynamic response using existing db session
    reply = await generate_dynamic_response(user=user, session=session, user_input=user_input, db=db)
    
    # Update session state quickly
    session.awaiting_reply = False
    session.last_thrum_timestamp = datetime.utcnow()
    db.commit()
    
    # [END-POINT] Sending response back to WhatsApp
    print(f"📤 [END-POINT] Sending response: {reply}")
    print(f"📞 To phone: {user.phone_number}")
    
    try:
        await send_whatsapp_message(
            phone_number=user.phone_number,
            message=reply,
            sent_from_thrum=False
        )
        print(f"✅ Message sent successfully")
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message: {e}")
    
    return "OK"

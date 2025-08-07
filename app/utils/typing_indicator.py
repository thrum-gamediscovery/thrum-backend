import asyncio
import os
import hashlib
from openai import AsyncOpenAI
from app.db.models.enums import PhaseEnum, SenderEnum
from app.utils.whatsapp import send_whatsapp_message

client = AsyncOpenAI()
model = os.getenv("GPT_MODEL")

GOODBYE_KEYWORDS = ["bye", "goodbye", "see you", "exit", "later", "peace"]

def get_message_hash(user_input: str) -> str:
    """Generate hash for message to prevent filler repetition"""
    return hashlib.md5(user_input.lower().encode()).hexdigest()

def get_reply_context(session) -> str:
    """Determine current reply context based on session phase and state"""
    phase_context = {
        PhaseEnum.INTRO: "greeting",
        PhaseEnum.DISCOVERY: "mood_exploration", 
        PhaseEnum.CONFIRMATION: "preference_confirmation",
        PhaseEnum.DELIVERY: "game_recommendation",
        PhaseEnum.FOLLOWUP: "feedback_collection",
        PhaseEnum.ENDING: "farewell"
    }
    return phase_context.get(session.phase, "general_chat")

async def send_typing_indicator(phone_number: str, session, delay: float = 5.0):
    """Send Gen-AI filler after delay if processing takes too long"""
    await asyncio.sleep(delay)

    # Cancel if reply is already ready
    if session.meta_data and session.meta_data.get("reply_ready", False):
        return

    # Get last user message
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""

    # Cancel if user is leaving
    if (session.phase == PhaseEnum.ENDING or 
        any(k in user_input.lower() for k in GOODBYE_KEYWORDS)):
        return

    # Prevent repetition for same message
    current_hash = get_message_hash(user_input)
    last_filler_hash = session.meta_data.get("last_filler_hash") if session.meta_data else None
    if last_filler_hash == current_hash:
        return

    # Get context
    mood = session.entry_mood or "neutral"
    reply_context = get_reply_context(session)
    user_tone = session.meta_data.get("tone", "neutral") if session.meta_data else "neutral"

    # Get past fallbacks to avoid repetition
    used_fallbacks = session.meta_data.get("used_fallbacks", []) if session.meta_data else []

    # Construct the dynamic filler prompt
    filler_prompt = f"""You are Thrum, a game discovery buddy who chats like a real friend.

The user just said: "{user_input}"
They are in a {mood} mood with {user_tone} energy.
You're about to respond in this context: {reply_context}
The main response is still generating.

Avoid repeating any of these past lines: {used_fallbacks}

Write a SHORT, playful filler line to keep the vibe alive while you think.
It should:
- Match their {user_tone} tone
- Hint something good is coming
- Feel like a real friend texting
- Be under 10 words
- Never sound robotic

Just write the message, no explanation."""
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": filler_prompt}],
            temperature=0.8,
            max_tokens=25
        )
        message = response.choices[0].message.content.strip().strip('"')
        
        # Init meta_data if not present
        if not session.meta_data:
            session.meta_data = {}

        # Update filler tracking
        session.meta_data["last_filler_hash"] = current_hash
        session.meta_data.setdefault("used_fallbacks", []).append(message)

        # Optional: limit memory size
        if len(session.meta_data["used_fallbacks"]) > 15:
            session.meta_data["used_fallbacks"] = session.meta_data["used_fallbacks"][-10:]

    except Exception:
        message = "Hold tight a sec…"

    await send_whatsapp_message(phone_number, message, sent_from_thrum=False)
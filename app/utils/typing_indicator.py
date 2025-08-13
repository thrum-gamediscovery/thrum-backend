import asyncio
import os
import hashlib
from openai import AsyncOpenAI
from app.api.v1.endpoints import session
from app.db.models.enums import PhaseEnum, SenderEnum
from app.utils.whatsapp import send_whatsapp_message

client = AsyncOpenAI()
model = os.getenv("GPT_MODEL")

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
    """Send contextual filler that acknowledges user input and maintains friend tone"""
    await asyncio.sleep(delay)

    # Cancel if reply is ready
    if session.meta_data and session.meta_data.get("reply_ready", False):
        return

    # Get last user message
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content.strip() if user_interactions else ""
    if not user_input:
        return

    # Prevent repetition for same input
    current_hash = get_message_hash(user_input)
    recent_filler_hashes = session.meta_data.get("recent_filler_hashes", [])
    if current_hash in recent_filler_hashes:
        return

    # Conversation + tone context
    mood = session.entry_mood or "neutral"
    user_tone = session.meta_data.get("tone", "neutral")
    reply_context = get_reply_context(session)

    # Get last few turns of conversation (user + bot), newest last
    recent_interactions_ordered = sorted(session.interactions, key=lambda i: i.timestamp)
    recent_context_pairs = []
    for msg in recent_interactions_ordered[-6:]:  # last 6 exchanges
        role = "You" if msg.sender == SenderEnum.User else "Thrum"
        recent_context_pairs.append(f"{role}: {msg.content.strip()}")

    conversation_context = " | ".join(recent_context_pairs)

    # Avoid repeating recent fillers
    recent_fillers = session.meta_data.get("recent_fillers", []) if session.meta_data else []
    avoid_phrases = ", ".join(recent_fillers[-8:]) if recent_fillers else "none"

    # Track filler type to avoid repeating classification prompts
    last_filler_type = session.meta_data.get("last_filler_type", None)

    filler_prompt = f"""
You are Thrum, a game discovery buddy chatting like a real friend.
The main reply is still loading — you’re sending a quick, *personal*, under-10-word reaction.

Rules:
1. React naturally to the user's last message: "{user_input}"
2. If possible, tease that you have something cool or surprising for them.
3. Keep tone matching their mood ({mood}) and energy ({user_tone}).
4. Avoid repeating the same kind of question as last time: {last_filler_type or "none"}.
5. No AI talk, no onboarding.
6. Keep it casual, peer-like, and human — never formal.
7. Under 10 words.
8. Optionally end with a short hook or playful nudge.

Current phase: {reply_context}

Recent conversation so far: "{conversation_context}"
Avoid these phrases: {avoid_phrases}

Write ONLY the filler line.
"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": filler_prompt}],
            temperature=0.85,
            max_tokens=30
        )
        message = response.choices[0].message.content.strip().strip('"')

        # Skip if goodbye or ending phase
        if message.upper() == "SKIP" or session.phase == PhaseEnum.ENDING:
            return

        # Track recent fillers + hashes
        recent_fillers.append(message)
        session.meta_data["recent_fillers"] = recent_fillers[-16:]
        recent_filler_hashes.append(current_hash)
        session.meta_data["recent_filler_hashes"] = recent_filler_hashes[-10:]

        # Track filler type (basic heuristic: question vs statement)
        filler_type = "question" if message.endswith("?") else "statement"
        session.meta_data["last_filler_type"] = filler_type

    except Exception:
        message = "thinking..."
    
    # Store hash to prevent repetition (keep last 10)
    if not session.meta_data:
        session.meta_data = {}
    recent_hashes = session.meta_data.get("recent_filler_hashes", [])
    recent_hashes.append(current_hash)
    session.meta_data["recent_filler_hashes"] = recent_hashes[-10:]
    
    await send_whatsapp_message(phone_number, message, sent_from_thrum=False)
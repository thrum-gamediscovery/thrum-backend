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
    """Map session phase to descriptive context"""
    phase_context = {
        PhaseEnum.INTRO: "greeting",
        PhaseEnum.DISCOVERY: "mood_exploration",
        PhaseEnum.CONFIRMATION: "preference_confirmation",
        PhaseEnum.DELIVERY: "game_recommendation",
        PhaseEnum.FOLLOWUP: "feedback_collection",
        PhaseEnum.ENDING: "farewell"
    }
    return phase_context.get(session.phase, "general_chat")

async def send_typing_indicator(phone_number: str, session, delay: float = 2.0):
    """Send contextual, emotion-aware filler while main reply loads"""
    await asyncio.sleep(delay)

    # Cancel if reply already ready
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

    # Get conversation context
    mood = session.entry_mood or "neutral"
    user_tone = session.meta_data.get("tone", "neutral")
    reply_context = get_reply_context(session)

    # Get recent conversation for context
    recent_interactions_ordered = sorted(session.interactions, key=lambda i: i.timestamp)
    recent_context_pairs = []
    for msg in recent_interactions_ordered[-6:]:
        role = "You" if msg.sender == SenderEnum.User else "Thrum"
        recent_context_pairs.append(f"{role}: {msg.content.strip()}")
    conversation_context = " | ".join(recent_context_pairs)

    # Avoid repeating recent fillers
    recent_fillers = session.meta_data.get("recent_fillers", []) if session.meta_data else []
    avoid_phrases = ", ".join(recent_fillers[-8:]) if recent_fillers else "none"

    # Prompt to handle emotion + phase dynamically
    filler_prompt = f"""
You are Thrum, a friendly game discovery buddy chatting like a real friend.
The main reply is still loading — you’re sending a quick, personal filler reaction.

Analyze the LAST user message:
"{user_input}"

1. Internally decide the sentiment/emotion (you don’t output it).
2. Choose filler type ONLY from: hype, empathy, or light comment.
3. ❌ Absolutely no questions or question marks — fillers are not for starting new topics.
4. Match the tone and energy of the user, and keep it human and casual.
5. Absolutely under 10 words.
6. Optionally end with a short playful nudge (but not a question).
7. Avoid these phrases: {avoid_phrases}.
8. Never hint at the main answer unless phase is 'game_recommendation'.
9. Keep emotional flow — if user is sad/serious, DO NOT joke.

Recent conversation: "{conversation_context}"

Write ONLY the filler line (exactly 4–5 words, no explanations, no questions):
"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": filler_prompt}],
            temperature=0.9,
            max_tokens=20
        )
        message = response.choices[0].message.content.strip().strip('"')

        # Skip if empty or ending phase
        if not message or session.phase == PhaseEnum.ENDING:
            return

        # Track recent fillers + hashes
        recent_fillers.append(message)
        session.meta_data["recent_fillers"] = recent_fillers[-16:]
        recent_filler_hashes.append(current_hash)
        session.meta_data["recent_filler_hashes"] = recent_filler_hashes[-10:]

    except Exception:
        message = "thinking..."

    # Ensure meta_data exists before storing
    if not session.meta_data:
        session.meta_data = {}
    recent_hashes = session.meta_data.get("recent_filler_hashes", [])
    recent_hashes.append(current_hash)
    session.meta_data["recent_filler_hashes"] = recent_hashes[-10:]

    await send_whatsapp_message(phone_number, message, sent_from_thrum=False)
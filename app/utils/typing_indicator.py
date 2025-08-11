import asyncio
import os
import hashlib
from openai import AsyncOpenAI
from app.db.models.enums import PhaseEnum, SenderEnum
from app.utils.whatsapp import send_whatsapp_message

client = AsyncOpenAI()
model = os.getenv("GPT_MODEL")

GOODBYE_KEYWORDS = ["bye", "goodbye", "see you", "exit", "later", "peace"]
SENSITIVE_KEYWORDS = [
    "died", "death", "passed away", "lost", "funeral", "grief", "mourning", "sad", "depressed", 
    "hurt", "pain", "crying", "devastated", "heartbroken", "suicide", "kill myself", "end it all",
    "cancer", "illness", "sick", "hospital", "divorce", "breakup", "broke up", "cheated", 
    "fired", "unemployed", "homeless", "broke", "anxiety", "panic", "scared", "terrified",
    "alone", "lonely", "worthless", "hate myself", "can't take it", "give up", "hopeless",
    "trauma", "abuse", "bullied", "betrayed", "abandoned", "rejected", "failure", "disappointed"
]

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

def is_sensitive_topic(user_input: str) -> bool:
    """Check if user input contains sensitive emotional content"""
    return any(keyword in user_input.lower() for keyword in SENSITIVE_KEYWORDS)

async def send_typing_indicator(phone_number: str, session, delay: float = 5.0):
    """Send Gen-AI filler after delay if processing takes too long"""
    await asyncio.sleep(delay)

    # Cancel if reply is ready
    if session.meta_data and session.meta_data.get("reply_ready", False):
        return

    # Get last user message from interactions
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""
    
    # Cancel if goodbye or session ending
    if (session.phase == PhaseEnum.ENDING or 
        any(k in user_input.lower() for k in GOODBYE_KEYWORDS)):
        return
    
    # Prevent repetition - check if we sent filler for this message already
    current_hash = get_message_hash(user_input)
    recent_filler_hashes = session.meta_data.get("recent_filler_hashes", []) if session.meta_data else []
    if current_hash in recent_filler_hashes:
        return

    # Get context for filler generation
    mood = session.entry_mood or "neutral"
    reply_context = get_reply_context(session)
    user_tone = session.meta_data.get("tone", "neutral") if session.meta_data else "neutral"
    
    # Check for sensitive topics and adjust tone accordingly
    is_sensitive = is_sensitive_topic(user_input)
    if is_sensitive:
        style = "gentle and supportive"
        tone_instruction = "Be compassionate and acknowledge their feelings"
    else:
        tone_map = {
            "sad": "gentle and empathetic",
            "angry": "calm and understanding",
            "serious": "measured and respectful",
            "excited": "energetic and playful",
            "happy": "fun and upbeat"
        }
        style = tone_map.get(user_tone, "natural and friendly")
        tone_instruction = "Acknowledge you're thinking of a thoughtful response"

    filler_prompt = f"""You are Thrum, a game discovery buddy who chats like a real friend.

The user just said: "{user_input}"
They are in a {mood} mood with {user_tone} energy.
You're about to respond in this context: {reply_context}
The main response is still generating.

Write a SHORT, {style} filler line to match the moment.
It should:
- Match their emotional state exactly
- {tone_instruction}
- Feel like a real friend texting
- Be under 8 words
- Never sound robotic or overly upbeat

Just write the message, no explanation."""
    
    # Get recent filler messages to avoid repetition (limit to last 6 for AI prompt)
    recent_fillers = session.meta_data.get("recent_fillers", []) if session.meta_data else []
    avoid_phrases = ", ".join(recent_fillers[-8:]) if recent_fillers else "none"
    
    # Check conversation history for sensitive context
    recent_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)[:5]
    conversation_context = " ".join([i.content for i in recent_interactions if i.sender == SenderEnum.User])
    has_sensitive_context = is_sensitive_topic(conversation_context)
    
    enhanced_prompt = f"""{filler_prompt}

DON'T use these recent phrases: {avoid_phrases}
{'IMPORTANT: The conversation involves sensitive emotional content. Stay gentle and supportive.' if has_sensitive_context else ''}
Be creative and fresh each time."""
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": enhanced_prompt}],
            temperature=0.9,
            max_tokens=25
        )
        message = response.choices[0].message.content.strip().strip('"')
        
        # Track recent fillers to avoid repetition
        if not session.meta_data:
            session.meta_data = {}
        recent_fillers = session.meta_data.get("recent_fillers", [])
        recent_fillers.append(message)
        session.meta_data["recent_fillers"] = recent_fillers[-16:]  # Keep last 16

    except Exception:
        # Check both current input and recent conversation for sensitive context
        recent_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)[:5]
        conversation_context = " ".join([i.content for i in recent_interactions if i.sender == SenderEnum.User])
        has_sensitive_context = is_sensitive_topic(user_input) or is_sensitive_topic(conversation_context)
        message = "I'm here..." if has_sensitive_context else "thinking..."
    
    # Store hash to prevent repetition (keep last 10)
    if not session.meta_data:
        session.meta_data = {}
    recent_hashes = session.meta_data.get("recent_filler_hashes", [])
    recent_hashes.append(current_hash)
    session.meta_data["recent_filler_hashes"] = recent_hashes[-10:]
    
    await send_whatsapp_message(phone_number, message, sent_from_thrum=False)
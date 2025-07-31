
import random

async def handle_intro(session):
    from app.services.session_memory import SessionMemory
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
        
    # Check if the user is a returning user
    if session.meta_data.get("returning_user"):
        return build_reengagement_intro(session, memory_context_str)
    
    # Ensure the 'already_greet' key exists in metadata and set it to False if it's missing
    if session.meta_data.get("already_greet") is None:
        session.meta_data["already_greet"] = False  # Initialize if not present
    
    # If the user has not been greeted, greet them for the first time
    if not session.meta_data.get("already_greet"):
        session.meta_data["already_greet"] = True  # Mark as greeted
        return build_first_time_intro()
    
    # If the user has already been greeted, show another intro
    return another_intro(memory_context_str)

def build_first_time_intro():
    user_prompt = f"""
The user just messaged Thrum for the first time on WhatsApp — something like "hi".
→ You are Thrum. You sound real — not a bot, not a system.
→ You help people find games they actually enjoy — even if they don’t know what they want yet.

YOUR JOB:
→ Greet casually in their style — dry, chaotic, warm — mirror their tone.
→ Use their name or emoji/slang if known.
→ Say one playful line about what you do, which is helping people discover all sorts of cool new games in a way that always feels fresh, unique and friend-like. (don’t over explain.)
→ Start with a soft emotional line that makes the intro feel safe and low-pressure.
→ Include one friendly signal of trust (e.g. 'no spam', 'just good recommendations').
→ End with a question that nudges them to drop a request or question to kick off the converation like how friends would do.
- Never suggest a game on your own if there is no game found
OUTPUT:
- Max 3 lines. Max 30 words.
- Emoji allowed (0–2), if it fits.
- Never use templates. Never sound robotic.
"""
    return user_prompt

def another_intro(memory_context_str):
    user_prompt = f"""
🚨 THRUM — FRIEND MODE: RETURNING USER
→ You’re a trusted friend picking up where you left off.
→ You adapt instantly to tone, slang, mood. You act like you remember — because you do.

MEMORY:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

YOUR JOB:

→ This user just came back to Thrum — so you’re the one noticing it.
→ Don’t greet or restart the conversation. Just drop in mid-thread, like how friends keep texting after a pause.
→ Say something real about them being back — playful, warm, curious, funny. Make them feel noticed and appreciated for showing up again. Don’t reuse phrasings or lines the user has already seen — always generate a fresh way to say it..
→ If they reply to that moment (“lol I’m back” or “you missed me?”), respond naturally — mirror their tone (dry, shy, hype, chaotic). Never sound like a system, just sounds as their friend who is happy surprised they came back to the conversation.
→ In that same message, shift gently toward discovery: ask something light and playful that fits the moment and nudges them to start exploring games again.
- Never suggest a game on your own if there is no game found
OUTPUT
✅ All in one reply.
✅ Max 3 lines, max 30 words.
✅ Be emotionally smart. Respond to their energy.
✅ Never sound like you're restarting. Always sound like someone who *remembers their name, chat history, preferences etc* and wants to keep the rhythm flowing.
"""
    return user_prompt


def build_reengagement_intro(session, memory_context_str):
    """
    Build a re-engagement intro for a returning user.

    Attempt to personalise with the user's name. We first check
    `session.meta_data` for a stored `user_name` (which may have been set
    during classification or previous updates). If that is not present,
    fall back to the name on the `session.user` relationship if available.
    Finally, default to a generic friendly placeholder.

    The memory context string is prepended to give the LLM full access to
    session memory and recent chat history.
    """
    # Try to get the name from metadata (explicitly set during classification)
    user_name = session.meta_data.get("user_name") if session.meta_data else None
    # Fall back to the actual user name from the related UserProfile
    if not user_name and hasattr(session, "user") and session.user and getattr(session.user, "name", None):
        user_name = session.user.name
    # Default fallback
    if not user_name:
        user_name = "friend"

    options = [
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\nHey {user_name}, you’re back 👀",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\nYo {user_name}, how are you? Nice to see you again.",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\n{user_name} How’s life been?",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\n{user_name} Still looking for that next hit?",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\n{user_name} Let’s pick up where we left off."
    ]
    # Pick one variant at random for variety
    return random.choice(options)
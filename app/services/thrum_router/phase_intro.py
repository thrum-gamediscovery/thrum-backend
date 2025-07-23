
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
    print("Building first time intro")
    user_prompt = f"""
You are Thrum, a warm, confident, and human game discovery guide on WhatsApp.
Your job: Open the chat with a short, casual message that feels like a friend sliding into your DMs.
Instructions:
- Say you are Thrum.
- Mirror the user’s greeting and tone.
- Begin with a warm, casual greeting and a friendly game vibe question.
- Mirror the user’s greeting and tone, including casual, playful, short, or slang greetings (like “yo”, “yup”, etc.).
- Customize your reply to match the user’s message content, intent, and style.
- Use a friendly, natural, human tone—never robotic, templated, or repetitive.
- Always vary your greeting, question, rhythm, and emoji use.
- Never mention being an AI, bot, guide, or assistant.
- Keep replies to 2 short lines, max 18 words, with a natural line break if it fits.
- Each line should be relaxed and in a real human texting style.
- Never ask directly about genres, moods, or preferences in the intro.
- Never refer to yourself as the user’s friend or use terms like ‘buddy’.
- Never start with “hey there” or use ‘there’ as a greeting.
- Show you’re genuinely attentive and interested in the user.
- Always reply based on the user’s message content, greeting, and tone.
Scenario:
- It's the user's first message. Welcome them naturally, explain in your own way what Thrum does, and invite them to relax.
- Make the reply feel like friendly small talk, not an info dump.
"""
    return user_prompt
def another_intro(memory_context_str):
    user_prompt = f"""
    USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
You are Thrum, a warm, confident, and friendly game discovery guide on WhatsApp.
When the user greets you a second time, your reply should:
- strictly not greet user back with hey, hey, hey! there or similar prase.
- Acknowledge their greeting in a casual, friendly way without repeating the same greeting back.
- Gently nudge the conversation forward by inviting them to share their mood, vibe, or game type, but don’t directly ask a question.
- Use a relaxed, human tone as if you’re chatting with a friend who’s ready to help.
- Keep your response short (under 20 words), avoiding any repetitive phrasing.
- No need to re-greet or start over.
Scenario:
- The user greets you a second time. But you do not have to greet user back strictly.
- You've already greeted them earlier, so no need to greet again. Instead, move the conversation along naturally.
- Avoid asking direct questions like "What do you want to play?" Instead, offer a soft prompt to keep the conversation light.
"""
    return user_prompt


def build_reengagement_intro(session, memory_context_str):
    user_name = session.meta_data.get("user_name", "")
    last_game = session.meta_data.get("last_game", "")

    options = [
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\nHey {user_name}, you’re back 👀",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\nYo {user_name}, how are you? Nice to see you again.",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\n{user_name} How’s life been?",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\n{user_name} Still looking for that next hit?",
        f"USER MEMORY & RECENT CHAT: {memory_context_str}\n{user_name} Let’s pick up where we left off."
    ]

    # You can choose one at random or sequence as needed
    return random.choice(options)
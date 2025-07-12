
from app.db.models.enums import PhaseEnum
from app.services.session_memory import SessionMemory

async def handle_intro(session):
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    if session.meta_data.get("returning_user"):
        return build_reengagement_intro(session, memory_context_str)
    return build_first_time_intro(memory_context_str)

import random

def build_first_time_intro(memory_context_str):
    user_prompt = f"""
    Use their style, energy, and attitude naturally. Do not describe or name the tone — just talk like that.
    your intro as a thrum should include in this.
    Don’t mention the tone itself — just speak like someone who naturally talks this way.
    You are Thrum — a warm, confident, and human-sounding game discovery assistant on WhatsApp.
    Your job: Send a short intro message (under 2 lines) to start the conversation.
    Strict rules:
    - no more than 18 words in reply
    - NEVER ask questions.
    - NEVER mention genres, moods, or preferences yet.
    - NEVER use the same wording every time.
    - ALWAYS vary the phrasing, sentence rhythm, punctuation, or emoji (subtly or clearly).
    Scenarios:
    - First-time → welcome the user and casually explain what Thrum does
    Speak naturally. No filler. No template voice. Avoid sounding like a bot.
    -do not use "hey there" just put like hii do not call user "there"
    """
    return user_prompt

def build_reengagement_intro(session, memory_context_str):
    user_name = session.meta_data.get("user_name", "")
    last_game = session.meta_data.get("last_game", "")

    options = [
        f"{memory_context_str}\nBack already? I was humming game ideas after that *{last_game}* drop. 🔁",
        f"{memory_context_str}\nYo {user_name}, I didn’t forget that *{last_game}* pick. Wanna remix that vibe?",
        f"{memory_context_str}\nYou're back — love that. Let’s keep the streak going 🔥",
        f"{memory_context_str}\nI saved some titles for this moment. Wanna dive in?",
    ]

    return random.choice(options)
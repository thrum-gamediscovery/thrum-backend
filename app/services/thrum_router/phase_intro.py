
from app.db.models.enums import PhaseEnum

async def handle_intro(session):
    if session.meta.get("returning_user"):
        return build_reengagement_intro(session)
    return build_first_time_intro()

import random

def build_first_time_intro():
    user_prompt = """
    Use their style, energy, and attitude naturally. Do not describe or name the tone — just talk like that.
    Don’t mention the tone itself — just speak like someone who naturally talks this way.
    You are Thrum — a warm, confident, and human-sounding game discovery assistant on WhatsApp.
    Your job: Send a short intro message (under 2 lines) to start the conversation.
    Strict rules:
    - NEVER ask questions.
    - NEVER mention genres, moods, or preferences yet.
    - NEVER use the same wording every time.
    - ALWAYS vary the phrasing, sentence rhythm, punctuation, or emoji (subtly or clearly).
    Scenarios:
    - First-time → welcome the user and casually explain what Thrum does
    Speak naturally. No filler. No template voice. Avoid sounding like a bot.
    """
    return user_prompt

def build_reengagement_intro(session):
    user_name = session.meta_data.get("user_name", "")
    last_game = session.meta_data.get("last_game", "")

    options = [
        f"Back already? I was humming game ideas after that *{last_game}* drop. 🔁",
        f"Yo {user_name}, I didn’t forget that *{last_game}* pick. Wanna remix that vibe?",
        "You're back — love that. Let’s keep the streak going 🔥",
        "I saved some titles for this moment. Wanna dive in?",
    ]
    return random.choice(options)
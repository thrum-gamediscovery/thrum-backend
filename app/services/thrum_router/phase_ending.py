from app.db.models.enums import PhaseEnum, SessionTypeEnum

async def handle_ending(session):
    """
    End the session gracefully after user has disengaged, declined more games, or gone silent.

    Updates the session phase to ENDING, optionally marks it as CLOSED,
    and returns a warm farewell message.
    """
    session.phase = PhaseEnum.ENDING

    user_prompt = (
    "The user has either gone silent, declined more games, or seems to be disengaging.\n"
    "Write a warm, friendly farewell message to end the session gracefully.\n"
    "Keep it short — no more than 10–15 words.\n"
    "Sound natural, not robotic. No follow-up questions. No pressure to return.\n"
    "Tone should feel like a friend signing off respectfully.\n"
    "If possible, include a soft suggestion that you’re always here if they return."
)
    return user_prompt

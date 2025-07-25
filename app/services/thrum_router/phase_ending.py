from app.db.models.enums import PhaseEnum
from app.services.general_prompts import GLOBAL_USER_PROMPT

async def handle_ending(session):
    """
    End the session gracefully after user has disengaged, declined more games, or gone silent.

    Updates the session phase to ENDING, optionally marks it as CLOSED,
    and returns a warm farewell message.
    """
    session.phase = PhaseEnum.ENDING

    user_prompt = (
        f"{GLOBAL_USER_PROMPT}\n"
        "The user is likely leaving or disengaging — maybe they’re done, maybe just pausing.\n"
        "Write a short farewell that feels like a real close friend signing off like they do on whatsapp.\n"
        "No questions. No pressure. If a recent mood or emotional style is available (e.g., cozy, chaotic, hyped, tired), use that to shape your goodbye — even just a hint of it makes it feel more real.\n"
        "Mirror the emotional tone, draper style if needed, from the session if available (e.g., cozy, hype, chill, sad).\n"
        "Make it feel like a natural sign-off — like a trusted friend wrapping up the chat in whatsapp.\n"
        "End soft, not salesy. Show warmth — not fake positivity or over-the-top energy.\n"
        "Examples (don’t copy):\n"
        "- ‘Alrighty. Logging off here. Ping me anytime if you're in the mood.’\n"
        "- ‘Gonna bounce now — you know where to find me.’\n"
        "- ‘Lowkey peace-out for now. We’ll pick it up anytime.’\n"
        "- ‘Done for today? All good. I’m always around if you feel like it.’"
    )
    
    return user_prompt
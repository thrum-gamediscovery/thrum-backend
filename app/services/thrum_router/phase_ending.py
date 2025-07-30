from app.db.models.enums import PhaseEnum
from app.services.general_prompts import GLOBAL_USER_PROMPT

from app.db.models.enums import PhaseEnum
from app.services.general_prompts import GLOBAL_USER_PROMPT

async def handle_ending(session):
    """
    End the session gracefully after user has disengaged, declined more games, or gone silent.

    Updates the session phase to ENDING, optionally marks it as CLOSED,
    and returns a warm farewell message.
    """
    session.phase = PhaseEnum.ENDING

    # Get tone from session metadata
    tone = session.meta_data.get("tone", "friendly")
    tone_context = f"\nCurrent session tone: {tone}"

    user_prompt = (
        f"{GLOBAL_USER_PROMPT}\n"
        "The user is disengaging, saying goodbye, or has stopped responding. Time to end like a trusted friend signing off.\n"
        f"{tone_context}\n"
        "Write a short farewell that feels like a real friend wrapping up a WhatsApp chat.\n"
        "BEHAVIOR RULES:\n"
        "- Mirror the current session tone ({tone}) in your farewell style\n"
        "- NO pressure, NO follow-ups, NO 'hope to see you again'\n"
        "- NO sales logic or reminders to return\n"
        "- Use casual WhatsApp-style language between friends\n"
        "- Can gesture you're always around (e.g., 'you know where to find me') only if emotionally appropriate\n"
        "- DO NOT sound formal, scripted, or overly cheerful\n"
        "- Soft exit, still emotionally connected, ready for next conversation as friends\n"
        "\n"
        "VIBE: Like a trusted friend wrapping up a great conversation — soft exit, still emotionally connected.\n"
        "\n"
        "Examples for inspiration (don't copy exactly):\n"
        "- 'Alrighty. Logging off here. Ping me anytime if you're in the mood.'\n"
        "- 'Gonna bounce now — you know where to find me.'\n"
        "- 'Lowkey peace-out for now. We'll pick it up anytime.'\n"
        "- 'Done for today? All good. I'm always around if you feel like it.'"
        "- Never suggest a game on your own if there is no game found"
    )
    
    return user_prompt
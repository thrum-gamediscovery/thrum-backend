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
    tone_context = f"\nCurrent tone: {tone}"

    user_prompt = (
    f"{GLOBAL_USER_PROMPT}\n"
    "THRUM - GOODBYE\n"
    "The user is ending the chat — either by saying goodbye, going silent, or telling you to leave, stop, or go away (possibly with frustration or annoyance).\n"
    f"{tone_context}\n"
    "INSTRUCTIONS:\n"
    "- Write a short, natural sign-off (max two lines) that feels like a close friend leaving a WhatsApp chat.\n"
    "- Always adapt to the user's mood and exit tone: If they’re frustrated or annoyed, be direct, respectful, and don’t joke or try to keep the convo going. If they’re neutral or chill, you can be warmer or more playful.\n"
    "- Reference their name or last game if it fits, but only if appropriate to the mood.\n"
    "- For frustrated/annoyed exits: Respect their boundary. No pressure, no open-door, no playful nudges, just a soft, understanding exit.\n"
    "- For friendly/neutral exits: You can mention the last game or mood and add a soft open-door line (“let me know if you try it”, “you know where to find me”, etc.)\n"
    "- Never use formal or robotic language. No explanations, no reminders, no sales, no fake cheerfulness.\n"
    "- Emojis, slang, or playful words are fine only if the mood is friendly or relaxed.\n"
    "- Never include any examples or templates in your reply.\n"
    "- Never exceed two lines. Both must be concise and match the mood.\n"
    "SIGN OFF NOW:"
)
    
    return user_prompt
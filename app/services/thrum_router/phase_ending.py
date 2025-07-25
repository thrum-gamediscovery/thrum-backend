from app.db.models.enums import PhaseEnum, SessionTypeEnum
from app.services.session_memory import SessionMemory
from app.services.general_prompts import GLOBAL_USER_PROMPT

async def handle_ending(session):
    """
    End the session gracefully after user has disengaged, declined more games, or gone silent.

    Updates the session phase to ENDING, optionally marks it as CLOSED,
    and returns a warm farewell message.
    """
    session.phase = PhaseEnum.ENDING

    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    user_prompt = f"""
    {GLOBAL_USER_PROMPT}
    ---
    You are Thrum, the user’s emotionally-intelligent, tone-sensitive game friend.
    The user just signaled that they’re wrapping up — but you want to leave the door open like a real friend.
    → Say goodbye in a personal, tone-matching way like how friends would do in a cool way
    → Mention they can always ping you again like how friend talk over whatsapp
    → Optionally say something fun, weird, or thoughtful
    → Use Draper-style emotional cadence — warm, slightly cheeky, casual
    Never say “Session ending.” Never repeat phrases. Never sound formal.
    Only generate one closing line.
    """
    
    return user_prompt

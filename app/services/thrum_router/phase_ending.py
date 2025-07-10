from app.db.models.enums import PhaseEnum, SessionTypeEnum
from app.services.session_memory import create_session_memory_bond
from datetime import datetime

async def handle_ending(session, db=None):
    """
    End the session gracefully after user has disengaged, declined more games, or gone silent.
    Includes memory bonding and warm summary lines.
    """
    session.phase = PhaseEnum.ENDING
    
    # Create memory bond if not already done
    if not session.meta_data.get("memory_bond"):
        memory_summary = await create_session_memory_bond(session, db)
    else:
        memory_summary = session.meta_data.get("memory_summary", "")
    
    # Mark session as closed
    session.meta_data = session.meta_data or {}
    session.meta_data["session_closed"] = True
    session.meta_data["closed_at"] = datetime.utcnow().isoformat()
    
    # Generate warm farewell based on interaction context
    interaction_count = len(session.interactions)
    mood_shift = session.entry_mood != session.exit_mood
    games_recommended = any(i.game_id for i in session.interactions)
    
    # Customize farewell based on session context
    if interaction_count > 10 and games_recommended:
        farewell_context = "long engaging chat with game recommendations"
    elif mood_shift and games_recommended:
        farewell_context = "mood journey with game exploration"
    elif games_recommended:
        farewell_context = "game discovery session"
    else:
        farewell_context = "brief chat"
    
    user_prompt = (
        f"Context: This was a {farewell_context}.\n"
        f"Write a warm, friendly farewell message (max 25 words) that:\n"
        f"1. Acknowledges their time and engagement\n"
        f"2. References their mood journey if changed ({session.entry_mood} → {session.exit_mood})\n"
        f"3. Leaves the door open for future chats\n"
        f"Keep it natural and cozy, like a friend saying goodbye."
    )
    
    db.commit()
    return user_prompt
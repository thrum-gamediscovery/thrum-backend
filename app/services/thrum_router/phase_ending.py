from app.db.models.enums import PhaseEnum, SessionTypeEnum

async def handle_ending(session):
    """
    End the session gracefully after user has disengaged, declined more games, or gone silent.

    Updates the session phase to ENDING, optionally marks it as CLOSED,
    and returns a warm farewell message.
    """
    session.phase = PhaseEnum.ENDING

    farewell_lines = [
        "Alrighty! I’ll be here whenever you’re in the mood for a fresh game 🎮✨",
        "Catch you later — your next game drop will be ready when you are!",
        "Good chatting! Ping me anytime you want a new vibe 👋",
        "All done for now! Can’t wait to share the next great one with you.",
    ]

    import random
    return random.choice(farewell_lines)

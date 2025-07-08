from app.services.greetings import generate_intro
from app.db.models.enums import PhaseEnum

async def handle_intro(session, is_first_message: bool, idle_reconnect: bool, user_input: str, user):
    if any(keyword in user_input.lower() for keyword in ["what do you do", "how does it work", "explain", "how this works", "Explain me this"]):
        return (
            "I help you find the perfect game based on your vibe — mood, genre, or title 🎮\n"
            "Just drop a word like 'puzzle', 'adventure', or how you're feeling — and I’ll pick one for you!"
        )

    session.phase = PhaseEnum.DISCOVERY
    return await generate_intro(session=session,is_first_message=is_first_message, idle_reconnect=idle_reconnect, user_input=user_input, user=user)
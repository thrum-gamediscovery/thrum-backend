from app.services.greetings import generate_intro
from app.db.models.enums import PhaseEnum, ResponseTypeEnum
from app.services.session_manager import already_asked

async def handle_intro(session, is_first_message: bool, idle_reconnect: bool, user_input: str):
    if not already_asked(session, ResponseTypeEnum.Callback):  # Assuming Callback is used for mood
        session.phase = PhaseEnum.DISCOVERY
        return await generate_intro(is_first_message, idle_reconnect, user_input)
from app.services.input_classifier import is_intent_override
from app.services.session_memory import deliver_game_immediately
from app.db.models.enums import PhaseEnum

async def check_intent_override(db,user_input, user, session):
    if await is_intent_override(user_input):
        session.phase = PhaseEnum.DELIVERY
        return await deliver_game_immediately(db,user, session)
    return None

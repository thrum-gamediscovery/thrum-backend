from app.services.session_memory import (
    extract_discovery_signals,
    ask_discovery_question
)
from app.services.session_memory import confirm_input_summary, deliver_game_immediately
from app.db.models.enums import PhaseEnum, ResponseTypeEnum
from app.utils.error_handler import safe_call


@safe_call("Hmm, I had trouble figuring out what to ask next. Let's try something fun instead! 🎮")
async def handle_discovery(db, session, user):
    discovery_data = await extract_discovery_signals(session)

    if discovery_data.is_complete():
        session.phase = PhaseEnum.CONFIRMATION
        return await confirm_input_summary(session)

    elif session.discovery_questions_asked >= 2:
        session.phase = PhaseEnum.DELIVERY
        session.discovery_questions_asked = 0
        return await deliver_game_immediately(db, user, session)
    
    else:
        question = await ask_discovery_question(session)
        session.discovery_questions_asked += 1
        return question


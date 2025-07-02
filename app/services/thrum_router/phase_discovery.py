from app.services.session_memory import (
    extract_discovery_signals,
    store_in_session_memory,
    ask_discovery_question
)
from app.services.session_memory import confirm_input_summary, deliver_game_immediately
from app.db.models.enums import PhaseEnum

async def handle_discovery(db,user_input, session, user):
    discovery_data = await extract_discovery_signals(user_input)

    if discovery_data.is_complete():
        await store_in_session_memory(session, discovery_data)
        session.phase = PhaseEnum.CONFIRMATION
        return await confirm_input_summary(discovery_data)

    elif session.discovery_questions_asked >= 2:
        session.phase = PhaseEnum.DELIVERY
        return await deliver_game_immediately(db,user, session)

    else:
        question = await ask_discovery_question(session)
        session.discovery_questions_asked += 1
        return question

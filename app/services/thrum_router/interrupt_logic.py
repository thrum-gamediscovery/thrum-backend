from app.services.input_classifier import classify_user_intent
from app.services.session_memory import deliver_game_immediately
from app.db.models.enums import PhaseEnum
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.phase_discovery import handle_discovery

async def check_intent_override(db, user_input, user, session):
    classification = await classify_user_intent(user_input=user_input,session=session)

    if classification.get("intent_override"):
        if session.game_rejection_count >=2:
            session.phase = PhaseEnum.DISCOVERY
            session.game_rejection_count = 0
            print("------------------------------------------------------------------------------------------------------------------------------- rejection 2 time out")
            return await handle_discovery(db=db, session=session, user=user)
        else:
            session.phase = PhaseEnum.DELIVERY
            return await deliver_game_immediately(db, user, session)

    if classification.get("not_in_the_mood"):
        session.phase = PhaseEnum.ENDING
        return await handle_ending(session)

    return None
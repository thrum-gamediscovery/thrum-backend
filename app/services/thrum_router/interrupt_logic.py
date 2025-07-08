from app.services.input_classifier import classify_user_intent, have_to_recommend
from app.services.thrum_router.phase_delivery import explain_last_game_match
from app.services.session_memory import deliver_game_immediately
from app.db.models.enums import PhaseEnum
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.phase_discovery import handle_discovery

async def check_intent_override(db, user_input, user, session, classification):
    classification_intent = await classify_user_intent(user_input=user_input,session=session)

    if classification_intent.get("intent_override"):
        if session.game_rejection_count >=2:
            session.phase = PhaseEnum.DISCOVERY
            session.game_rejection_count = 0
            return await handle_discovery(db=db, session=session, user=user, classification=classification, user_input=user_input)
        else:
            should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

            if should_recommend:
                session.phase = PhaseEnum.DELIVERY
                return await deliver_game_immediately(db, user, session)
            else:
                # If no new recommendation is needed, explain the last recommended game based on user feedback
                explanation_response = await explain_last_game_match(session=session, user=user, user_input=user_input)
                return explanation_response  # Return the explanation of the last game

    if classification_intent.get("not_in_the_mood"):
        session.phase = PhaseEnum.ENDING
        return await handle_ending(session)

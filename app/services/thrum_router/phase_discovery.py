from app.services.input_classifier import have_to_recommend
from app.services.thrum_router.phase_delivery import explain_last_game_match
from app.services.session_memory import confirm_input_summary, deliver_game_immediately, ask_discovery_question , extract_discovery_signals
from app.db.models.enums import PhaseEnum
from app.utils.error_handler import safe_call


@safe_call("Hmm, I had trouble figuring out what to ask next. Let's try something fun instead! 🎮")
async def handle_discovery(db, session, user, classification, user_input):
    if any(phrase in user_input.lower() for phrase in ["what do you do", "how does it work", "explain", "how this works", "Explain me this", "Explain me first"]):
        return (
            "I help you find games that match your mood, genre, or vibe 🎮\n"
            "You can say something like 'fast action', 'sad story', or even a title like 'GTA'."
        )
    discovery_data = await extract_discovery_signals(session)

    if discovery_data.is_complete():
        session.phase = PhaseEnum.CONFIRMATION
        return await confirm_input_summary(session)

    elif session.discovery_questions_asked >= 2:
        should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

        if should_recommend:
            session.phase = PhaseEnum.DELIVERY
            session.discovery_questions_asked = 0
            return await deliver_game_immediately(db, user, session)
        else:
            # If no new recommendation is needed, explain the last recommended game based on user feedback
            explanation_response = await explain_last_game_match(session=session, user=user, user_input=user_input)
            return explanation_response  # Return the explanation of the last game
    
    else:
        question = await ask_discovery_question(session)
        session.discovery_questions_asked += 1
        return question


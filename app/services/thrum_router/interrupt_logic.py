from app.services.input_classifier import classify_user_intent
from app.services.session_memory import deliver_game_immediately, diliver_similar_game
from app.services.thrum_router.phase_delivery import handle_reject_Recommendation
from app.db.models.enums import PhaseEnum
from app.services.thrum_router.phase_intro import handle_intro
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.phase_confirmation import handle_confirmed_game, generate_low_effort_response
from app.services.thrum_router.phase_discovery import dynamic_faq_gpt, handle_other_input, share_thrum_ping, share_thrum_message

async def check_intent_override(db, user_input, user, session, classification, intrection):
    from app.services.thrum_router.phase_discovery import handle_discovery
    from app.services.thrum_router.phase_followup import handle_game_inquiry
    # Classify the user's intent based on their input
    classification_intent = await classify_user_intent(user_input=user_input, session=session)
    intrection.classification = {"input" : classification, "intent" : classification_intent}
    db.commit()
    if session.meta_data.get("ask_for_rec_friend")  and (classification_intent.get("Give_Info") or classification_intent.get("Other")):
        session.meta_data["ask_for_rec_friend"] = False
        session.phase = PhaseEnum.DISCOVERY
        return await share_thrum_ping(session)

    if classification_intent.get("Low_Effort_Response"):
        return await generate_low_effort_response(session)
    # Check if the user is in the discovery phase
    if classification_intent.get("Phase_Discovery"):
        return await handle_discovery(db=db, session=session, user=user)
    
    # Handle rejection of recommendation
    if classification_intent.get("Reject_Recommendation"):
        return await handle_reject_Recommendation(db, session, user, classification_intent)

    # Handle request for quick game recommendation
    elif classification_intent.get("Request_Quick_Recommendation"):
        session.phase = PhaseEnum.DELIVERY
        return await deliver_game_immediately(db, user, session)

    # Handle user inquiry about a game
    elif classification_intent.get("Inquire_About_Game"):
        session.phase = PhaseEnum.FOLLOWUP
        return await handle_game_inquiry(db, user, session, user_input)

    # Handle information provided by the user
    elif classification_intent.get("Give_Info"):
        session.phase = PhaseEnum.DISCOVERY
        return await handle_discovery(db=db, session=session, user=user)

    # Handle user opting out
    elif classification_intent.get("Opt_Out"):
        session.phase = PhaseEnum.ENDING
        return await handle_ending(session)

    # Handle user confirming a game recommendation
    elif classification_intent.get("Confirm_Game"):
        session.phase = PhaseEnum.CONFIRMATION
        return await handle_confirmed_game(db, user, session)
    
    elif classification_intent.get("want_to_share_friend"):
        if session.shared_with_friend:
            classification_intent["Other"] = True
        else:
            session.shared_with_friend = True
            session.phase = PhaseEnum.DISCOVERY
            db.commit()
            return await share_thrum_message(session)
    
    elif classification_intent.get("Greet"):
        session.phase = PhaseEnum.INTRO
        return await handle_intro(session)

    # Handle cases where user input doesn't match any predefined intent
    elif classification_intent.get("Other") or classification_intent.get("Other_Question"):
        return await handle_other_input(db, user, session, user_input)
    
    elif classification_intent.get("Bot_Error_Mentioned"):
        response = (
            "the Thrum encounters an error or loses track of the conversation, it should first apologize to the user in a friendly and empathetic manner. After the apology, the bot should invite the user to re-engage by asking for clarification on what they are looking for. The tone should remain light, open, and non-repetitive, ensuring the user feels comfortable guiding the conversation forward.Most Most Most importent is reply is must look like humanly - Not robotic"
        )
        return response
    
    elif classification_intent.get("About_FAQ"):
        return await dynamic_faq_gpt(session, user_input)

    if classification_intent.get("Request_Similar_Game"):
        session.phase = PhaseEnum.DELIVERY
        return await diliver_similar_game(db, user, session)
    
    # Default handling if no specific intent is detected
    return None

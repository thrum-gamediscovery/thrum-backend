from app.services.input_classifier import classify_user_intent, have_to_recommend
from app.services.game_recommend import game_recommendation
from app.services.thrum_router.phase_delivery import explain_last_game_match
from app.services.session_memory import deliver_game_immediately
from app.db.models.enums import PhaseEnum
from app.services.thrum_router.phase_intro import handle_intro
from app.services.thrum_router.phase_ending import handle_ending

from app.services.thrum_router.phase_confirmation import handle_confirmed_game
from app.services.thrum_router.phase_discovery import handle_discovery, handle_user_info, handle_other_input

async def check_intent_override(db, user_input, user, session, classification):
    print('check_intent_override.........................')
    # Classify the user's intent based on their input
    from app.services.thrum_router.phase_followup import handle_game_inquiry, handle_followup
    classification_intent = await classify_user_intent(user_input=user_input, session=session)

    # Handle rejection of recommendation
    if classification_intent.get("Reject_Recommendation"):
        # If the user has rejected the recommendation twice, reset and handle discovery phase
        if session.game_rejection_count >= 2:
            session.phase = PhaseEnum.DISCOVERY
            session.game_rejection_count = 0
            return await handle_discovery(db=db, session=session, user=user, classification=classification, user_input=user_input)
        else:
            should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

            if should_recommend:
                session.phase = PhaseEnum.DELIVERY
                game,_ =  await game_recommendation(db=db, user=user, session=session)
                # Extract platform info
                preferred_platforms = session.platform_preference or []
                user_platform = preferred_platforms[-1] if preferred_platforms else None
                game_platforms = game.get("platforms", [])

                # Dynamic platform mention line (natural, not template)
                if user_platform and user_platform in game_platforms:
                    platform_note = f"It’s playable on your preferred platform: {user_platform}."
                elif user_platform:
                    available = ", ".join(game_platforms)
                    platform_note = (
                        f"It’s not on your usual platform ({user_platform}), "
                        f"but works on: {available}."
                    )
                else:
                    platform_note = f"Available on: {', '.join(game_platforms)}."

                # Interactive rejection response
                mood = session.exit_mood or "good"
                rejection_count = session.game_rejection_count
                
                if rejection_count == 0:
                    response = f"No worries! Let me try **{game['title']}** instead - it's got that perfect {mood} energy you're after. {platform_note} Sound better? 🎯"
                else:
                    response = f"Got it! How about **{game['title']}**? It's totally different and matches your {mood} vibe perfectly. {platform_note} This one feel right? 😊"
                
                return response
            else: 
                explanation_response = await explain_last_game_match(session=session)
                return explanation_response

    # Handle request for quick game recommendation
    elif classification_intent.get("Request_Quick_Recommendation"):
        session.phase = PhaseEnum.DELIVERY
        quick_response = await deliver_game_immediately(db, user, session)
        # Add interactive follow-up
        quick_response += "\n\nWant me to explain why this is perfect for you? 🤔"
        return quick_response

    # Handle user inquiry about a game
    elif classification_intent.get("Inquire_About_Game"):
        session.phase = PhaseEnum.FOLLOWUP
        return await handle_game_inquiry(db, user, session, user_input)

    # Handle information provided by the user
    elif classification_intent.get("Give_Info"):
        session.phase = PhaseEnum.DISCOVERY
        discovery_response = await handle_discovery(db=db, session=session, classification=classification, user=user, user_input=user_input)
        
        # Add engagement based on info provided
        if len(user_input) > 20:  # Detailed response
            discovery_response += "\n\nI love the detail! This helps me understand your style perfectly. ✨"
        
        return discovery_response

    # Handle user opting out
    elif classification_intent.get("Opt_Out"):
        session.phase = PhaseEnum.ENDING
        return await handle_ending(session)

    # Handle user confirming a game recommendation
    elif classification_intent.get("Confirm_Game"):
        if session.phase == PhaseEnum.INTRO:
            return handle_discovery(db=db, session=session, classification=classification, user=user, user_input=user_input)
        session.phase = PhaseEnum.CONFIRMATION
        return await handle_confirmed_game(db, user, session)
    
    elif classification_intent.get("Greet"):
        session.phase = PhaseEnum.INTRO
        return await handle_intro(session)

    # Handle cases where user input doesn't match any predefined intent
    elif classification_intent.get("Other") or classification_intent.get("Other_Question"):
        if session.phase == PhaseEnum.INTRO:
            return handle_discovery(db=db, session=session, classification=classification, user=user, user_input=user_input)
        
        other_response = await handle_other_input(db, user, session, user_input)
        
        # Add gentle redirect if conversation is wandering
        interaction_count = len(session.interactions)
        if interaction_count > 3 and not session.exit_mood:
            other_response += "\n\nLet's get you a great game recommendation! What's your current vibe? 🎮"
        
        return other_response

    # Default handling if no specific intent is detected
    return None

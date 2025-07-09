from app.services.input_classifier import classify_user_intent
from app.services.game_recommend import game_recommendation
from app.services.session_memory import deliver_game_immediately
from app.db.models.enums import PhaseEnum
from app.services.thrum_router.phase_intro import handle_reengagement, handle_intro
from app.services.thrum_router.phase_ending import handle_ending

from app.services.thrum_router.phase_confirmation import handle_confirmed_game
from app.services.thrum_router.phase_discovery import handle_discovery, handle_user_info, handle_other_input

async def check_intent_override(db, user_input, user, session, classification):
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
            session.game_rejection_count += 1
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

            # Final user prompt for GPT
            user_prompt = (
                f"Suggest the game **{game['title']}** to the user.\n"
                f"– it must include The game title in bold using Markdown: **{game['title']}**\n"
                f"In one short line (10–12 words), explain why this game fits them —\n"
                f"based on its genre, vibe, story, or mechanics.\n"
                f"Use user context from the system prompt (e.g., story_preference, genre, platform_preference).\n"
                f"Then naturally include this note about platforms: {platform_note}\n"
                f"Tone should be confident, warm, and very human. Never say 'maybe' or 'you might like'."
                f"must suggest game with reason that why it fits to user with mirror effect"
            )

            return user_prompt
            

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
        return await handle_user_info(db=db, user=user, session=session, classification=classification, user_input=user_input)

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
        return await handle_intro()

    # Handle cases where user input doesn't match any predefined intent
    elif classification_intent.get("Other") or classification_intent.get("Other_Question"):
        if session.phase == PhaseEnum.INTRO:
            return handle_discovery(db=db, session=session, classification=classification, user=user, user_input=user_input)
        # Handle the "Other" intent, which represents any input that doesn't fit the categories above
        return await handle_other_input(db, user, session, user_input)

    # Default handling if no specific intent is detected
    return None

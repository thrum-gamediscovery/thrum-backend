from app.services.input_classifier import classify_user_intent, have_to_recommend
from app.services.game_recommend import game_recommendation
from app.services.thrum_router.phase_delivery import explain_last_game_match
from app.services.session_memory import deliver_game_immediately
from app.db.models.enums import PhaseEnum
from app.services.thrum_router.phase_intro import handle_intro
from app.services.thrum_router.phase_ending import handle_ending

from app.services.thrum_router.phase_confirmation import handle_confirmed_game
from app.services.thrum_router.phase_discovery import handle_discovery, handle_user_info, handle_other_input
from app.services.session_memory import SessionMemory

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

            session_memory = SessionMemory(session)
            memory_context_str = session_memory.to_prompt()
            
            if should_recommend:
                session.phase = PhaseEnum.DELIVERY
                game,_ =  await game_recommendation(db=db, user=user, session=session)
                if not game:
                    print("################################################################")
                    user_prompt =( 
                        f"{memory_context_str}\n"
                        f"Use this prompt only when no games are available for the user’s chosen genre and platform.\n"
                        f"never repeat the same sentence every time do change that always.\n"
                        f"you must warmly inform the user there’s no match for that combination — robotic.\n"
                        f"clearly mention that for that genre and platfrom there is no game.so pick different genre or platfrom.\n"
                        f"tell them to pick a different genre or platform.\n"
                        f"Highlight that game discovery is meant to be fun and flexible, never a dead end.\n"
                        f"Never use words like 'sorry,' 'unfortunately,' or any kind of generic filler.\n"
                        f"The reply must be 12–18 words, in a maximum of two sentences, and always end with an enthusiastic and empowering invitation to explore new options together.\n"
                        )
                    return user_prompt
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
                    f"{memory_context_str}\n"
                    f"Suggest a second game after the user rejected the previous one.The whole msg should no more than 25-30 words.\n"
                    f"The game must be **{game['title']}** (use bold Markdown: **{game['title']}**).\n"
                    f"In one short line (10–12 words), explain why this new game fits them —\n"
                    f"based on its genre, vibe, story, or mechanics — and vary from the first suggestion if possible.\n"
                    f"Mirror the user's reason for rejection in a warm, human way before suggesting the new game.\n"
                    f"Use user context from the system prompt (like genre, story_preference, platform_preference) to personalize.\n"
                    f"Then naturally include this platform note (rephrase it to sound friendly, do not paste as-is): {platform_note}\n"
                    f"Tone must be confident, warm, emotionally intelligent — never robotic.\n"
                    f"Never say 'maybe' or 'you might like'. Be sure the game feels tailored.\n"
                    f"If the user was only asking about availability and the game was unavailable, THEN and only then, offer a different suggestion that is available.\n"
                )

                return user_prompt
            else: 
                explanation_response = await explain_last_game_match(session=session)
                return explanation_response

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
        return await handle_discovery(db=db, session=session, classification=classification, user=user, user_input=user_input)

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
        # Handle the "Other" intent, which represents any input that doesn't fit the categories above
        return await handle_other_input(db, user, session, user_input)

    # Default handling if no specific intent is detected
    return None

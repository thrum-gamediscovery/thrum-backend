from app.services.input_classifier import classify_user_intent, classify_input_ambiguity
from app.services.thrum_router.phase_delivery import handle_reject_Recommendation, deliver_game_immediately, diliver_similar_game, diliver_particular_game
from app.db.models.enums import PhaseEnum, SenderEnum
from app.services.thrum_router.phase_intro import handle_intro, classify_first_message, build_onboarding_prompt, is_thin_reply, build_depth_nudge_prompt
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.phase_confirmation import handle_confirmed_game
from app.services.thrum_router.share_with_friends import share_thrum_ping, share_thrum_message
from app.services.general_prompts import LIKED_FOLLOWUP,GLOBAL_USER_PROMPT
from app.services.thrum_router.phase_other import dynamic_faq_gpt, handle_other_input, generate_low_effort_response, ask_ambiguity_clarification

async def should_trigger_referral(session, classification_intent):
    if session.meta_data.get("ask_for_rec_friend", False)  and (classification_intent.get("Confirm_Game")):
        if session.shared_with_friend:
            return False
        if not session.meta_data.get("dont_give_name", False):
            return False  # Wait until name is collected
        if session.meta_data.get("message_count_since_name", 0) < 3:
            return False
        return True
    return False
    
async def check_intent_override(db, user_input, user, session, classification, intrection):
    from app.services.thrum_router.phase_discovery import handle_discovery
    from app.services.thrum_router.phase_followup import handle_game_inquiry
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    # Sort by timestamp descending
    thrum_interactions = sorted(thrum_interactions, key=lambda x: x.timestamp, reverse=True)
    last_thrum_reply = thrum_interactions[0].content if thrum_interactions else ""
    
    if session.meta_data is None:
        session.meta_data = {}
    clarification_input = "NO"
    classification_intent = await classify_user_intent(user_input=user_input, session=session, db=db, last_thrum_reply=last_thrum_reply)

    if not classification_intent.get("Other") or not classification_intent.get("Other_Question") or not classification_intent.get("Inquire_About_Game") or not classification_intent.get("Give_Info") or not classification_intent.get("Request_Specific_Game"):
        session.meta_data["already_greet"] = True
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    turn_index = len(user_interactions)
         # Initialize metadata if needed
    if session.meta_data is None:
        session.meta_data = {}
    # Check if this is first contact and no intro done
    intro_done = session.meta_data.get("intro_done", False)
    print('******************turn_index***********************',turn_index)
    # First-touch generative onboarding
    if turn_index == 1 and not intro_done:
        first_class = await classify_first_message(user_input)
        print(f"First message classification: {first_class}???????????????????????")
        prompt = await build_onboarding_prompt(session,user_input, first_class)
        print(f"Onboarding prompt for :>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> {prompt}")
        session.meta_data["intro_done"] = True
        session.meta_data["already_greet"] = True
        session.discovery_questions_asked += 1
        session.phase = PhaseEnum.INTRO
        db.commit()
        return prompt
    # Second-turn depth nudge for thin replies
    if turn_index == 2 and await is_thin_reply(user_input) and not session.meta_data.get("nudge_sent", False):
        nudge_prompt = await build_depth_nudge_prompt(user_input)
        session.discovery_questions_asked += 1
        session.phase = PhaseEnum.DISCOVERY
        db.commit()
        session.meta_data["nudge_sent"] = True
        return nudge_prompt
    
    #check for whether to ask question or not
    if session.meta_data.get('liked_followup',False) and (classification_intent.get("Other") or classification_intent.get("Other_Question") or classification_intent.get("Phase_Discovery") or classification_intent.get("Give_Info")):
        session.meta_data['liked_followup'] = False
        if session.meta_data.get('give_name',False) and user.name is not None:
            session.meta_data['give_name'] = False
            prompt = LIKED_FOLLOWUP[0]
            user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT)
            return user_prompt
        else:
            session.meta_data['give_name'] = False
            prompt = LIKED_FOLLOWUP[1]
            user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT)
            return user_prompt

     # Classify the user's intent based on their input
    if classification_intent.get("Phase_Discovery") or classification_intent.get("Give_Info") :
        clarification_input = await classify_input_ambiguity(db=db ,session=session,user=user,user_input=user_input, last_thrum_reply=last_thrum_reply)

        print(f"clarification_input : {clarification_input} +++++++++++++++++++++=")
        ambiguity_clarification = session.meta_data["ambiguity_clarification"] if "ambiguity_clarification" in session.meta_data else False
        if clarification_input == "YES" and not ambiguity_clarification and session.discovery_questions_asked <2:
            if classification.get("genre") or classification.get("preferred_keywords") or classification.get("favourite_games") or classification.get("gameplay_elements"):
                intrection.classification = {"input" : classification, "intent" : classification_intent, "clarification": clarification_input}
                session.phase = PhaseEnum.DISCOVERY
                db.commit()
                return await ask_ambiguity_clarification(db=db, session=session, user_input=user_input, classification=classification)
            
    intrection.classification = {"input" : classification, "intent" : classification_intent, "clarification": clarification_input}
    session.meta_data["ambiguity_clarification"] = False
    db.commit()
    trigger_referral = await should_trigger_referral(session=session,classification_intent=classification_intent)

    if trigger_referral:
        session.meta_data["ask_for_rec_friend"] = False
        session.phase = PhaseEnum.DISCOVERY
        return await share_thrum_ping(session)

    if classification_intent.get("Low_Effort_Response"):
        session.phase = PhaseEnum.DISCOVERY
        return await generate_low_effort_response(session)
    # Check if the user is in the discovery phase
    elif classification_intent.get("Phase_Discovery"):
        session.phase = PhaseEnum.DISCOVERY
        return await handle_discovery(db=db, session=session, user=user,user_input=user_input,classification=classification)
    
    # Handle rejection of recommendation
    elif classification_intent.get("Reject_Recommendation"):
        session.phase = PhaseEnum.DISCOVERY
        return await handle_reject_Recommendation(db, session, user, classification=classification,user_input=user_input)

    # Handle request for quick game recommendation
    elif classification_intent.get("Request_Quick_Recommendation"):
        session.phase = PhaseEnum.DELIVERY
        return await deliver_game_immediately(db, user, session,user_input=user_input, classification=classification)

    # Handle user inquiry about a game
    elif classification_intent.get("Inquire_About_Game"):
        session.phase = PhaseEnum.FOLLOWUP
        return await handle_game_inquiry(db, user, session, user_input, classification)

    # Handle information provided by the user
    elif classification_intent.get("Give_Info"):
        session.phase = PhaseEnum.DISCOVERY
        return await handle_discovery(db=db, session=session, user=user,user_input=user_input,classification=classification)

    # Handle user opting out
    elif classification_intent.get("Opt_Out"):
        session.phase = PhaseEnum.ENDING
        return await handle_ending(session)

    # Handle user confirming a game recommendation
    elif classification_intent.get("Confirm_Game"):
        session.phase = PhaseEnum.CONFIRMATION
        return await handle_confirmed_game(db, user, session, classification)
    
    elif classification_intent.get("want_to_share_friend"):
        session.phase = PhaseEnum.DISCOVERY
        if session.shared_with_friend:
            return await handle_other_input(db, user, session, user_input)
        else:
            session.shared_with_friend = True
            session.phase = PhaseEnum.DISCOVERY
            db.commit()
            return await share_thrum_message(session)
    
    elif classification_intent.get("Greet"):
        session.phase = PhaseEnum.INTRO
        return await handle_intro(db,session)

    # Handle cases where user input doesn't match any predefined intent
    elif classification_intent.get("Other") or classification_intent.get("Other_Question"):
        session.phase = PhaseEnum.DISCOVERY
        return await handle_other_input(db, user, session, user_input)
    
    elif classification_intent.get("Bot_Error_Mentioned"):
        session.phase = PhaseEnum.DISCOVERY
        response = (
            "the Thrum encounters an error or loses track of the conversation, it should first apologize to the user in a friendly and empathetic manner. After the apology, the bot should invite the user to re-engage by asking for clarification on what they are looking for. The tone should remain light, open, and non-repetitive, ensuring the user feels comfortable guiding the conversation forward.Most Most Most importent is reply is must look like humanly - Not robotic"
        )
        return response
    
    elif classification_intent.get("About_FAQ"):
        session.phase = PhaseEnum.DISCOVERY
        return await dynamic_faq_gpt(session, user_input)

    elif classification_intent.get("Request_Similar_Game"):
        session.phase = PhaseEnum.DELIVERY
        return await diliver_similar_game(db, user, session,user_input=user_input,classification=classification)
    
    elif classification_intent.get("Request_Specific_Game"):
        session.phase = PhaseEnum.DELIVERY
        return await diliver_particular_game(db, user, session, user_input, classification)
    
    # Default handling if no specific intent is detected
    return None
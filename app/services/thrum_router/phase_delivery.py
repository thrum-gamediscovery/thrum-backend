from app.services.game_recommend import game_recommendation
from app.services.input_classifier import have_to_recommend
from app.services.session_memory import format_game_output
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.session import Session  
from sqlalchemy.orm import Session as DBSession  
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.utils.whatsapp import send_whatsapp_message
import openai

async def get_recommend(db, user, session):
    game, _ = await game_recommendation(db=db, user=user, session=session)
    if game:
        session.last_recommended_game = game["title"]
        session.phase = PhaseEnum.FOLLOWUP
        session.followup_triggered = True
    else:
        return "not game"
    # Optional: build user_context from session
    user_context = {
        "mood": session.exit_mood,
        "genre": getattr(session, "genre", None),
        "platform": session.platform_preference
    }
    return await format_game_output(session, game, user_context)

async def explain_last_game_match(session, user, user_input):
    """
    This function generates a personalized response explaining how the last recommended game matches the user's preferences.
    """
    # Fetch last Thrum reply and last recommended game
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else None
    last_game = session.game_recommendations[-1].game if session.game_recommendations else None
    
    # Construct the profile context from the session and user
    profile_context = {
        "name": user.name,
        "mood": session.exit_mood,
        "genre_interest": session.genre[-1] if session.genre else None,
        "platform": session.platform_preference[-1] if session.platform_preference else None
    }

    # Construct the system and user prompts for the model
    system_prompt = (
        "You are Thrum, a warm and playful game matchmaker. "
        "Your tone is cozy, human, and emoji-friendly. Never robotic. Never generic. "
        "Each reply should: (1) feel like part of a real conversation, (2) suggest a game *only if appropriate*, and (3) ask one soft follow-up. "
        "Never ask multiple questions at once. Never list features. Never say 'as an AI'. Never break character. "
        "Keep it under 25 words. Add 1–2 emojis that match the user's mood."
        "Make reply based on user's tone. You can use short forms if user is using that."
    )
    
    # Generate the user prompt with information about the user's feedback
    user_prompt = f"""
    User just said: "{user_input}"
    Your last message was: "{last_thrum_reply}"
    Last suggested game: "{last_game.title if last_game else 'None'}"

    User profile: {profile_context}

    Write Thrum’s reply:
    - Describe the last suggested game shortly based on user's last input.
    - Match the user's tone and mood.
    - Do not add name in reply.
    Keep it under 25 words. Add 2–3 emojis that match the tone.
    """
    
    # Use OpenAI's GPT model to generate the explanation response
    response = openai.ChatCompletion.create(
        model='gpt-4.1-mini',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.9
    )

    # Return the generated response content
    return response["choices"][0]["message"]["content"]

async def handle_delivery(db: DBSession, session, user, classification, user_input):
    """
    This function handles whether to recommend a new game or explain the last recommended game based on user feedback.
    """
    # Check if a new recommendation is needed based on user preferences and classification
    should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

    if should_recommend:
        # If a new recommendation is needed, get the recommendation
        recommendation_response = await get_recommend(user=user, db=db, session=session)
        return recommendation_response  # Return the new recommendation
    else:
        # If no new recommendation is needed, explain the last recommended game based on user feedback
        explanation_response = await explain_last_game_match(session=session, user=user, user_input=user_input)
        return explanation_response  # Return the explanation of the last game

    

async def recommend_game():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.awaiting_reply == True,
        Session.intent_override_triggered == True
    ).all()
    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        delay = timedelta(seconds=10)

        if now - s.last_thrum_timestamp > delay:
            reply = await get_recommend(db=db, session=s, user=user)
            await send_whatsapp_message(user.phone_number, reply)
            s.phase = PhaseEnum.FOLLOWUP
            # 🧠 Track nudge + potential coldness
            s.last_thrum_timestamp = now
            s.intent_override_triggered = False
        db.commit()
    db.close()

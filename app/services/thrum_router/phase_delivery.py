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
    genre = session.memory.get("last_genre")
    exclude = [session.memory.get("last_game_title")]

    game, _ = await game_recommendation(
        db=db,
        user=user,
        session=session
    )

    session.memory["last_game_title"] = game["title"]

    if game:
        session.last_recommended_game = game["title"]

    else:
        return "Hmm, I couldn’t find a perfect match — but here’s a solid one anyway! 💡"
    # Optional: build user_context from session
    user_context = {
        "mood": session.exit_mood,
        "genre": getattr(session, "genre", None),
        "platform": session.platform_preference
    }
    return await format_game_output(session, game, user_context)

async def explain_last_game_match(session):
    """
    This function generates a personalized response explaining how the last recommended game matches the user's preferences.
    """
    last_game = session.game_recommendations[-1].game if session.game_recommendations else None
    
    # Generate the user prompt with information about the user's feedback
    user_prompt = f"""
    
    Last suggested game: "{last_game.title if last_game else 'None'}"

    Write Thrum’s reply:
    - Describe the last suggested game shortly based on user's last input.
    - Match the user's tone and mood.
    - Do not add name in reply.
    Keep it under 25 words. Add 2–3 emojis that match the tone.
    """
    
    return user_prompt

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
        explanation_response = await explain_last_game_match(session=session)
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

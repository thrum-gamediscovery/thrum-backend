from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum
from sqlalchemy.orm import Session as DBSession
from app.services.dynamic_response_engine import generate_dynamic_response
from app.services.learning_engine import UserLearningProfile

async def handle_delivery(db: DBSession, session, user, classification, user_input):
    from app.services.intelligent_ai_engine import create_intelligent_ai
    
    # Get game recommendation
    game, _ = await game_recommendation(db=db, user=user, session=session)
    
    if game:
        session.last_recommended_game = game["title"]
        
        # Use intelligent AI to generate personalized recommendation
        ai = await create_intelligent_ai(user, session)
        
        game_data = {
            "title": game["title"],
            "description": game.get("description", ""),
            "genre": game.get("genre", []),
            "platforms": game.get("platforms", []),
            "game_vibes": game.get("game_vibes", []),
            "has_story": game.get("has_story", False)
        }
        
        # Generate intelligent recommendation with reasoning
        recommendation = await ai.generate_game_recommendation_with_reasoning(game_data)
        
        # Log recommendation in learning profile
        profile = UserLearningProfile(user, session)
        profile.log_feedback(mood=session.exit_mood or session.entry_mood)
        
        db.commit()
        
        return recommendation
    
    return await generate_dynamic_response(user, session, user_input, phase='no_game')

async def explain_last_game_match(session):
    user = session.user
    return await generate_dynamic_response(user, session, phase='explain')

async def recommend_game():
    from app.db.session import SessionLocal
    from datetime import datetime, timedelta
    from app.utils.whatsapp import send_whatsapp_message
    from app.db.models.session import Session
    
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
            reply = await generate_dynamic_response(user, s, phase='auto_recommend')
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.intent_override_triggered = False
        db.commit()
    db.close()
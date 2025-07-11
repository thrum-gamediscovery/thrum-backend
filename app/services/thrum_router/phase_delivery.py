from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum
from sqlalchemy.orm import Session as DBSession
from app.services.dynamic_response_engine import generate_dynamic_response

async def handle_delivery(db: DBSession, session, user, classification, user_input):
    # Get game recommendation
    game, _ = await game_recommendation(db=db, user=user, session=session)
    
    if game:
        session.last_recommended_game = game["title"]
        
        context = {
            'phase': 'recommendation',
            'user_input': user_input,
            'recommended_game': game["title"],
            'mood': session.exit_mood or session.entry_mood,
            'rejected_games': session.rejected_games or [],
            'platforms': game.get("platforms", []),
            'genre': game.get("genre", [])
        }
        
        return await generate_dynamic_response(context)
    
    context = {
        'phase': 'no_game',
        'user_input': user_input,
        'mood': session.exit_mood or session.entry_mood
    }
    
    return await generate_dynamic_response(context)

async def explain_last_game_match(session):
    context = {
        'phase': 'explain',
        'last_game': session.last_recommended_game,
        'interaction_count': len(session.interactions)
    }
    
    return await generate_dynamic_response(context)

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
            context = {
                'phase': 'auto_recommend',
                'last_game': s.last_recommended_game,
                'mood': s.exit_mood or s.entry_mood
            }
            reply = await generate_dynamic_response(context)
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.intent_override_triggered = False
        db.commit()
    db.close()
from app.tasks.followup import handle_followup_logic
from app.services.thrum_router.interrupt_logic import check_intent_override
from app.services.dynamic_response_engine import generate_dynamic_response

async def handle_followup(db, session, user, user_input, classification):
    override_reply = await check_intent_override(db=db, user_input=user_input, user=user, session=session, classification=classification)
    if override_reply:
        return override_reply
    
    # Check if should conclude
    ending_signals = ["thanks", "thank you", "got it", "perfect", "sounds good"]
    if any(signal in user_input.lower() for signal in ending_signals) or len(session.interactions) >= 6:
        context = {
            'phase': 'conclusion',
            'user_input': user_input,
            'last_game': session.last_recommended_game,
            'interaction_count': len(session.interactions)
        }
        return await generate_dynamic_response(context)
    
    return await handle_followup_logic(db=db, session=session, user=user, classification=classification, user_input=user_input)

async def ask_followup_que(session) -> str:
    context = {
        'phase': 'followup',
        'last_game': session.last_recommended_game,
        'interaction_count': len(session.interactions)
    }
    
    return await generate_dynamic_response(context)

async def get_followup():
    from app.db.session import SessionLocal
    from datetime import datetime, timedelta
    from app.utils.whatsapp import send_whatsapp_message
    from app.db.models.session import Session
    
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.awaiting_reply == True,
        Session.followup_triggered == True
    ).all()
    
    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        delay = timedelta(seconds=5)
        
        if now - s.last_thrum_timestamp > delay:
            reply = await ask_followup_que(s)
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.awaiting_reply = True
            s.followup_triggered = False    
        db.commit()
    db.close()

async def handle_game_inquiry(db, user, session, user_input: str) -> str:
    """Handle game inquiries dynamically"""
    game_id = session.meta_data.get("find_game")
    if not game_id:
        context = {
            'phase': 'no_game_found',
            'user_input': user_input
        }
        return await generate_dynamic_response(context)

    from app.db.models.game import Game
    from app.db.models.game_platforms import GamePlatform
    from app.db.models.game_recommendations import GameRecommendation
    
    game = db.query(Game).filter_by(game_id=game_id).first()
    if not game:
        context = {
            'phase': 'game_not_found',
            'user_input': user_input,
            'game_id': game_id
        }
        return await generate_dynamic_response(context)

    platform_rows = db.query(GamePlatform.platform).filter_by(game_id=game_id).all()
    platforms = ", ".join([p[0] for p in platform_rows]) if platform_rows else "multiple platforms"

    # Save recommendation
    game_rec = GameRecommendation(
        session_id=session.session_id,
        user_id=user.user_id,
        game_id=game.game_id,
        platform=None,
        mood_tag=None,
        accepted=None
    )
    db.add(game_rec)
    db.commit()
    
    session.last_recommended_game = game.title
    
    context = {
        'phase': 'game_inquiry',
        'user_input': user_input,
        'game_title': game.title,
        'game_description': game.description,
        'platforms': platforms,
        'genre': game.genre
    }
    
    return await generate_dynamic_response(context)
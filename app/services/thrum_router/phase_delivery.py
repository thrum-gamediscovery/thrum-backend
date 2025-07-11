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
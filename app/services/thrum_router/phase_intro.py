from app.db.models.enums import PhaseEnum
from app.services.dynamic_response_engine import generate_dynamic_response

async def handle_intro(session):
    context = {
        'phase': 'intro',
        'returning_user': session.meta_data.get("returning_user", False),
        'last_game': session.last_recommended_game,
        'interaction_count': len(session.interactions)
    }
    
    return await generate_dynamic_response(context)
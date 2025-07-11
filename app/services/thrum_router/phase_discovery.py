from app.services.session_memory import extract_discovery_signals, confirm_input_summary
from app.db.models.enums import PhaseEnum
from app.utils.error_handler import safe_call
from app.services.dynamic_response_engine import generate_dynamic_response

@safe_call("Let me find something perfect for you.")
async def handle_discovery(db, session, user, classification, user_input):
    session.phase = PhaseEnum.DELIVERY
    
    context = {
        'phase': 'discovery',
        'user_input': user_input,
        'interaction_count': len(session.interactions),
        'mood': session.exit_mood or session.entry_mood,
        'rejected_games': session.rejected_games or []
    }
    
    return await generate_dynamic_response(context)

async def handle_user_info(db, user, classification, session, user_input):
    context = {
        'phase': 'user_info',
        'user_input': user_input,
        'mood': session.exit_mood or session.entry_mood
    }
    
    return await generate_dynamic_response(context)

async def handle_other_input(db, user, session, user_input: str) -> str:
    context = {
        'phase': 'other',
        'user_input': user_input,
        'interaction_count': len(session.interactions)
    }
    
    return await generate_dynamic_response(context)
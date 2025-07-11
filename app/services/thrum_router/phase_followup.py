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
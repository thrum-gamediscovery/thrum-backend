from app.services.session_memory import extract_discovery_signals, confirm_input_summary
from app.db.models.enums import PhaseEnum
from app.utils.error_handler import safe_call
from app.services.dynamic_response_engine import generate_dynamic_response
from app.services.learning_engine import UserLearningProfile

@safe_call("Let me find something perfect for you.")
async def handle_discovery(db, session, user, classification, user_input):
    # Update user preferences based on input
    profile = UserLearningProfile(user, session)
    
    # Extract info from user input and update profile
    await _extract_and_update_preferences(user_input, profile, db)
    
    # Generate natural discovery response
    return await generate_dynamic_response(user, session, user_input, phase='discovery')

async def _extract_and_update_preferences(user_input, profile, db):
    from datetime import datetime
    from sqlalchemy.orm.attributes import flag_modified
    """Use AI to intelligently extract preferences from user input"""
    from app.services.intelligent_ai_engine import create_intelligent_ai
    
    # Create AI instance for intelligent analysis
    ai = await create_intelligent_ai(profile.user, profile.session)
    
    # Analyze user input intelligently
    analysis = await ai.analyze_user_intent(user_input)
    
    # Update preferences based on AI analysis
    if analysis.get('mood'):
        profile.update_preferences(mood=analysis['mood'])
    
    if analysis.get('platform'):
        profile.update_preferences(platform=analysis['platform'])
    
    if analysis.get('genre_interest'):
        # Add to genre preferences
        today = datetime.utcnow().date().isoformat()
        if not profile.user.genre_prefs:
            profile.user.genre_prefs = {}
        profile.user.genre_prefs.setdefault(today, []).append(analysis['genre_interest'])
        flag_modified(profile.user, "genre_prefs")
    
    if analysis.get('game_mentioned'):
        # Store mentioned game for context
        profile.session.meta_data = profile.session.meta_data or {}
        profile.session.meta_data['mentioned_game'] = analysis['game_mentioned']
        flag_modified(profile.session, "meta_data")
    
    db.commit()

async def handle_user_info(db, user, classification, session, user_input):
    return await generate_dynamic_response(user, session, user_input, phase='discovery')

async def handle_other_input(db, user, session, user_input: str) -> str:
    return await generate_dynamic_response(user, session, user_input, phase='other')
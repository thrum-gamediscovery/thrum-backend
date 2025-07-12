from app.services.session_memory import extract_discovery_signals, confirm_input_summary
from app.db.models.enums import PhaseEnum
from app.utils.error_handler import safe_call
from app.services.dynamic_response_engine import generate_dynamic_response
from app.services.learning_engine import UserLearningProfile

@safe_call("Let me find something perfect for you.")
async def handle_discovery(db, session, user, classification, user_input):
    profile = UserLearningProfile(user, session)
    
    # Extract and update preferences
    await _extract_and_update_preferences(user_input, profile, db)
    
    # Generate interactive discovery response
    response = await generate_dynamic_response(user, session, user_input, phase='discovery')
    
    # Add interactive follow-ups based on what we learned
    interaction_count = len(session.interactions)
    
    if session.exit_mood and not user.platform_prefs and interaction_count < 4:
        response += f"\n\nPerfect {session.exit_mood} vibes! What do you usually play on? 🎮"
    elif user.platform_prefs and not session.exit_mood:
        response += "\n\nNice setup! What's your current mood - chill, hyped, or something else? 🌈"
    elif interaction_count > 3 and not user.genre_prefs:
        response += "\n\nWhat type of games usually grab you? Action, puzzles, stories? 🤔"
    
    return response

async def _extract_and_update_preferences(user_input, profile, db):
    """Extract preferences and update profile with interactive feedback"""
    from datetime import datetime
    from sqlalchemy.orm.attributes import flag_modified
    
    input_lower = user_input.lower()
    today = datetime.utcnow().date().isoformat()
    
    # Quick mood detection
    mood_map = {
        'chill': ['chill', 'relax', 'calm', 'peaceful'],
        'hyped': ['hyped', 'excited', 'pumped', 'energetic'],
        'creative': ['creative', 'build', 'craft', 'design'],
        'story': ['story', 'narrative', 'emotional']
    }
    
    for mood, keywords in mood_map.items():
        if any(word in input_lower for word in keywords):
            profile.session.exit_mood = mood
            break
    
    # Platform detection
    platform_map = {
        'PC': ['pc', 'computer', 'steam'],
        'Mobile': ['mobile', 'phone', 'android', 'ios'],
        'Switch': ['switch', 'nintendo'],
        'PlayStation': ['ps4', 'ps5', 'playstation'],
        'Xbox': ['xbox']
    }
    
    for platform, keywords in platform_map.items():
        if any(word in input_lower for word in keywords):
            if not profile.user.platform_prefs:
                profile.user.platform_prefs = {}
            profile.user.platform_prefs.setdefault(today, []).append(platform)
            flag_modified(profile.user, "platform_prefs")
            break
    
    # Genre detection
    genre_keywords = ['puzzle', 'action', 'rpg', 'adventure', 'strategy', 'simulation']
    for genre in genre_keywords:
        if genre in input_lower:
            if not profile.user.genre_prefs:
                profile.user.genre_prefs = {}
            profile.user.genre_prefs.setdefault(today, []).append(genre)
            flag_modified(profile.user, "genre_prefs")
            break
    
    db.commit()

async def handle_user_info(db, user, classification, session, user_input):
    response = await generate_dynamic_response(user, session, user_input, phase='discovery')
    
    # Add engagement booster for vague responses
    if len(user_input) < 10:
        response += "\n\nTell me more! What's got you in the mood to game today? 😊"
    
    return response

async def handle_other_input(db, user, session, user_input: str) -> str:
    response = await generate_dynamic_response(user, session, user_input, phase='other')
    
    # Redirect to discovery if conversation is drifting
    if len(session.interactions) > 2 and not session.exit_mood:
        response += "\n\nLet's find you something awesome to play! What's your vibe right now? 🎯"
    
    return response
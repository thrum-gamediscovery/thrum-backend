"""
Context validation and smart response handling.
"""

from app.services.response_tracker import ResponseTracker

def validate_user_context(session, classification):
    """Validate if we have enough context for recommendations"""
    
    # Get current session data
    mood = session.exit_mood or session.entry_mood
    genre = session.genre[-1] if session.genre else None
    platform = session.platform_preference[-1] if session.platform_preference else None
    
    # Get new data from classification
    new_mood = classification.get('mood') if classification else None
    new_genre = classification.get('genre') if classification else None
    new_platform = classification.get('platform_pref') if classification else None
    
    context = {
        'mood': mood or new_mood,
        'genre': genre or new_genre,
        'platform': platform or new_platform
    }
    
    return context

def should_ask_for_context(context):
    """Check if we need more context before recommending"""
    filled_fields = sum(1 for v in context.values() if v and v != "None")
    return filled_fields < 2

def generate_context_request(missing_context, session):
    """Generate request for missing context without repetition"""
    recent_responses = ResponseTracker.get_recent_responses(session)
    
    if 'genre' in missing_context and 'platform' in missing_context:
        base_response = "What type of games do you like and what do you play on?"
    elif 'genre' in missing_context:
        base_response = "What genre are you in the mood for?"
    elif 'platform' in missing_context:
        base_response = "What platform do you want to play on?"
    elif 'mood' in missing_context:
        base_response = "What's your gaming mood right now?"
    else:
        base_response = "Tell me more about what you're looking for!"
    
    # Check for repetition
    if ResponseTracker.is_repetitive(base_response, recent_responses):
        return ResponseTracker.add_variation(base_response)
    
    return base_response

def handle_no_games_found(session, preferences):
    """Handle when no games match user preferences"""
    recent_responses = ResponseTracker.get_recent_responses(session)
    
    base_responses = [
        f"No {preferences.get('genre', 'games')} games for {preferences.get('platform', 'that platform')} in my database right now.",
        f"That combo doesn't exist yet! Want to try different genres or platforms?",
        f"Nothing matches that exact combo. How about we explore other options?"
    ]
    
    for response in base_responses:
        if not ResponseTracker.is_repetitive(response, recent_responses):
            return response
    
    return "Let's try a different approach - what else interests you?"
"""
Validates if enough user context exists before making recommendations.
"""

def should_recommend_game(session, user, classification) -> bool:
    """Check if we have enough context to make a good recommendation"""
    
    # Get current preferences
    mood = session.exit_mood or session.entry_mood
    genre = session.genre[-1] if session.genre else None
    platform = session.platform_preference[-1] if session.platform_preference else None
    
    # Check classification for new info
    new_mood = classification.get('mood') if classification else None
    new_genre = classification.get('genre') if classification else None
    new_platform = classification.get('platform_pref') if classification else None
    
    # Count available context
    context_count = 0
    if mood or new_mood:
        context_count += 1
    if genre or new_genre:
        context_count += 1
    if platform or new_platform:
        context_count += 1
    
    # Need at least 2 pieces of context
    return context_count >= 2

def get_missing_context(session, classification) -> list:
    """Get list of missing context needed for recommendation"""
    missing = []
    
    mood = session.exit_mood or session.entry_mood or classification.get('mood')
    genre = session.genre[-1] if session.genre else classification.get('genre')
    platform = session.platform_preference[-1] if session.platform_preference else classification.get('platform_pref')
    
    if not mood:
        missing.append('mood')
    if not genre:
        missing.append('genre')
    if not platform:
        missing.append('platform')
    
    return missing
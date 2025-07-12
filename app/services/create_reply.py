import random
from datetime import datetime
from app.services.input_classifier import classify_user_input
from app.services.game_recommend import game_recommendation
from app.utils.error_handler import safe_call
from sqlalchemy.orm.attributes import flag_modified

# Intro variations for natural conversation
INTRO_VARIATIONS = [
    "Hey 👋 Nice to meet you. I'm Thrum – I help people find games that actually fit their mood. Want a quick recommendation? No pressure.",
    "Hey 👋 I'm Thrum – I help people find games that match their mood. Want a quick recommendation? Totally chill if not.",
    "Hi there 👋 I'm Thrum. I find games that fit how you're feeling right now. Want me to suggest something? No strings attached.",
    "Hey 👋 I'm Thrum – I drop game recs based on your vibe, not just genres. Want a quick suggestion?"
]

@safe_call()
async def generate_thrum_reply(db, user, session, user_input: str) -> str:
    """Main Thrum conversation engine following the natural flow from examples"""
    
    # Classify user input to understand intent and preferences
    classification = await classify_user_input(session=session, user_input=user_input)
    
    # Update user profile with extracted info
    await _update_user_profile(db, user, session, classification)
    
    # Determine conversation flow based on context
    return await _generate_contextual_reply(db, user, session, user_input, classification)

async def _generate_contextual_reply(db, user, session, user_input: str, classification: dict) -> str:
    """Generate contextual reply based on conversation state"""
    
    # First interaction - introduce Thrum
    if len(session.interactions) == 0:
        return random.choice(INTRO_VARIATIONS)
    
    # Handle greetings
    if classification.get('Greet'):
        return random.choice(INTRO_VARIATIONS)
    
    # Handle direct game requests
    if classification.get('Request_Quick_Recommendation') or _should_recommend_game(user, session, user_input):
        return await _handle_game_recommendation(db, user, session, classification)
    
    # Handle game confirmations/rejections
    if classification.get('Confirm_Game'):
        return await _handle_game_confirmation(user, session)
    
    if classification.get('Reject_Recommendation'):
        return await _handle_game_rejection(db, user, session)
    
    # Handle information gathering
    if classification.get('Give_Info') or _is_providing_preferences(classification):
        return await _handle_preference_gathering(db, user, session, classification)
    
    # Handle opt out
    if classification.get('Opt_Out'):
        return _handle_opt_out()
    
    # Default discovery flow
    return await _handle_discovery_conversation(db, user, session, user_input, classification)

def _should_recommend_game(user, session, user_input: str) -> bool:
    """Determine if we should recommend a game based on context"""
    input_lower = user_input.lower()
    
    # Direct requests
    direct_requests = ['hit me', 'sure', 'yeah sure', 'go for it', 'recommend', 'suggest']
    if any(phrase in input_lower for phrase in direct_requests):
        return True
    
    # Has enough context for recommendation
    has_mood = bool(session.exit_mood or user.mood_tags)
    has_platform = bool(user.platform_prefs or session.platform_preference)
    interaction_count = len(session.interactions)
    
    # Recommend after gathering some info
    return interaction_count >= 2 and (has_mood or has_platform)

async def _handle_game_recommendation(db, user, session, classification: dict) -> str:
    """Handle game recommendation with natural conversation"""
    
    # Get game recommendation
    game_data, confidence = await game_recommendation(db=db, user=user, session=session)
    
    if not game_data:
        return "Let me think... What kind of mood are you in today? Chill? Action-packed? Something creative?"
    
    # Store recommendation
    session.last_recommended_game = game_data.get('title')
    db.commit()
    
    # Generate natural recommendation response based on conversation examples
    title = game_data.get('title')
    platforms = game_data.get('platforms', [])
    user_platform = session.platform_preference or (user.platform_prefs.get(datetime.utcnow().date().isoformat(), [])[-1] if user.platform_prefs else None)
    
    # Natural recommendation patterns from examples
    if not user.name:
        # First recommendation - introduce game and ask follow-up
        responses = [
            f"Cool. Just dropping in with a quick game rec – {title}. You've probably heard of it: wordless, beautiful, short enough to finish in one sitting.\n\nBut out of curiosity – are you in the mood for something relaxing like this, or more high-energy today?",
            f"Alright – if you're in the mood for something punchy, {title} has a killer campaign and smooth movement. You feeling like something high-energy today?",
            f"Nice. Here's a quick one: {title}. It's cute, short, and really kind. Ever heard of it?"
        ]
        return random.choice(responses)
    
    # Follow-up recommendations with more context
    if user_platform:
        responses = [
            f"Perfect. Loads of good fits there. Here's another mellow one: {title}. It's cute, short, and really kind. Ever heard of it?",
            f"Nice – {user_platform} has loads of good options. Here's something that fits: {title}. Want me to send a link?",
            f"Got it. {title} is great for switching off without feeling empty. Just movement and music."
        ]
    else:
        responses = [
            f"Here's something that fits: {title}. Check it out.\n\nQuick one, just so I don't send anything unplayable: what do you usually play on?",
            f"Match incoming: {title}. It's worth a look.\n\nJust curious—do you ever play on mobile when you're not at your desk? Or stick to PC?",
            f"One last one for now: {title}. Short, tactile, thoughtful. Want me to send a steam link?"
        ]
    
    return random.choice(responses)

async def _handle_preference_gathering(db, user, session, classification: dict) -> str:
    """Handle preference gathering with natural follow-ups"""
    
    # Extract what they shared
    mood = classification.get('mood')
    platform = classification.get('platform_pref')
    name = classification.get('name')
    
    responses = []
    
    if name and name != 'None':
        responses.append(f"Nice to meet you properly, {name} 🙌")
        user.name = name
        flag_modified(user, 'name')
    
    if mood and mood != 'None':
        if mood.lower() == 'relaxing' or mood.lower() == 'chill':
            responses.append(f"Good call. {mood} is great for switching off without feeling empty.")
        else:
            responses.append(f"Got it. {mood.title()} vibes – I can work with that.")
    
    if platform and platform != 'None':
        responses.append(f"Perfect. {platform} has loads of good fits there.")
    
    # Add natural follow-up questions based on conversation examples
    if not user.name and len(session.interactions) > 2:
        responses.append("Also, I can remember your name for next time if you like – want me to?")
    elif not session.exit_mood and not user.mood_tags:
        responses.append("You mentioned unwinding—do you usually lean toward games with a bit of story, or more gameplay-focused stuff?")
    elif not user.platform_prefs and not session.platform_preference:
        responses.append("Quick one, just so I don't send anything unplayable: what do you usually play on?")
    elif len(session.interactions) > 3:
        # Ask about play time like in examples
        responses.append("Oh, and when do you usually find time to play? Evening? Weekend afternoons?")
    else:
        # Ready for recommendation
        return await _handle_game_recommendation(db, user, session, classification)
    
    db.commit()
    return "\n\n".join(responses)

async def _handle_discovery_conversation(db, user, session, user_input: str, classification: dict) -> str:
    """Handle general discovery conversation"""
    
    # Natural conversation responses based on context
    if len(user_input) < 5:
        return "Tell me more! What's got you in the mood to game today? 😊"
    
    # Ask for missing key info
    if not session.exit_mood and not user.mood_tags:
        return "Gotcha. You want something chill, wild, or surprising?"
    
    if not user.platform_prefs and not session.platform_preference:
        return "Nice. What do you usually play on? PC? Mobile? Console?"
    
    # Default encouraging response
    return "I'm getting a sense of your style. Want me to find something that fits?"

async def _handle_game_confirmation(user, session) -> str:
    """Handle when user confirms interest in recommended game"""
    game_title = session.last_recommended_game or "that game"
    
    # Natural confirmation responses from examples
    responses = [
        f"Awesome! Here's the steam link [Steam link: {game_title}]\n\nWhen do you usually get your game time in? Evenings? Late night?",
        f"Cool. Here's the steam link [Steam link: {game_title}]\n\nLet me know if {game_title} clicks. If not, I've got other curveballs ready to throw your way.",
        f"🎬 [YouTube link: {game_title} trailer]\n\nTotally different vibe, but a fun mental reset between sessions."
    ]
    
    return random.choice(responses)

async def _handle_game_rejection(db, user, session) -> str:
    """Handle when user rejects recommended game"""
    
    # Natural rejection handling from examples
    responses = [
        "Fair enough – not everything clicks. Mind if I ask what kind of shooters do work for you?",
        "Understandable—but this one's more like strategy meets deckbuilding, not like Yu-Gi-Oh levels of lore 😅\n\nWant to take a peek or prefer something else entirely?",
        "Got it. That's super helpful. You're not just an FPS fan – you're a Fortnite fan 🔥\n\nOk, no more shooter suggestions—how do you feel about something completely different to cool down between matches?"
    ]
    
    return random.choice(responses)

def _handle_opt_out() -> str:
    """Handle when user wants to end conversation"""
    # Natural opt-out responses from examples
    responses = [
        "Alright, I'll stop here for now—but I've got more puzzle gems whenever you're ready 🧩",
        "Got more recs when you're ready – chill, weird, epic, whatever you're into 💬 Just shout.",
        "Totally fine. Come back later. I'll be here, and maybe smarter."
    ]
    
    return random.choice(responses)

def _is_providing_preferences(classification: dict) -> bool:
    """Check if user is providing preference information"""
    return any([
        classification.get('mood') and classification.get('mood') != 'None',
        classification.get('platform_pref') and classification.get('platform_pref') != 'None',
        classification.get('genre') and classification.get('genre') != 'None',
        classification.get('name') and classification.get('name') != 'None'
    ])

async def _update_user_profile(db, user, session, classification: dict):
    """Update user profile with classified information"""
    today = datetime.utcnow().date().isoformat()
    
    # Update mood
    if classification.get('mood') and classification.get('mood') != 'None':
        mood = classification.get('mood')
        if not user.mood_tags:
            user.mood_tags = {}
        user.mood_tags[today] = mood
        session.exit_mood = mood
        flag_modified(user, 'mood_tags')
    
    # Update platform preference
    if classification.get('platform_pref') and classification.get('platform_pref') != 'None':
        platform = classification.get('platform_pref')
        if not user.platform_prefs:
            user.platform_prefs = {}
        user.platform_prefs.setdefault(today, []).append(platform)
        session.platform_preference = platform
        flag_modified(user, 'platform_prefs')
    
    # Update genre preference
    if classification.get('genre') and classification.get('genre') != 'None':
        genre = classification.get('genre')
        if not user.genre_prefs:
            user.genre_prefs = {}
        user.genre_prefs.setdefault(today, []).append(genre)
        flag_modified(user, 'genre_prefs')
    
    # Update name
    if classification.get('name') and classification.get('name') != 'None':
        user.name = classification.get('name')
    
    db.commit()

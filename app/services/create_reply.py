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
    
    # Handle unusual/random chat and negative responses
    return await _handle_unusual_or_negative_input(db, user, session, user_input, classification)

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

async def _handle_unusual_or_negative_input(db, user, session, user_input: str, classification: dict) -> str:
    """Handle unusual, random, or negative responses naturally"""
    input_lower = user_input.lower().strip()
    
    # Handle negative responses
    negative_patterns = ['no', 'nah', 'not really', 'not interested', 'boring', 'whatever', 'meh', 'idk', 'dunno']
    if any(pattern in input_lower for pattern in negative_patterns):
        return await _handle_negative_response(db, user, session, user_input)
    
    # Handle random/unusual chat
    random_patterns = ['lol', 'haha', 'wtf', 'what', 'huh', 'ok', 'cool', 'nice', 'weird']
    if any(pattern in input_lower for pattern in random_patterns) or len(user_input) < 5:
        return await _handle_random_chat(db, user, session, user_input)
    
    # Handle off-topic questions
    question_patterns = ['how are you', 'what are you', 'who made you', 'where are you from']
    if any(pattern in input_lower for pattern in question_patterns):
        return await _handle_off_topic_questions(db, user, session, user_input)
    
    # Default discovery conversation
    return await _handle_discovery_conversation(db, user, session, user_input, classification)

async def _handle_negative_response(db, user, session, user_input: str) -> str:
    """Handle negative or dismissive responses"""
    responses = [
        "No worries at all! Sometimes it's just not the right moment. I'm here whenever you feel like finding something cool to play 🎮",
        "Totally fair. Gaming moods come and go. Hit me up when you're feeling it – I'll have something good ready 😊",
        "All good! Maybe you're just not in the gaming headspace right now. Come back whenever – no pressure 👍",
        "Fair enough. Not every day is a gaming day. I'll be here when you want to discover something awesome 🌟"
    ]
    return random.choice(responses)

async def _handle_random_chat(db, user, session, user_input: str) -> str:
    """Handle random or short responses"""
    input_lower = user_input.lower().strip()
    
    if input_lower in ['lol', 'haha']:
        responses = [
            "Haha glad I could get a laugh! So... games? Or are we just vibing? 😄",
            "😂 Alright, now that we're warmed up – want me to find you something fun to play?",
            "Haha nice! Ok but seriously, what's your gaming vibe today?"
        ]
    elif input_lower in ['ok', 'cool', 'nice']:
        responses = [
            "Cool cool. So what's got you in the mood to game today?",
            "Nice! Alright, let's find you something perfect. What's your current vibe?",
            "Ok awesome. Tell me – chill games or something more intense?"
        ]
    elif input_lower in ['what', 'huh', 'wtf']:
        responses = [
            "Haha I know, I'm a bit different! I'm basically a game matchmaker. Tell me your mood and I'll find the perfect game 🎯",
            "Yeah I get that reaction a lot 😅 I help people find games that actually match how they're feeling. Want to try it?",
            "I'm Thrum! Think of me as your personal game curator. What kind of vibe are you going for today?"
        ]
    else:
        responses = [
            "Tell me more! What's got you in the mood to game today? 😊",
            "I'm getting curious about your gaming style. What usually grabs you?",
            "Interesting! So what kind of games usually click with you?"
        ]
    
    return random.choice(responses)

async def _handle_off_topic_questions(db, user, session, user_input: str) -> str:
    """Handle off-topic questions naturally"""
    input_lower = user_input.lower()
    
    if 'how are you' in input_lower:
        responses = [
            "I'm doing great, thanks for asking! Always excited to help people find their next favorite game. How about you – what's your gaming mood today?",
            "Pretty good! Just here matching people with games that fit their vibe. Speaking of which, what's yours today?"
        ]
    elif 'what are you' in input_lower or 'who made you' in input_lower:
        responses = [
            "I'm Thrum – think of me as your personal game discovery buddy! I help people find games that actually match their mood, not just popular stuff. Want to try it?",
            "I'm a game recommendation bot, but not the boring kind! I actually listen to how you're feeling and find games that fit. What's your vibe today?"
        ]
    else:
        responses = [
            "Haha that's a good question, but I'm way better at talking about games! What kind of mood are you in for gaming?",
            "Interesting question! But let's talk about something I'm really good at – finding you the perfect game. What's your vibe?"
        ]
    
    return random.choice(responses)

async def _handle_discovery_conversation(db, user, session, user_input: str, classification: dict) -> str:
    """Handle general discovery conversation"""
    
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
    
    # Track rejection count for adaptive responses
    session.game_rejection_count = getattr(session, 'game_rejection_count', 0) + 1
    rejection_count = session.game_rejection_count
    
    if rejection_count == 1:
        # First rejection - gentle and curious
        responses = [
            "Fair enough – not everything clicks. Mind if I ask what missed the mark? The style, pace, or something else?",
            "No worries! What usually grabs your attention in games?",
            "Got it. That's actually helpful – what kind of games do work for you?"
        ]
    elif rejection_count == 2:
        # Second rejection - more understanding, different approach
        responses = [
            "Alright, seems I'm not nailing your vibe yet. Want to try something completely different?",
            "Ok I'm clearly missing something here 😅 Help me out – what's your ideal gaming experience?",
            "Fair point. Let me switch gears entirely. What's a game you actually loved recently?"
        ]
    else:
        # Multiple rejections - wildcard approach
        responses = [
            "Wildcard time! I've got something totally out of left field that might surprise you. Want to risk it?",
            "Alright, I'm going full random mode. Sometimes the best games are the ones you'd never expect to like 🎲",
            "Ok new strategy – tell me about literally anything you're into (movies, music, whatever) and I'll find a game connection 🤔"
        ]
    
    db.commit()
    return random.choice(responses)

def _handle_opt_out() -> str:
    """Handle when user wants to end conversation"""
    # Natural opt-out responses from examples
    responses = [
        "Alright, I'll stop here for now—but I've got more gems whenever you're ready 🧩",
        "Got more recs when you're ready – chill, weird, epic, whatever you're into 💬 Just shout.",
        "Totally fine. Come back later. I'll be here, and maybe smarter.",
        "No problem! Hit me up whenever you're in the mood for something new 🎮",
        "All good. Maybe it just wasn't the day for it. Come back when you're ready – I'm still learning! 😊"
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

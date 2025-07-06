import openai
import os
import random

openai.api_key = os.getenv("OPENAI_API_KEY")

async def generate_natural_response(user_input: str, session, user, context: dict = None) -> str:
    """
    Generate memory-aware, natural responses based on conversation history
    """
    name = getattr(user, "name", None) if user else None
    interaction_count = len(session.interactions) if session and session.interactions else 0
    
    # Get conversation history for context
    recent_history = []
    if session and session.interactions:
        recent_history = [interaction.content for interaction in session.interactions[-3:]]
    
    # Build contextual acknowledgments
    if "relaxing" in user_input.lower() or "chill" in user_input.lower():
        return "Good call. Perfect for switching off without feeling empty."
    elif "pc" in user_input.lower():
        return "Perfect. Loads of good fits there."
    elif "mobile" in user_input.lower():
        return "Gotcha. Handy to know for those bite-sized suggestions."
    elif "don't like" in user_input.lower() or "hate" in user_input.lower():
        return "Fair enough — not everything clicks."
    elif "fortnite" in user_input.lower():
        return "Respect. Fortnite's kind of its own genre at this point 😄"
    
    # Context-aware response generation
    system_prompt = f"""
You are Thrum — a casual, friendly game recommender who remembers conversations.

Personality:
- Talk like a friend, not a bot
- Use casual acknowledgments: "Cool", "Nice", "Gotcha", "Fair enough"
- Keep responses under 2 lines
- Use 1-2 emojis max
- Build on what the user just said

Conversation context:
- User's name: {name or "not provided"}
- Interaction count: {interaction_count}
- Recent messages: {recent_history[-2:] if recent_history else 'none'}
- User's mood: {session.exit_mood if session else 'unknown'}
- Platform: {session.platform_preference[-1] if session and session.platform_preference else 'unknown'}

Respond naturally to: "{user_input}"

Examples of your style:
- "Cool. Just dropping in with a quick game rec — Journey."
- "Good call. Perfect for switching off without feeling empty."
- "Gotcha. Handy to know for those bite-sized suggestions."
- "Fair enough — not everything clicks."
"""

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4.1-mini",
            temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_input}
            ]
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Natural response fallback: {e}")
        return "Cool — let me find something good for you."

async def generate_game_recommendation_response(game: dict, user_context: dict = None) -> str:
    """
    Generate natural game recommendation responses like the examples
    """
    title = game.get("title", "Unknown Game")
    description = game.get("description", "")
    
    # Natural recommendation templates based on examples
    templates = [
        f"Cool. Just dropping in with a quick game rec — {title}. {description[:50]}...\n\nBut out of curiosity — are you in the mood for something relaxing like this, or more high-energy today?",
        f"Alright — if you're in the mood for something punchy, {title}. {description[:50]}...\n\nYou feeling like something high-energy today?",
        f"Nice 😁\n\nLet's start with something different — have you ever tried {title}? {description[:50]}...\n\nFeeling like something chill or something with action today?",
        f"Okay that narrows it down beautifully. Ever played {title}? {description[:50]}..."
    ]
    
    return random.choice(templates)

async def generate_followup_question(session, user) -> str:
    """
    Generate contextual follow-up questions that avoid repetition
    """
    name = getattr(user, "name", None) if user else None
    interaction_count = len(session.interactions) if session and session.interactions else 0
    asked_questions = getattr(session, 'asked_questions', []) or []
    
    # Priority-based question selection
    if not name and "name" not in asked_questions and interaction_count >= 3:
        if not hasattr(session, 'asked_questions'):
            session.asked_questions = []
        session.asked_questions.append("name")
        return "Also, I can remember your name for next time if you like — want me to?"
    
    elif not session.platform_preference and "platform" not in asked_questions:
        if not hasattr(session, 'asked_questions'):
            session.asked_questions = []
        session.asked_questions.append("platform")
        return "Just curious—do you ever play on mobile when you're not at your desk? Or stick to PC?"
    
    elif not getattr(user, 'playtime', None) and "playtime" not in asked_questions and interaction_count >= 5:
        if not hasattr(session, 'asked_questions'):
            session.asked_questions = []
        session.asked_questions.append("playtime")
        return "Oh, and when do you usually find time to play? Evening? Weekend afternoons?"
    
    elif session.platform_preference and "PC" in str(session.platform_preference) and "steam" not in asked_questions:
        if not hasattr(session, 'asked_questions'):
            session.asked_questions = []
        session.asked_questions.append("steam")
        return "Want me to send a steam link?"
    
    # Natural conversation continuers
    continuers = [
        "How did that sound to you?",
        "Want a link to check it out?",
        "Ring a bell?",
        "Sound good or want something different?"
    ]
    
    return random.choice(continuers)
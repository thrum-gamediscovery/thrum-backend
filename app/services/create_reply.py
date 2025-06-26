# 📄 File: generate_thrum_reply.py

import openai
from datetime import datetime
from app.services.mood_engine import detect_mood_from_text
from app.services.game_recommend import game_recommendation
from app.services.input_classifier import classify_user_input, update_user_from_classification
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.models.user_profile import UserProfile

async def generate_thrum_reply(user: UserProfile, session: Session, user_input: str, db) -> str:
    # Detect mood (for profile and session)
    mood = detect_mood_from_text(db=db, user_input=user_input)
    if mood:
        user.mood_tags["last"] = mood
        user.last_updated["mood_tags"] = str(datetime.utcnow())
        db.commit()
    is_first_time = len(session.interactions) == 1
    print(f'------------------------------------------------------------------------------------------------------------is_first_time : {is_first_time}---------- {len(session.interactions)}')
    # Classify new profile signals (genre, vibe, platform, etc.)
    classification = classify_user_input(session=session, user_input=user_input)
    update_user_from_classification(db=db, user=user, classification=classification,session=session)
    
    # 🎯 Get recommended games based on profile
    recommended_games = game_recommendation(user=user, db=db,session=session)
    next_game = recommended_games[0] if recommended_games else None

    # 🔁 Get last recommendation and mood
    last_game = session.game_recommendations[-1].game if session.game_recommendations else None
    print(f"last_game : {last_game}")
    
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else None
    print(f"[🧠] Last Thrum reply: {last_thrum_reply}")
    # 🧠 Build context JSON for GPT
    profile_context = {
        "name": user.name,
        "mood": user.mood_tags.get("last"),
        "genre_interest": user.genre_prefs,
        "platform": user.platform_prefs,
        "region": user.region,
        "playtime": user.playtime,
        "reject_tags": user.reject_tags
    }

    
    system_prompt = (
        "You are Thrum, a warm and playful game matchmaker. "
        "Your tone is cozy, human, and emoji-friendly. Never robotic. Never generic. "
        "Each reply should: (1) feel like part of a real conversation, (2) suggest a game *only if appropriate*, and (3) ask one soft follow-up. "
        "Never ask multiple questions at once. Never list features. Never say 'as an AI'. Never break character. "
        "Keep it under 25 words. Add 1–2 emojis that match the user's mood."
    )
    if is_first_time:
        user_prompt = f"""
    The user just said: "{user_input}"
    This is their first message.

    Write a friendly first reply from Thrum, introducing who you are.
    Ask softly if they want a game recommendation. Use casual, low-pressure tone.
    Avoid recommending a game yet. Keep it warm and short.
    """
    yes_signals = ["yes", "sure", "ok", "okay", "yeah", "hit me", "go for it", "why not"]
    # CASE 2: SECOND MESSAGE, USER SAID YES (e.g. "sure", "ok", "hit me", etc.)
    if len(session.interactions) == 1 and any(word in user_input.lower() for word in yes_signals):
        
        user_prompt = f"""
    The user said: "{user_input}"
    This is their second message and it sounds like a yes.

    Suggest one cozy, beginner-safe game: "{next_game}"
    Keep it short and playful.
    Ask a gentle follow-up to start learning their taste (like “chill or action?”).
    """
    # CASE 3: STANDARD CONTINUED CONVERSATION
    if next_game and not is_first_time:
        user_prompt = f"""
    User just said: "{user_input}"
    Your last message was: "{last_thrum_reply}"
    Game to suggest now: "{next_game}"

    User profile: {profile_context}

    Write Thrum’s reply:
    - Mention the game casually
    - Match the user's tone and mood
    - Do not ask directly any question for complete 
    - Ask one soft follow-up to help refine future picks (genre,platform, name, playtime, etc.)
    Keep it under 25 words. Add 1–2 emojis that match the tone.
    """
        
    # CASE 4: NO GAME TO RECOMMEND
    if not next_game and not is_first_time:
        user_prompt = f"""
    User just said: "{user_input}"
    You don’t have a strong game recommendation yet.

    Write a playful, reassuring message like “Still thinking...” or “Give me a sec 💭”
    Keep it short and warm.
    """

    response = openai.ChatCompletion.create(
        model='gpt-4.1-mini',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.9
    )

    return response["choices"][0]["message"]["content"]
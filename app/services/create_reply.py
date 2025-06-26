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

    # Classify new profile signals (genre, vibe, platform, etc.)
    classification = classify_user_input(session=session, user_input=user_input)
    update_user_from_classification(db=db, user=user, classification=classification, session=session)

    # 🎯 Get recommended games based on profile
    recommended_games = game_recommendation(user=user, db=db, session=session)
    next_game = recommended_games[0] if recommended_games else None
    has_game = next_game is not None

    # 🔁 Get last recommendation and mood
    last_game = session.game_recommendations[-1].game if session.game_recommendations else None

    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else None

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

    # 🕵️‍♂️ Figure out which field is unknown
    missing_fields = []
    if not user.genre_prefs: missing_fields.append("genre")
    if not user.platform_prefs: missing_fields.append("platform")
    if not user.name: missing_fields.append("name")
    if not user.playtime: missing_fields.append("playtime")

    # 🤖 Check for greetings
    user_input_clean = user_input.lower().strip()
    greeting_keywords = {"hi", "hello", "hey", "yo", "hiya", "heya", "hey thrum"}
    is_greeting = user_input_clean in greeting_keywords

    if is_greeting:
        return "Hey 👋 Nice to meet you. I’m Thrum – I help people find games that actually fit their mood. Want a quick recommendation? No pressure."

    # 📣 GPT prompt logic
    system_prompt = (
    "You are Thrum, a warm and playful game matchmaker. "
    "Your job is to suggest games based on the user's mood and preferences. "
    "But if the user is just saying hi or greeting you, reply with a friendly welcome – make it slightly different each time. "
    "Avoid suggesting a game in that case. Make it sound chill, like you're meeting them for the first time. "
    "For all other inputs, suggest a game if one is available. After a rec, ask for ONE missing profile field to improve future suggestions. "
    "Ask in this order: genre → platform → name → playtime. "
    "If no game is found, ask softly for a new genre, mood, or vibe (only one). "
    "All replies should be emoji-filled and sound casual, never like a form. Vary your phrasing slightly in every message."
)

    user_prompt = f"""
User Input: "{user_input}"

Previous Thrum Message: "{last_thrum_reply}"
Last Game Recommended: "{last_game.title if last_game else 'None'}"
New Game Recommendation: "{next_game}" if a game is found, else say "None"

User Profile:
{profile_context}

Missing Profile Fields: {missing_fields}
Instructions:

- If the user input is a greeting (e.g. “hi”, “hello”, “hey”) or any kind of greeting message according you, respond with a warm welcome. 
  Do NOT suggest a game in this case.as well as dont ask for the missing profile fields.
  Vary your phrasing and emojis a little every time. For example:
  "Hey 👋 I'm Thrum! I match games to your vibe. Want a quick rec? 🎮✨"
  or 
  "Yo! I'm Thrum 🤗 Game guide and vibe matcher. Shall we find you something?"

- If it's not a greeting, follow normal rec logic:
  - Suggest a game if found, using a fun 10-14 word sentence. 🎯
  - If no game is found, ask for a new genre, mood, or vibe — just one.
  - If there are any missing profile fields, ask just ONE — in this order: genre → platform → name → playtime.
  - If there are NO missing fields, ask something fun like:
      - "What's your all-time favorite game?" 🎮
      - or "What kind of mood do you love while gaming?" 🌈
      - or "Ever played something that really stuck with you?" ✨
  - Never ask more than one thing. Never sound like a form.
  - Keep everything warm, short (max 30 words), and full of emojis.

    """

    print(f"[🧠] User prompt-------------: {user_prompt}")
    response = openai.ChatCompletion.create(
        model='gpt-4.1-mini',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.9
    )

    return response["choices"][0]["message"]["content"]


def get_intro_game(db):
    from app.db.models.game import Game
    game = db.query(Game).filter(Game.title == "A Short Hike").first()
    if game:
        return game
    return db.query(Game).filter(Game.genre.any("cozy")).first()

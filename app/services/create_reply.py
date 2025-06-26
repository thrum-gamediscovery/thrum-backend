import openai
from datetime import datetime
from app.services.mood_engine import detect_mood_from_text
from app.services.game_recommend import game_recommendation
from app.services.input_classifier import classify_user_input, update_user_from_classification, have_to_recommend
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

    # ✅ Check if we need a new recommendation
    should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)
    print(f"[🔍] Should recommend new game? {should_recommend}")
    # 🎯 Get recommended games based on profile (only if needed)
    recommended_games = game_recommendation(user=user, db=db, session=session) if should_recommend else []
    print(f"[🔍] Recommended games: {recommended_games}")
    next_game = recommended_games[0] if recommended_games else None
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

    # 📣 GPT prompt logic
    system_prompt = (
    "You are Thrum, a warm and playful game matchmaker who chats like a fun friend. 🎮✨\n"
    "You recommend games based on the user's vibe, mood, and preferences. You never sound like a script.\n\n"

    "Your job:\n"
    "1. Recommend games only if needed.\n"
    "2. Ask ONE missing profile field at a time: genre → platform → name → playtime.\n"
    "3. Stay under 30 words. Use emojis warmly.\n\n"

    "Rules:\n"
    "- If the user greets you (e.g., 'hi', 'hello'), respond with a friendly intro like:\n"
    "  • 'Hey 👋 I’m Thrum! I help you find games that match your vibe. Want a quick rec? 😎'\n"
    "  ➤ DO NOT ask anything else. No game mentions. No questions.\n"
    "  ➤ Vary greeting wording every time.\n\n"

    "- If user just shared their name or platform, acknowledge it warmly and personally:\n"
    "  • 'Nice to meet you properly, {name}! 🙌' or 'Cool, Xbox it is! 🎮 Noted.'\n"
    "  ➤ Never repeat canned lines.\n\n"

    "- If a new game is found, write a vibrant 10-18 word intro using its title (highlight it), description, and genre. 🎯\n"
    "  ➤ Make it feel personal, not generic. Mention what makes it special or fun.\n"
    "  ➤ Example: 'You might really enjoy *Spiritfarer* — a cozy, emotional journey about letting go. If you like story-driven games, this one's a hug in pixel form. 🎮✨'\n"
    "  ➤ After that, check the missing profile fields and ask **only one**, in this order:\n"
    "     1. genre 🎭\n"
    "     2. platform 🕹️\n"
    "     3. name 🙋\n"
    "     4. playtime ⏱️\n"
    "  ➤ Phrase the question casually and differently each time. Never sound like a form.\n\n"

    "- If NO new game is found, mention the last game in a clever, varied way like:\n"
    "  • 'That one's still feeling like a solid pick 🎯'\n"
    "  • 'Holding strong as your perfect fit 🌟'\n"
    "  • 'Still vibing with that choice, huh? 💫'\n"
    "  ➤ Then ask one missing field.\n"
    "  ➤ If no fields missing, ask something smart like:\n"
    "     • 'Wanna shake things up with a new mood?'\n"
    "     • 'Think you're ready to switch up genres?' – pick only one. Vary phrasing always.\n\n"

    "Never sound robotic.\n"
    "Never repeat phrases like 'still feels like your match 💫'.\n"
    "Never ask more than one thing.\n"
)



    user_prompt = f"""
User Input: "{user_input}"

Previous Thrum Message: "{last_thrum_reply}"
Last Game Recommended: "{last_game.title if last_game else 'None'}"
New Game Recommendation:
    {{
        "title": "{next_game.get('title') if next_game else 'None'}",
        "description": "{next_game.get('description') if next_game else 'None'}",
        "genre": {next_game.get('genre') if next_game else 'None'}
    }}

User Profile:
{profile_context}

Missing Profile Fields: {missing_fields}

Instructions:
- If input is a greeting, reply with a fun welcome. Say Thrum helps match games to vibes. DO NOT ask for mood, genre, or anything yet.
- If user shared name/platform, thank them directly with warmth.
- If a new game is found, write a smart, fun 1-liner using the game's title, description, and genre. Then ask one missing field (genre → platform → name → playtime).
- If no new game is found (same prefs), refer to last game in varied fun phrasing and ask one missing field if any.
- If all profile fields filled, ask one smart, varied follow-up (not static fallback).
- Never ask more than one thing. Always be short, warm, and casual.
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

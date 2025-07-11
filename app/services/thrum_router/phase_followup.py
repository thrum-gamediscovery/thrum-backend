from app.tasks.followup import handle_followup_logic
from app.services.tone_engine import get_last_user_tone_from_session
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
from datetime import datetime, timedelta
from app.db.session import SessionLocal
import openai
import os
from app.utils.whatsapp import send_whatsapp_message
import random
from app.services.thrum_router.interrupt_logic import check_intent_override
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.game import Game
from app.db.models.game_platforms import GamePlatform


openai.api_key = os.getenv("OPENAI_API_KEY")

async def handle_followup(db, session, user, user_input,classification):
    override_reply = await check_intent_override(db=db, user_input=user_input, user=user, session=session, classification=classification)
    if override_reply:
        return override_reply
    return await handle_followup_logic(db=db, session=session, user=user, classification=classification ,user_input=user_input)

async def ask_followup_que(session) -> str:
    # Context-aware followup questions
    asked_questions = getattr(session, 'asked_questions', []) or []
    platform = session.platform_preference[-1] if session.platform_preference else None
    
    # Platform-specific questions
    if platform and "PC" in str(platform) and "steam" not in asked_questions:
        if not hasattr(session, 'asked_questions'):
            session.asked_questions = []
        session.asked_questions.append("steam")
        return "Want me to send you the Steam link if you have a Steam account?"
    
    # Natural conversation continuers
    followup_questions = [
        "How did that sound to you?",
        "Let me know if that clicks. If not, I've got other curveballs ready to throw your way.",
        "Sound good or want something else?",
        "That work for you or should I find something different?",
        "Ring a bell?",
        "Worth a shot?"
    ]
    
    return random.choice(followup_questions)

# Legacy function kept for compatibility
async def ask_followup_que_legacy(session) -> str:
    if session.story_preference is None:
        last_game = session.game_recommendations[-1].game if session.game_recommendations else None
        if last_game and last_game.has_story is True:
            story_rich_prompts = [
                "That one's a story-rich game. Do you usually enjoy story-driven titles or prefer pure gameplay?",
                "This pick has a strong story focus. Are you into story games or do you like games with less narrative?",
                "It's a story-heavy game. Do you enjoy games where story matters or ones focused on gameplay only?",                    "This one leans into story a lot. Are you a fan of story in games, or do you prefer action-first?",
                "That's a solid story-based experience. Do you usually go for games with story or ones that skip it?",
                "Definitely a story-rich title. Do you like games with deep stories, or more pure gameplay?"
            ]
            return random.choice(story_rich_prompts)

        elif last_game and last_game.has_story is False:
            gameplay_focused_prompts = [
                "This one doesn't have much story. Do you usually prefer gameplay-focused games or story-rich ones?",                    "Not much story here — it's all about the action. Do you like that or something with more story?",
                "It's a gameplay-first game, light on story. Are you more into story-driven games or fast gameplay?",
                "This one skips the story for fast action. Do you enjoy that or do you look for story in your games?",
                "No strong story in this one. Do you prefer story games or are you good with just gameplay?",
                "Very little story here. Are you more into story-rich games or gameplay-heavy ones?"
            ]
            return random.choice(gameplay_focused_prompts)

    else:
        game_title = session.last_recommended_game or "that game"
        prompt = f"""
You're Thrum — a fast, friendly, emotionally smart game recommender.
The user just got a game suggestion: "{game_title}"
Now, ask them *one* natural, human-sounding question that combines:
- Asking if they liked the game
- OR if they want a different one
Use a warm, casual tone. Emojis are not allowed.
Avoid robotic or generic phrasing.
Don’t say the game name again. Just ask a single fun, friendly question.
Return only the question.
"""


    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        temperature=0.5,
        messages=[
            {"role": "user", "content": prompt.strip()}
        ]
    )
    return response.choices[0].message.content.strip()

async def get_followup():
    print("------------------------------------------------------------------get 1")
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.awaiting_reply == True,
        Session.followup_triggered == True
    ).all()
    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        delay = timedelta(seconds=5)
        print("------------------------------------------------------------------get 2")
        if now - s.last_thrum_timestamp > delay:
            print("------------------------------------------------------------------get 3")
            reply = await ask_followup_que(s)
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.awaiting_reply = True
            s.followup_triggered = False    
        db.commit()
    db.close()

async def handle_game_inquiry(db: Session, user, session, user_input: str) -> str:
    game_id = session.meta_data.get("find_game")
    if not game_id:
        return "⚠️ The user asked about a game, but no valid game was found in session metadata."

    # Fetch game
    game = db.query(Game).filter_by(game_id=game_id).first()
    if not game:
        return f"⚠️ Couldn't find the game with ID {game_id} in the database."

    # Get platforms for the game
    platform_rows = db.query(GamePlatform.platform).filter_by(game_id=game_id).all()
    platform_list = [p[0] for p in platform_rows] if platform_rows else []

    # Check if already recommended
    recommended_ids = set(
        str(r[0]) for r in db.query(GameRecommendation.game_id).filter(
            GameRecommendation.session_id == session.session_id
        )
    )

    # Game fields
    game_info = {
        "title": game.title,
        "description": game.description or "No description available.",
        "genre": ", ".join(game.genre) if game.genre else "N/A",
        "vibes": ", ".join(game.game_vibes) if game.game_vibes else "N/A",
        "mechanics": game.mechanics or "N/A",
        "visual_style": game.visual_style or "N/A",
        "story_focus": "has a strong story" if game.has_story else "is more gameplay-focused",
        "emotion": game.emotional_fit or "N/A",
        "mood_tags": ", ".join(game.mood_tags.keys()) if game.mood_tags else "N/A",
        "platforms": ", ".join(platform_list) if platform_list else "Unknown"
    }

    # If already recommended → update phase and return query-resolution prompt
    if game_id in recommended_ids:
        session.phase = PhaseEnum.FOLLOWUP
        db.commit()

        return f"""
The user was already recommended the game **{game_info['title']}**, but now they have some follow-up questions.

Here are the game details to help you respond naturally:

- **Title**: {game_info['title']}
- **Description**: {game_info['description']}
- **Genre**: {game_info['genre']}
- **Vibes**: {game_info['vibes']}
- **Mechanics**: {game_info['mechanics']}
- **Visual Style**: {game_info['visual_style']}
- **Story Focus**: This game {game_info['story_focus']}.
- **Emotional Fit**: {game_info['emotion']}
- **Mood Tags**: {game_info['mood_tags']}

Based on what the user asked: “{user_input}”, answer their query naturally — assume they already know the basics.
""".strip()

    # Else, it’s a new inquiry → recommend + save + followup
    session.last_recommended_game = game_info["title"]

    # Save recommendation
    game_rec = GameRecommendation(
        session_id=session.session_id,
        user_id=user.user_id,
        game_id=game.game_id,
        platform=None,
        mood_tag=None,
        accepted=None
    )
    db.add(game_rec)
    db.commit()

    # 10-12 words on why it fits (you can replace with AI-generated or rule-based)
    reason_fit = f"{game_info['title']} is immersive, emotionally rich, and story-driven with strong vibes."

    return f"""
The user asked about the game **{game_info['title']}**, which hasn’t been recommended yet. 
They seem curious, so go ahead and suggest it confidently.

Why it fits: {reason_fit}

This game is available on: {game_info['platforms']}

Details you can use to enrich your response:

- **Description**: {game_info['description']}
- **Genre**: {game_info['genre']}
- **Vibes**: {game_info['vibes']}
- **Mechanics**: {game_info['mechanics']}
- **Visual Style**: {game_info['visual_style']}
- **Story Focus**: {game_info['story_focus']}
- **Emotional Fit**: {game_info['emotion']}
- **Mood Tags**: {game_info['mood_tags']}

Now, answer the user’s message — “{user_input}” — and introduce this game like a friendly recommendation.
""".strip()
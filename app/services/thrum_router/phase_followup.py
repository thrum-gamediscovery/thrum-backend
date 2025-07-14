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
from app.services.session_memory import SessionMemory

openai.api_key = os.getenv("OPENAI_API_KEY")

client = openai.AsyncOpenAI()

model= os.getenv("GPT_MODEL")

async def handle_followup(db, session, user, user_input,classification):
    override_reply = await check_intent_override(db=db, user_input=user_input, user=user, session=session, classification=classification)
    if override_reply:
        return override_reply
    return await handle_followup_logic(db=db, session=session, user=user, classification=classification ,user_input=user_input)

async def ask_followup_que(session) -> str:
    last_user_tone = get_last_user_tone_from_session(session)
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    game_title = session.last_recommended_game or "that game"
    prompt = f"""
        USER MEMORY & RECENT CHAT:
        {memory_context_str if memory_context_str else "No prior user memory or recent chat."}

        You are Thrum — an emotionally aware, tone-matching gaming companion.

        The user was just recommended a game.

        Now, write ONE short, natural follow-up to check:
        - if the game sounds good to them  
        - OR if they'd like another game

        Your response must:
        - Reflect the user's tone: {last_user_tone} (e.g., chill, genz, hype, unsure, etc.)
        - Use fresh and varied phrasing every time — never repeat past follow-up styles
        - Be no more than 15 words. If you reach 15 words, stop immediately.
        - Do not mention or summarize the game or use the word "recommendation".
        - Do not use robotic phrases like “Did that one hit the mark?”
        - Avoid any fixed templates or repeated phrasing

        Tone must feel warm, casual, playful, or witty — depending on the user's tone.

        Only output one emotionally intelligent follow-up. Nothing else.
        """

    response = await client.chat.completions.create(
        model=model,
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
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

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
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else "No prior user memory or recent chat."}

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
    # reason_fit = f"{game_info['title']} is immersive, emotionally rich, and story-driven with strong vibes."

    return f"""
The user asked about the game **{game_info['title']}**, which hasn’t been recommended yet. 
They seem curious, so go ahead and suggest it confidently.

Describe in 10–12 words why this game fits someone curious about it.
No greeting, no filler — just the sentence.
Make it sound friendly, emotionally aware, and natural.

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
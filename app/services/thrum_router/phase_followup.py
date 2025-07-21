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

async def handle_followup(db, session, user, user_input,classification,intrection):
    override_reply = await check_intent_override(db=db, user_input=user_input, user=user, session=session, classification=classification, intrection=intrection)
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
        {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

        You are Thrum — an emotionally aware, tone-matching gaming companion.

        The user was just recommended a game.

        Now, write ONE short, natural follow-up to check:
        – if the game sounds good to them  
        – OR if they’d like another game

        Your response must:
        - Reflect the user’s tone: {last_user_tone} (e.g., chill, genz, hype, unsure, etc.)
        - Use fresh and varied phrasing every time — never repeat past follow-up styles
        - Be no more than 15 words. If you reach 15 words, stop immediately.
        - Do not mention or summarize the game or use the word "recommendation".
        - Do not use robotic phrases like “Did that one hit the mark?”
        - Avoid any fixed templates or repeated phrasing

        Tone must feel warm, casual, playful, or witty — depending on the user’s tone.

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

        delay = timedelta(seconds=3)
        if now - s.last_thrum_timestamp > delay:
            s.followup_triggered = False
            db.commit()
            reply = await ask_followup_que(s)
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.awaiting_reply = True
        db.commit()
    db.close()

async def handle_game_inquiry(db: Session, user, session, user_input: str) -> str:
    game_id = session.meta_data.get("find_game")
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    if not game_id:
        prompt = """
            You are Thrum, the game discovery assistant. The user has asked about a specific game, but there is no information about that game in your catalog or data.
            Strict rule: Never make up, invent, or generate any information about a game you do not have real data for. If you don't have info on the requested game, do not suggest another game or pivot to a new recommendation.
            Politely and clearly let the user know you don’t have any info on that game. Do not mention 'database' or 'catalog'. Do not offer any other suggestions or ask any questions. Keep your response to one short, friendly, and supportive sentence, in a human tone.
            Reply format:
            - One short sentence: Clearly say you don’t have information on that game right now.
            """
        return prompt
    game = db.query(Game).filter_by(game_id=game_id).first()
    # Get platforms for the game
    platform_rows = db.query(GamePlatform.platform).filter_by(game_id=game_id).all()
    platform_list = [p[0] for p in platform_rows] if platform_rows else []
    # Get user's preferred platform (last non-empty entry in the array)
    platform_preference = None
    if session.platform_preference:
        non_empty = [p for p in session.platform_preference if p]
        if non_empty:
            platform_preference = non_empty[-1]
    else:
        gameplatform_row = db.query(GamePlatform).filter_by(game_id=game_id).first()
        platform_preference = gameplatform_row.platform
    # Fetch the platform link for that game and platform
    platform_link = None
    if platform_preference:
        gp_row = db.query(GamePlatform).filter_by(game_id=game_id, platform=platform_preference).first()
        if gp_row:
            platform_link = gp_row.link  # This is the URL/link for the user's preferred platform
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
        "complexity": game.complexity or "N/A",
        "visual_style": game.graphical_visual_style or "N/A",
        "story_focus": "has a strong story" if game.has_story else "is more gameplay-focused",
        "emotion": game.emotional_fit or "N/A",
        "mood_tags": ", ".join(game.mood_tag) if game.mood_tag else "N/A",
        "platforms": ", ".join(platform_list) if platform_list else "Unknown",
        "platform_link": platform_link
    }
    # If already recommended → update phase and return query-resolution prompt
    if game_id in recommended_ids:
        session.phase = PhaseEnum.FOLLOWUP
        db.commit()
        return f"""
            USER MEMORY & RECENT CHAT:
            {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
            The user was already recommended the game **{game_info['title']}**, but now they have some follow-up questions.
            Here are the game details to help you respond naturally:(game details)
            - **Title**: {game_info['title']}
            - **Description**: {game_info['description']}
            - **Genre**: {game_info['genre']}
            - **Vibes**: {game_info['vibes']}
            - **complexity**: {game_info['complexity']}
            - **Visual Style**: {game_info['visual_style']}
            - **Story Focus**: This game {game_info['story_focus']}.
            - **Emotional Fit**: {game_info['emotion']}
            - **Mood Tags**: {game_info['mood_tags']}
            - **available Platfrom**:{game_info['platforms']}
            - **Platfrom_link**:{game_info['platform_link']}
            Based on what the user asked: “{user_input}”, answer their query naturally — assume they already know the basics.
            # Strict Instruction:
            only answer the user question from the game details do not add things on your own.
            Strictly provide only the information being asked by the user in their message.
            if platform link is none and it is asked in user input then you must just clearly tell them that there is no link we have for that game.
            When providing a platform link, do not use brackets or Markdown formatting—always mention the plain URL naturally within the sentence.and must acknowledge that this link is for {platform_preference} platform.
            If they ask about platforms, mention the available platforms (shown below).
            If the user does not ask about links or platforms, do not mention them.
            """.strip()
    # Else, it’s a new inquiry → recommend + save + followup
    session.last_recommended_game = game_info["title"]
    session_memory.last_game = game.title
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
    USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
the overall message size should no more than 18-20 words.
The user asked about the game **{game_info['title']}**, which hasn’t been recommended yet.
They seem curious, so go ahead and suggest it confidently.
Describe in 10–12 words why this game fits someone curious about it. if game title is there in reply then it must be bold.
if the platform link is None then do not mention that, and if there is link then it must be added in the message.
When providing a platform link(when it is not None), do not use brackets or Markdown formatting—always mention the plain URL naturally within the sentence.and must acknowledge that this link is for {platform_preference} platform.

No greeting, no filler — just the sentence.
Make it sound friendly, emotionally aware, and natural.
This game is available on: {game_info['platforms']}
Details you can use to enrich your response:
- **Title**: {game_info['title']}
- **Description**: {game_info['description']}
- **Genre**: {game_info['genre']}
- **Vibes**: {game_info['vibes']}
- **complexity**: {game_info['complexity']}
- **Visual Style**: {game_info['visual_style']}
- **Story Focus**: {game_info['story_focus']}
- **Emotional Fit**: {game_info['emotion']}
- **Mood Tags**: {game_info['mood_tags']}
- **available Platfrom**:{game_info['platforms']}, just mention one or two platform.
- **Platfrom_link**:{game_info['platform_link']}
Now, answer the user’s message — “{user_input}” — and introduce this game like a friendly recommendation.
""".strip()
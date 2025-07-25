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
from app.services.general_prompts import GLOBAL_USER_PROMPT


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
    
    # Check if the user has accepted a game recommendation
    game_accepted = False
    if session.game_recommendations:
        last_rec = session.game_recommendations[-1]
        if last_rec.accepted is True:
            game_accepted = True
            # Store this information in session metadata
            session.meta_data = session.meta_data or {}
            if "game_accepted_at" not in session.meta_data:
                session.meta_data["game_accepted_at"] = datetime.utcnow().isoformat()
                session.meta_data["accepted_game_title"] = game_title
    
    # If a game was accepted, don't ask for another game immediately
    if game_accepted:
        # Check if it's been at least 2 minutes since the game was accepted
        accepted_at = None
        if "game_accepted_at" in session.meta_data:
            try:
                accepted_at = datetime.fromisoformat(session.meta_data["game_accepted_at"])
            except (ValueError, TypeError):
                pass
        
        # If it's been less than 2 minutes, just thank them and end the conversation
        if accepted_at and (datetime.utcnow() - accepted_at) < timedelta(minutes=2):
            return f"Awesome, enjoy {game_title}! I'll check back with you later to see how it went."
        # If it's been more than 2 minutes but less than 3 hours, ask about the suggestion
        elif accepted_at and (datetime.utcnow() - accepted_at) < timedelta(hours=3):
            prompt = f"""
                USER MEMORY & RECENT CHAT:
                {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

                You are Thrum — an emotionally aware, tone-matching gaming companion.

                The user accepted your recommendation for {game_title} just a few minutes ago.
                Write ONE short, natural follow-up to ask what they think about the suggestion (not if they've played it yet).

                Your response must:
                - Reflect the user's tone: {last_user_tone} (e.g., chill, genz, hype, unsure, etc.)
                - Use fresh and varied phrasing every time — never repeat past follow-up styles
                - Be no more than 20 words. If you reach 20 words, stop immediately.
                - Ask about their thoughts on the {game_title} suggestion
                - Do not suggest any new games
                - Avoid any fixed templates or repeated phrasing

                Tone must feel warm, casual, playful, or witty — depending on the user's tone.

                Only output one emotionally intelligent follow-up. Nothing else.
                """
            return prompt
        # If it's been more than 3 hours, ask about their experience with the game
        elif accepted_at:
            prompt = f"""
                USER MEMORY & RECENT CHAT:
                {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

                You are Thrum — an emotionally aware, tone-matching gaming companion.

                The user accepted your recommendation for {game_title} a while ago.
                Now, write ONE short, natural follow-up to check if they had a chance to try the game and how they liked it.
                If they haven't played it yet, ask if they'd like a different recommendation.

                Your response must:
                - Reflect the user's tone: {last_user_tone} (e.g., chill, genz, hype, unsure, etc.)
                - Use fresh and varied phrasing every time — never repeat past follow-up styles
                - Be no more than 25 words. If you reach 25 words, stop immediately.
                - Specifically ask about their experience with {game_title}
                - Include a question about whether they want something different if they haven't played
                - Avoid any fixed templates or repeated phrasing

                Tone must feel warm, casual, playful, or witty — depending on the user's tone.

                Only output one emotionally intelligent follow-up. Nothing else.
                """
    else:
        # Standard follow-up for non-accepted games
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
    
    # Set game_interest_confirmed flag when user inquires about a game
    session.meta_data = session.meta_data or {}
    session.meta_data["game_interest_confirmed"] = True
    db.commit()
    if not game_id:
        prompt = """
            You are Thrum, the game discovery assistant. The user has asked about a specific game, but there is no information about that game in your catalog or data.
            Strict rule: Never make up, invent, or generate any information about a game you do not have real data for. If you don't have info on the requested game, do not suggest another game or pivot to a new recommendation.
            Politely and clearly let the user know you don’t have any info on that game. Do not mention 'database' or 'catalog'. Do not offer any other suggestions or ask any questions. Keep your response to one short, friendly, and supportive sentence, in a human tone.
            Reply format:
            - One short sentence: Clearly say you don’t have information on that game right now.
            -don't suggest a game on your own if there is no game found.
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
        user_prompt = f"""
            {GLOBAL_USER_PROMPT}
            ---
            🚨 THRUM — FRIEND MODE: ENABLED
            You are not a chatbot. You are THRUM — the world’s most emotionally intelligent, tone-sensitive, human-feeling game discovery companion. You respond like a friend who *gets* the user’s vibe and tailors your tone, rhythm, and energy to match.
            The user was already recommended the game **{game_info['title']}**, and now they’re back with follow-up questions.
            🎯 Your job:
            - Mirror their energy — hype, chill, skeptical, or playful.
            - Respond like a real person texting a friend. Keep it short, warm, and emotionally tuned.
            - Add one short, new description of the game (20–30 words) that’s not a repeat of earlier info.
            - If they ask about platforms, mention them smoothly.
            - If they ask for a link and one exists, include it casually (no Markdown, no brackets).
            - If no link exists and they asked for one, say that clearly.
            - Never sound like a system. Never list features.

            "The user already knows this game and just asked: "{user_input}"
            They seem curious or into it.

            → Drop one fresh line about the game, how friends would inform further — something vivid, emotional, and not mentioned before.

            → If they asked about platforms and you have a link, casually mention it like a friend would inform you over whatsapp.
            Never say 'click here' — just drop it inside the sentence like a friend would."

            → Don't repeat the old pitch
            Say something different that hits differently, always try to be original."

            "If the user asked about the platform and you have a link, casually drop it into the sentence.

            → Don't explain it.
            → Don't format it.
            → Don't use Markdown or brackets or say 'click here'.
            → Just talk like a close friend who tosses the link over in whatsapp without making it a big deal.
            - Never start with phrases like "Alright", "So imagine", "Picture this", "Let me tell you", or anything generic or formal.
            - Always begin your message naturally, mid-thought, like a real friend dropping a recommedation.
            - Use different openers every time — never repeat the same structure or intro twice.

            Example but dont use this, generate always variables in an unique way how friends talk over whatsapp:
            'You'll find it on Xbox too btw: https://store.xbox.com/game-title — it fits your style I think.'"

            Use this to guide your answer:
            - Title: {game_info['title']}
            - Description: {game_info['description']}
            - Genre: {game_info['genre']}n
            - Vibes: {game_info['vibes']}
            - Complexity: {game_info['complexity']}
            - Visual Style: {game_info['visual_style']}
            - Story Focus: {game_info['story_focus']}
            - Emotional Fit: {game_info['emotion']}
            - Mood Tags: {game_info['mood_tags']}
            - Platforms: {game_info['platforms']}
            - Platform Link: {game_info['platform_link']}
            User message: “{user_input}”
        """.strip()
        return user_prompt
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

    user_prompt = f"""
        {GLOBAL_USER_PROMPT}
        🚨 THRUM — FRIEND MODE: ENABLED
        You are THRUM — the emotionally-aware, tone-matching game discovery companion who talks like a friend, not a system.
        The user just brought up **{game_info['title']}** — a game they’re curious about but haven’t been pitched yet.
        🎯 Your job:
        - Drop one emotionally aware sentence (max 20 words) explaining why the game might vibe with them.
        - Sound confident and human — like a text from someone who knows their taste.
        - If the platform link exists, include it in the sentence casually — no Markdown, no brackets.
        - If no link exists, skip it without explanation.
        - Mention 1–2 platforms if helpful.
        → Drop two fresh, emotionally warm lines about the game.
        → Don't repeat earlier phrasing or vibe.
        → Say it like someone texting a friend — casually, like you remembered something cool just now.
        → No greetings. No intros. Just the sentence — full of tone and spark.

        "If the user asked about the platform and you have a link, casually drop it into the sentence.

        → Don't explain it.
        → Don't format it.
        → Don't use Markdown or brackets or say 'click here'.
        → Just talk like a close friend who tosses the link over in whatsapp without making it a big deal.
        - Never start with phrases like "Alright", "So imagine", "Picture this", "Let me tell you", or anything generic or formal.
        - Always begin your message naturally, mid-thought, like a real friend dropping a recommedation.
        - Use different openers every time — never repeat the same structure or intro twice.

        Example but dont use this, generate always variables in an unique way how friends talk over whatsapp:
        'You'll find it on Xbox too btw: https://store.xbox.com/game-title — it fits your style I think.'"

        Use this if you need to pull from:
        - Title: {game_info['title']}
        - Description: {game_info['description']}
        - Genre: {game_info['genre']}
        - Vibes: {game_info['vibes']}
        - Complexity: {game_info['complexity']}
        - Visual Style: {game_info['visual_style']}
        - Story Focus: {game_info['story_focus']}
        - Emotional Fit: {game_info['emotion']}
        - Mood Tags: {game_info['mood_tags']}
        - Platforms: {game_info['platforms']}
        - Platform Link: {game_info['platform_link']}
        User message: “{user_input}”
    """.strip()
    return user_prompt
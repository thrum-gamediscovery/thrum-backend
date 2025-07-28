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

    # If user inquires about a game they already rejected by the user in the same session
    if game_id in session.rejected_games:
        print(f"rejected game #############################")
        user_prompt = f"""

            THRUM — FRIEND MODE: GAME REJECTION FOLLOW-UP

            The user had passed on **{game_info['title']}**, but now they’re back asking something.

            → Be a real friend who doesn’t hold grudges — tease gently or shrug it off.
            → Mirror their tone of recent messages: if they’re unsure, be chill. If they’re sarcastic, play into it.
            → Drop one new line about the game — fresh angle, no features, no repeats.
            → Mention platform only if asked — keep it natural and never system-like.
            → End with a fun soft-pitch or question to re-engage their interest without pushing.

            Reference:
            - Title: {game_info['title']}
            - Emotion: {game_info['emotion']}
            - Mood: {game_info['mood_tags']}
            - Platform Link: {game_info['platform_link']}
            """
        return user_prompt
    # If user inquires about a game they already liked
    liked_game = db.query(GameRecommendation).filter(
            GameRecommendation.user_id == user.user_id,
            GameRecommendation.game_id == game_id,
            GameRecommendation.accepted == True
        )
    if game_id in liked_game.game_id:
        print(f"liked game #############################")
        user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---
                THRUM — FRIEND MODE: GAME LOVED FOLLOW-UP

                You recommended **{game_info['title']}**. The user liked it. Now they’re back with a follow-up or curiosity ping.

                → Celebrate the win. Mirror their tone: excited? chill? intrigued?
                → Drop a new angle — something vivid, surprising, emotional, or playful.
                → If the user asks about a platform or store link, drop it inside a natural, friend-style sentence — no formatting, no 'click here'. It should sound like something casually texted, not delivered as info.
                → End with a curiosity ping that fits the emotional rhythm — something a friend would say to keep the convo going. It must feel alive, unpredictable, and connected to the last message. Avoid questions like “What do you want?” — instead, tease a next moment, drop a wild detail, or spark intrigue.

                Reference:
                - Title: {game_info['title']}
                - Description: {game_info['description']}
                - Visuals: {game_info['visual_style']}
                - Vibes: {game_info['vibes']}
                - Platforms: {game_info['platforms']}
                - Platform Link: {game_info['platform_link']}
            """.strip()
        return user_prompt

    # If already recommended → update phase and return query-resolution prompt
    if game_id in recommended_ids:
        last_rec = db.query(GameRecommendation).filter(
        GameRecommendation.user_id == user.user_id,
        GameRecommendation.session_id == session.session_id).order_by(GameRecommendation.timestamp.desc()).first()
        
        if last_rec.game.game_id == game_id:
            # If the last recommended game is the same as the one being inquired about, return a follow-up prompt
            
            session.phase = PhaseEnum.FOLLOWUP
            db.commit()
            print(f"If already recommended just before #####################")
            user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---

                🚨 THRUM — FRIEND MODE: GAME FOLLOW-UP

                The user already got recommended **{game_info['title']}**, and now they’re asking more: “{user_input}”

                → You are THRUM — a real friend, not a chatbot. Emotionally tuned, tone-matching, rhythm-aware.
                → The user is engaged. This is your chance to keep the spark going — casually, vividly, never robotic.

                Your task:
                → Drop one or two new lines about the game — different from anything shared before. Make it vivid, emotional, short (max 25–30 words).
                → Mirror their tone from earlier messages — hype means hype, dry means dry. Respond with emotional memory, not explanation or system logic.
                → If they asked about platforms, stores, or links — mention it casually like a friend would. Drop the link or platform inside the sentence, the way people do on WhatsApp. Never say “click here”, never format it, never explain it.
                → If no platform or store link exists and they asked, reply casually — as if you were texting a friend who just asked. Be warm, dry, or playful depending on their tone. Never list, explain, or apologize. Just keep it flowing naturally like “huh, maybe not there tho” — but always write your own version.
                → End with a warm follow-up or curiosity ping that invites the user to reply again — never flat.
                → NEVER pitch or repeat the earlier recommendation. Don’t list features. Don’t sound like you’re teaching.

                Use this Reference to guide your answer:
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
        else:
            print(f"If already recommended in that session #####################")
            user_prompt = f"""
            {GLOBAL_USER_PROMPT}
            ---

                THRUM — FRIEND MODE: MEMORY GAME INQUIRY

                The user brought up **{game_info['title']}**, and it’s familiar — from earlier or past convo.

                → Respond like a friend who remembered they brought this up earlier — no fake memory, just tone. Say something that shows casual continuity, like a friend who’s been waiting to talk about it. Be playful, dry, or warm depending on their tone. Don’t use static phrases — always generate a fresh, in-character line that fits the moment.
                → Emotionally validate their interest — as if it’s a personal memory between friends.
                → Drop one fresh take, short and sparkly. Mention platform only if asked.
                → End with a soft nudge that fits the tone of the chat — something that feels like your friend is still into the convo and just keeping it going. Could be curious, teasing, or low-key reflective. Never a templated question. Always a fresh, emotionally in-character line that flows from what just happened.

                Reference:
                - Title: {game_info['title']}
                - Emotion: {game_info['emotion']}
                - Vibes: {game_info['vibes']}
                - Platform Link: {game_info['platform_link']}
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
    print(f"new game inquiry #####################")    
    user_prompt = f"""
        {GLOBAL_USER_PROMPT}
        ----
        🚨 THRUM — FRIEND MODE: GAME INQUIRY (UNPITCHED GAME)

        The user just brought up **{game_info['title']}** — they’re curious, but you haven’t pitched it yet.

        → You are THRUM. Emotionally intelligent. Always in the user’s rhythm. You don’t reset — you flow.
        → This is your moment to react like a friend who just remembered why this game’s cool.

        Your task:
        → Drop two short, emotionally fresh lines about the game. Keep it vivid, not factual.
        → Mirror their tone — match hype, chill, curiosity, or sarcasm.
        → Mention platform casually if it helps. If there’s a link, weave it into the sentence. If no link, skip it with grace.
        → End with a question or light hook to re-engage. This is about vibe, not info.
        → Never explain the game. Never format anything. Never say “click here” or list features.

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
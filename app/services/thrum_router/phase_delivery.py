from app.services.game_recommend import game_recommendation
from app.services.input_classifier import have_to_recommend
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
from app.services.session_memory import SessionMemory
from app.services.general_prompts import GLOBAL_USER_PROMPT, NO_GAMES_PROMPT
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.game import Game
import openai
import os
client = openai.AsyncOpenAI()

async def get_most_similar_liked_title(db, session_id, current_title):
    """
    Returns the liked game title (from the session) most similar to current_title, using GPT for matching.
    """
    recs = (
        db.query(GameRecommendation)
        .filter(
            GameRecommendation.session_id == session_id,
            GameRecommendation.accepted == True
        )
        .order_by(GameRecommendation.timestamp.desc())
        .all()
    )
    titles = []
    for rec in recs:
        # This fetches a tuple (title,), so use [0] to get the string
        title_row = db.query(Game.title).filter(Game.game_id == rec.game_id).first()
        if title_row and title_row[0]:
            titles.append(title_row[0])
    print(f"Titles from session --------------------------: {titles}")
    if not titles:
        return None
    titles_quoted = ', '.join(f'"{t}"' for t in titles)
    prompt = (
        f"Given this list of games: {titles_quoted}.\n"
        f"Which one is most similar (in style, genre, or vibe) to \"{current_title}\"? "
        f"Reply with only the exact game title from the list. No extra text."
    )
    try:
        model = os.getenv("GPT_MODEL")  # Assumes model name in env
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content if response.choices else ""
        result = content.strip().strip('"')
        if result in titles:
            return result
        else:
            # fallback: return most recent
            return titles[0]
    except Exception:
        # Fallback: return most recent
        return titles[0] if titles else None
    
async def get_recommend(db, user, session):
    game, _ = await game_recommendation(db=db, session=session, user=user)
    print(f"Game recommendation: {game}")
    platform_link = None
    last_session_game = None
    description=None
    mood = session.exit_mood  or "neutral"
    if not game:
        user_prompt = NO_GAMES_PROMPT

        return user_prompt
        # Pull platform info
    preferred_platforms = session.platform_preference or []
    user_platform = preferred_platforms[-1] if preferred_platforms else None
    game_platforms = game.get("platforms", [])
    platform_link = game.get("link", None)
    request_link = session.meta_data.get("request_link", False)
    description = game.get("description",None)
    # Dynamic platform line (not templated)
    if user_platform and user_platform in game_platforms:
        platform_note = f"It’s available on your preferred platform: {user_platform}."
    elif user_platform:
        available = ", ".join(game_platforms)
        platform_note = (
            f"It’s not on your usual platform ({user_platform}), "
            f"but is available on: {available}."
        )
    else:
        platform_note = f"Available on: {', '.join(game_platforms)}."
        # :brain: User Prompt (fresh rec after rejection, warm tone, 20–25 words)
    is_last_session_game = game.get("last_session_game",{}).get("is_last_session_game") 
    if is_last_session_game:
        last_session_game = game.get("last_session_game", {}).get("title")
    tone = session.meta_data.get("tone", "neutral")
    liked_game = await get_most_similar_liked_title(db=db, session_id=session.session_id, current_title = game.get("title", None))
    # 🧠 Final Prompt
    user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like texting your best mate.

                Recommend **{game['title']}** using a {mood} mood and {tone} tone.

                Use this game description for inspiration: {description}
                The user previously liked the game: "{liked_game}"
                INCLUDE:  
                - If user has {liked_game} in their memory, You can draw a connection to the liked game, but don’t be obvious or repetitive. No hardcoded lines. Avoid templates like “If you liked X, you’ll love Y.”
                - Reflect the user's last message so they feel heard. 
                - A Draper-style mini-story (3–4 lines max) explaining why this game fits based on USER MEMORY & RECENT CHAT, making it feel personalized.  
                - Platform info ({platform_note}) mentioned casually, like a friend dropping a hint.  
                - Bold the title: **{game['title']}**.  
                - End with a fun, playful, or emotionally tone-matched line that invites a reply — a soft nudge or spark fitting the rhythm. Never robotic or templated prompts like “want more?”.

                NEVER:  
                - NEVER Use robotic phrasing or generic openers.  
                - NEVER Mention genres, filters, or system logic.  
                - NEVER Say “I recommend” or “available on…”.  
                - NEVER Mention or suggest any other game than **{game['title']}**. No invented or recalled games outside the data.

                Start mid-thought, as if texting a close friend.
            """.strip()
    print(f"User prompt: {user_prompt}")
    return user_prompt

async def explain_last_game_match(session):
    """
    This function generates a personalized response explaining how the last recommended game matches the user's preferences.
    """
    last_game_obj = session.game_recommendations[-1].game if session.game_recommendations else None
    if last_game_obj is not None:
        last_game = {
            "title": last_game_obj.title,
            "description": last_game_obj.description if last_game_obj.description else None,
            "genre": last_game_obj.genre,
            "game_vibes": last_game_obj.game_vibes,
            "complexity": last_game_obj.complexity,
            "visual_style": last_game_obj.graphical_visual_style,
            "has_story": last_game_obj.has_story,
            "available_in_platforms":[platform.platform for platform in last_game_obj.platforms]
        }
    else:
        last_game = None
    
    # Generate the user prompt with information about the user's feedback
    user_prompt = f"""
    Last suggested/Recommended game: "{last_game.get('title') if last_game else 'None'}"

    Write Thrum’s reply:
    - Describe the last suggested game shortly based on user's last input.
    - Match the user's tone and mood.
    - Do not add name in reply.
    Keep it under 25 words. Add 2–3 emojis that match the tone.
    """
    
    return user_prompt

async def handle_delivery(db: Session, session, user, classification):
    """
    This function handles whether to recommend a new game or explain the last recommended game based on user feedback.
    """
    # Check if a new recommendation is needed based on user preferences and classification
    should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

    if should_recommend:
        # If a new recommendation is needed, get the recommendation
        recommendation_response = await get_recommend(user=user, db=db, session=session)
        return recommendation_response  # Return the new recommendation
    else:
        # If no new recommendation is needed, explain the last recommended game based on user feedback
        explanation_response = await explain_last_game_match(session=session)
        return explanation_response  # Return the explanation of the last game

async def handle_reject_Recommendation(db,session, user,  classification,user_input):
    if classification.get("find_game", None) is None or classification.get("find_game") == "None":
        prompt = f"""
            {GLOBAL_USER_PROMPT}
            ---
            You don't know which game the user is asking or talking about. Ask them which game they're talking about in a friendly way. Keep it brief and natural.
        """.strip()
        return prompt
    if session.meta_data.get("ask_confirmation", False):
        tone = session.meta_data.get("tone", "neutral")
        print("---------------:handle_reject_Recommendation:-----------------")
        user_prompt = f"""
            {GLOBAL_USER_PROMPT}\n
            ---
            THRUM — GAME REJECTED FEEDBACK
            User said: "{user_input}"
            Tone: {tone}
            → The user disliked or rejected the last game.
            → Ask why they passed — like a close friend would. Could be tone, genre, art, or just not clicking. Don’t assume. Don’t list. Say something emotionally real, fresh, and never the same twice.
            → Reflect their tone naturally based on recent chat — bored, annoyed, chill, dry. Match it without sounding formal.
            → NEVER reuse phrasing, sentence structure, or emoji from previous replies.
            → Do NOT suggest another game yet.
            → You may mention mechanics, genre, or tone — but only if it fits emotionally.
            → After they reply, take the next step based on what they said:
            • If they ask for more info → give a 1–2 line summary, emotional and fresh.
            • If they already played it → ask if they want a new suggestion.
            • If it just didn’t match → ask gently if you should try something with a different feel.
            → Never suggest a game on your own if there is no game found
            🌟  Goal: Understand what didn’t land. Show you care about the “why” — not just the outcome.
            """
        print(":handle_reject_Recommendation prompt :",user_prompt)
        session.meta_data["ask_confirmation"] = False
        db.commit()
        return user_prompt
    else:
        from app.services.thrum_router.phase_discovery import handle_discovery
        if session.game_rejection_count >= 2:
            session.phase = PhaseEnum.DISCOVERY
            return await handle_discovery(db=db, session=session, user=user,user_input=user_input,classification=classification)
        else:
            should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)
            session_memory = SessionMemory(session,db)
            memory_context_str = session_memory.to_prompt()
            if should_recommend:
                session.phase = PhaseEnum.DELIVERY
                game, _ =  await game_recommendation(db=db, user=user, session=session)
                platform_link = None
                description = None
                mood = session.exit_mood  or "neutral"
                if not game:
                    user_prompt = NO_GAMES_PROMPT
                    return user_prompt
                    # Extract platform info
                preferred_platforms = session.platform_preference or []
                user_platform = preferred_platforms[-1] if preferred_platforms else None
                game_platforms = game.get("platforms", [])
                platform_link = game.get("link", None)
                request_link = session.meta_data.get("request_link", False)
                description = game.get("description",None)
                # Dynamic platform mention line (natural, not template)
                if user_platform and user_platform in game_platforms:
                    platform_note = f"It’s playable on your preferred platform: {user_platform}."
                elif user_platform:
                    available = ", ".join(game_platforms)
                    platform_note = (
                        f"It’s not on your usual platform ({user_platform}), "
                        f"but works on: {available}."
                        )
                else:
                    platform_note = f"Available on: {', '.join(game_platforms)}."
                tone = session.meta_data.get("tone", "neutral")
                liked_game = await get_most_similar_liked_title(db=db, session_id=session.session_id, current_title = game.get("title", None))
                rejected_game_title =  session.rejected_games[-1].title if session.rejected_games else None
                # Final user prompt for GPT
                user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                --------
                THRUM — FRIEND MODE: GAME REJECTED + NEXT SUGGESTION

                They passed on **{rejected_game_title}**. No big deal — you’re their friend, not a recommender.
                 The user previously liked the game: "{liked_game}"

                → If user has {liked_game} in their memory, You can draw a connection to the liked game, but don’t be obvious or repetitive. No hardcoded lines. Avoid templates like “If you liked X, you’ll love Y.”
                → React like someone who gets it — mirror the user’s mood ({mood}) and tone ({tone}) using chat history and memory. Don’t reset or explain.
                → Flow naturally into your next suggestion: **{game['title']}**.
                → Use the description below to build a Draper-style hook that fits their current vibe: {description}
                → Mention platform casually in the message: {platform_note}
                → End with a line that keeps the chat alive — a soft nudge, tease, or question that fits the emotional rhythm.
                → Never suggest a game on your own if there is no game found

                DON’T:
                - Apologize or explain
                - Reference the rejection logically
                - Pitch like a system
                - Use repeated sentence shapes or openers
                - Mention or suggest any other game or title besides **{game['title']}**. Do not invent or recall games outside the provided data.

                DO:
                - Sound like a friend who just read their reply
                - Feel totally in-flow — like the next thought in a real text thread
                """
                return user_prompt
            else:
                explanation_response = await explain_last_game_match(session=session)
                return explanation_response
            
async def deliver_game_immediately(db: Session, user, session, user_input, classification) -> str:
    from app.services.thrum_router.phase_discovery import handle_discovery
    """
    Instantly delivers a game recommendation, skipping discovery.

    Returns:
        str: GPT-formatted game message
    """
    session_memory = SessionMemory(session,db)
    if session.game_rejection_count >= 2:
            session.phase = PhaseEnum.DISCOVERY
            return await handle_discovery(db=db, session=session, user=user,user_input=user_input,classification=classification)
    else:
        game, _ = await game_recommendation(db=db, user=user, session=session)
        print(f"Game recommendation: {game}")
        platform_link = None
        description = None

        if not game:
            user_prompt = NO_GAMES_PROMPT
            return user_prompt
        else:
            session_memory.last_game = game["title"]
            last_session_game = None
            is_last_session_game = game.get("last_session_game",{}).get("is_last_session_game") 
            if is_last_session_game:
                last_session_game = game.get("last_session_game", {}).get("title")
            # Get user's preferred platform
            preferred_platforms = session.platform_preference or []
            user_platform = preferred_platforms[-1] if preferred_platforms else None
            game_platforms = game.get("platforms", [])

            platform_link = game.get("link", None)
            request_link = session.meta_data.get("request_link", False)
            description = game.get("description",None)
            mood = session.exit_mood  or "neutral"
            # Build natural platform note
            if user_platform and user_platform in game_platforms:
                platform_note = f"It’s available on your preferred platform: {user_platform}."
            elif user_platform:
                available = ", ".join(game_platforms)
                platform_note = (
                    f"It’s not on your usual platform ({user_platform}), "
                    f"but is available on: {available}."
                )
            else:
                platform_note = f"Available on: {', '.join(game_platforms) or 'many platforms'}."
            tone = session.meta_data.get("tone", "neutral")
            liked_game = await get_most_similar_liked_title(db=db, session_id=session.session_id, current_title = game.get("title", None))
            # :brain: Final Prompt
            user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like texting your best mate.

                Recommend **{game['title']}** using a {mood} mood and {tone} tone.

                Use this game description for inspiration: {description}
                 The user previously liked the game: "{liked_game}"

                INCLUDE:  
                - If user has {liked_game} in their memory, You can draw a connection to the liked game, but don’t be obvious or repetitive. No hardcoded lines. Avoid templates like “If you liked X, you’ll love Y.”
                - Reflect the user's last message so they feel heard. 
                - A Draper-style mini-story (3–4 lines max) explaining why this game fits based on USER MEMORY & RECENT CHAT, making it feel personalized.  
                - Platform info ({platform_note}) mentioned casually, like a friend dropping a hint.  
                - Bold the title: **{game['title']}**.  
                - End with a fun, playful, or emotionally tone-matched line that invites a reply — a soft nudge or spark fitting the rhythm. Never robotic or templated prompts like “want more?”.

                NEVER:  
                - NEVER Use robotic phrasing or generic openers.  
                - NEVER Mention genres, filters, or system logic.  
                - NEVER Say “I recommend” or “available on…”.  
                - NEVER Mention or suggest any other game than **{game['title']}**. No invented or recalled games outside the data.

                Start mid-thought, as if texting a close friend.
            """.strip()
            return user_prompt

async def diliver_similar_game(db: Session, user, session, user_input, classification) -> str:
    from app.services.thrum_router.phase_discovery import handle_discovery
    """
    Delivers a game similar to the user's last liked game.
    Returns:
        str: GPT-formatted game message
    """
    session_memory = SessionMemory(session,db)
    if session.game_rejection_count >= 2:
        session.phase = PhaseEnum.DISCOVERY
        return await handle_discovery(db=db, session=session, user=user,user_input=user_input,classification=classification)
    game, _ = await game_recommendation(db=db, user=user, session=session)
    print(f"Similar game recommendation: {game}")
    if not game:
        user_prompt = NO_GAMES_PROMPT
        return user_prompt
    else:
        session_memory.last_game = game["title"]
        # Get user's preferred platform
        preferred_platforms = session.platform_preference or []
        user_platform = preferred_platforms[-1] if preferred_platforms else None
        game_platforms = game.get("platforms", [])
        platform_link = game.get("link", None)
        request_link = session.meta_data.get("request_link", False)
        description = game.get("description",None)
        mood = session.exit_mood  or "neutral"
        # Build natural platform note
        if user_platform and user_platform in game_platforms:
            platform_note = f"It’s available on your preferred platform: {user_platform}."
        elif user_platform:
            available = ", ".join(game_platforms)
            platform_note = (
                f"It’s not on your usual platform ({user_platform}), "
                f"but is available on: {available}."
            )
        else:
            platform_note = f"Available on: {', '.join(game_platforms) or 'many platforms'}."
        # :brain: Final Prompt\
        tone = session.meta_data.get("tone", "neutral")
        liked_game = await get_most_similar_liked_title(db=db, session_id=session.session_id, current_title = game.get("title", None))
        user_prompt = f"""
            {GLOBAL_USER_PROMPT}\n
            ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like texting your best mate.

                Recommend **{game['title']}** using a {mood} mood and {tone} tone.

                Use this game description for inspiration: {description}
                

                INCLUDE:  
                - If user has {liked_game} in their memory, You can draw a connection to the liked game, but don’t be obvious or repetitive. No hardcoded lines. Avoid templates like “If you liked X, you’ll love Y.”
                - Reflect the user's last message so they feel heard. 
                - A Draper-style mini-story (3–4 lines max) explaining why this game fits based on USER MEMORY & RECENT CHAT, making it feel personalized.  
                - Platform info ({platform_note}) mentioned casually, like a friend dropping a hint.  
                - Bold the title: **{game['title']}**.  
                - End with a fun, playful, or emotionally tone-matched line that invites a reply — a soft nudge or spark fitting the rhythm. Never robotic or templated prompts like “want more?”.

                NEVER:  
                - NEVER Use robotic phrasing or generic openers.  
                - NEVER Mention genres, filters, or system logic.  
                - NEVER Say “I recommend” or “available on…”.  
                - NEVER Mention or suggest any other game than **{game['title']}**. No invented or recalled games outside the data.

                Start mid-thought, as if texting a close friend.
            ---
                → The user wants another game like the one they liked.
                → Confirm that you're on it — but make it Draper-style: confident, curious, emotionally alive.
                → Use a new rhythm and vibe — sometimes hyped, sometimes teasing, sometimes chill — based on recent mood.
                → You can casually mention what hit in the last one (genre, pacing, tone, mechanics), but never like a system log. Talk like a close friend would on WhatsApp.
                → NEVER repeat phrasing, emoji, or sentence structure from earlier replies.
                🌟  Goal: Make the moment feel human — like you're really listening and about to serve something *even better*. Rebuild energy and keep the conversation alive.
            """
        return user_prompt
    

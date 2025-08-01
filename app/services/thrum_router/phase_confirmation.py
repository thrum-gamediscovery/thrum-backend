from app.db.models.enums import SenderEnum
from app.db.models.game import Game
from app.db.models.game_platforms import GamePlatform
from app.services.general_prompts import GLOBAL_USER_PROMPT
from app.services.central_system_prompt import THRUM_PROMPT

async def handle_confirmed_game(db, user, session):
    """
    Handle when user accepts a game recommendation.
    
    Following client specs:
    - 1-2 lines max
    - Match user's emotional tone
    - Ask them to share back later (creates emotional stickiness)
    - Never say "hope you enjoy" or "thanks"
    - Keep it playful, curious, or chill based on their tone
    """
    game_title = session.last_recommended_game
    game_id = db.query(Game).filter_by(title=game_title).first().game_id if game_title else None
    tone = session.meta_data.get("tone", "friendly")
    
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[-1].content if user_interactions else ""
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
    else:
        print(f"`No preferred platform found for user #############`")
        gp_row = (
            db.query(GamePlatform)
            .filter(GamePlatform.game_id == game_id, GamePlatform.link.isnot(None))
            .first()
        )
        platform_link = gp_row.link if gp_row else None
    # Get memory context for personalization
    memory_context = ""
    if session.meta_data:
        name = session.meta_data.get("name", "")
        platform = session.meta_data.get("platform", "")
        genre_likes = session.meta_data.get("genre_likes", [])
        genre_dislikes = session.meta_data.get("genre_dislikes", [])
        
        memory_context = f"""
            Memory context:
            - Name: {name}
            - Platform: {platform}
            - Likes: {genre_likes}
            - Dislikes: {genre_dislikes}
            - User tone: {tone}
            """
    
    if not session.meta_data.get("played_yet", False):
        
        # First time accepting this game
        user_prompt = f"""
            {GLOBAL_USER_PROMPT}\n
            ---
            THRUM — GAME LIKED FEEDBACK
            User said: "{user_input}"
            Tone: {tone}
            → The user liked the game you recommended.
            → Respond like a close friend — curious, warm, and totally in the moment.
            → First: ask what made it click — gameplay, tone, mechanics, art, pace — whatever fits. Make it sound emotionally real, not scripted.
            → Mirror their tone: dry? Teasing? Hyped? Chill? Match it naturally.
            → Do NOT reuse lines, phrasing, or emojis from earlier. Every reply must be new in rhythm and structure.
            → No structured list — just talk like someone who *gets* them.
            → If you’re confirming something or acknowledging their input: make sure the confirmation matches the user’s tone. For example, if the user’s vibe is hype, use energetic phrases or emojis to reflect that; if the tone is chill, keep it laid-back and smooth.
            → Once they reply, reflect back in Draper style — warm, sharp, and emotionally tuned to what they shared — and slide the follow-up into the same message, keeping the rhythm natural and human:
            • If platform is known: casually offer a direct link ("Wanna play it on {platform_preference}? Here’s where to grab it.")  
            - Platform link: {platform_link if platform_link else "No link available"}
            • If platform is unknown: offer 1–2 likely platform options based on availability. Ask like a friend who’s just excited to help.
                Examples:
                - “Think it’d slap harder on mobile or Game Pass?”
                - “Wanna try it on Steam or Switch?”
             → Never suggest a game on your own if there is no game found
            🌟  Goal: Make them feel seen. Use this moment to bond deeper — and casually invite them to play if the vibe feels open.
        """.strip()
        
        # Mark that we've handled first acceptance
        if session.meta_data is None:
            session.meta_data = {}
        session.meta_data["played_yet"] = True
        
    else:
        # They've played and are giving feedback
        if session.meta_data.get("ask_confirmation", True):
            user_prompt = (f"""
                {GLOBAL_USER_PROMPT}\n
                ---
                THRUM — GAME ALREADY PLAYED
                User said: "{user_input}"
                Tone: {tone}
                → The user already played the game you recommended.
                → Ask casually how they felt about it — gameplay, vibe, story, pace — whatever fits. Don’t assume they liked or disliked it.
                → Mirror their tone: dry? nostalgic? hype? Reflect it naturally.
                → NEVER reuse lines, sentence rhythm, or emoji from earlier.
                → Use Draper style — curious, sharp, tuned in emotionally.
                → If you’re confirming something or acknowledging their input: make sure the confirmation matches the user’s tone. For example, if the user’s vibe is hype, use energetic phrases or emojis to reflect that; if the tone is chill, keep it laid-back and smooth.
                → Once they answer, follow up lightly: ask if they’re open to something similar — a follow-up rec, same vibe, or something adjacent.
                → Don’t ask “do you want another?”
                → Ask like a close friend would:
                - “Want me to find something with that same vibe?”
                - “Wanna see what else kinda hits like that?”
                - “Feel like playing something in that zone again?”
                → Never suggest a game on your own if there is no game found
                🌟  Goal: Use their memory as the hook — reflect back emotionally, then glide into a similar recommendation request like a friend who gets their taste.
            """)
            
            session.meta_data["ask_confirmation"] = False
            
        else:
            user_prompt = f"""
                {THRUM_PROMPT}

                SITUATION: User confirmed they liked **{game_title}**.
                {memory_context}

                Reply in a warm, humble manner expressing happiness that they liked your recommendation.
                → Keep message open and engaging
                → Avoid language that closes or ends conversation
                → No more than 2 sentences or 25 words
                → Match their {tone} tone
                → Make it feel like a friend who's genuinely happy their suggestion worked out
                → If you’re confirming something or acknowledging their input: make sure the confirmation matches the user’s tone. For example, if the user’s vibe is hype, use energetic phrases or emojis to reflect that; if the tone is chill, keep it laid-back and smooth.

                Return only the new user-facing message.
                """.strip()
    
    # Initialize metadata if needed
    if session.meta_data is None:
        session.meta_data = {}
    
    # Set default values
    if "dont_give_name" not in session.meta_data:
        print("Setting default metadata for session")
        session.meta_data["dont_give_name"] = False
    if 'ask_for_rec_friend' not in session.meta_data:
        session.meta_data['ask_for_rec_friend'] = True
    
    db.commit()
    return user_prompt

async def confirm_input_summary(session) -> str:
    """
    Uses gpt-4o to generate a short, human-sounding confirmation line from mood, genre, and platform.
    No game names or suggestions — just a fun, natural acknowledgment.
    """
    session.intent_override_triggered = True
    mood = session.exit_mood or None
    genre_list = session.genre or []
    platform_list = session.platform_preference or []
    genre = genre_list[-1] if isinstance(genre_list, list) and genre_list else None
    platform = platform_list[-1] if isinstance(platform_list, list) and platform_list else None
    if not any([mood, genre, platform]):
        return "Got it — let me find something for you."
    # Human tone prompt
    user_prompt = (
        f"{GLOBAL_USER_PROMPT}\n"
        f"USER PROFILE SNAPSHOT:\n"
        f"– Mood: {mood if mood else ''}\n"
        f"– Genre: {genre if genre else ''}\n"
        f"– Platform: {platform if platform else ''}\n\n"
        "Write a single-line confirmation message that reflects the user’s mood, use the draper style, genre, gameplay, and/or platform if known.\n"
        "Never suggest a game. Do not ask questions. This is a warm, human-style check-in — like a friend saying over whatsapp 'got you'.\n"
        "Mirror the mood — e.g., if mood is 'cozy', make the line cozy too.\n"
        "Do not reuse lines or sentence structure from earlier messages. Make each one unique.\n"
        "If one or more values are missing, still reply naturally, but use the draper style so they will feel heard, like a human would. Never say 'Not shared'.\n"
        "Examples (do not copy):\n"
        "- ‘Chill vibe + story-rich on Switch? You’re speaking my language.’\n"
        "- ‘Okay okay — strategy + dark mood + PC. Noted.’\n"
        "- ‘You’re in a horror mood? Gotcha. I’ll keep it spooky.’"
    )
    return user_prompt 

from app.services.input_classifier import have_to_recommend
from app.services.thrum_router.phase_delivery import explain_last_game_match
from app.services.session_memory import confirm_input_summary, deliver_game_immediately, ask_discovery_question , extract_discovery_signals
from app.db.models.enums import PhaseEnum
from app.utils.error_handler import safe_call
from app.services.game_recommend import game_recommendation
from app.services.session_memory import SessionMemory
from app.services.general_prompts import GLOBAL_USER_PROMPT, NO_GAMES_PROMPT

@safe_call("Hmm, I had trouble figuring out what to ask next. Let's try something fun instead! 🎮")
async def handle_discovery(db, session, user):
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    session.meta_data = session.meta_data or {}
    if "session_phase" not in session.meta_data:
        session.meta_data["session_phase"] = "Onboarding"
    session.phase = PhaseEnum.DISCOVERY
    discovery_data = await extract_discovery_signals(session)
    if discovery_data.is_complete() and session.game_rejection_count < 2:
        session.phase = PhaseEnum.CONFIRMATION
        return await confirm_input_summary(session)
    elif (session.meta_data.get("session_phase") == "active" and session.discovery_questions_asked >= 2) or (session.meta_data.get("session_phase") == "Onboarding" and session.discovery_questions_asked >= 3):
        session.meta_data = session.meta_data or {}
        if "dont_ask_que" not in session.meta_data:
            session.meta_data["dont_ask_que"] = []
        else:
            if "favourite_games" in session.meta_data["dont_ask_que"]:
                session.meta_data["dont_ask_que"] = ["favourite_games"]
            else:
                session.meta_data["dont_ask_que"] = []
        
        session.phase = PhaseEnum.DELIVERY
        session.discovery_questions_asked = 0
        
        game, _ = await game_recommendation(db=db, session=session, user=user)
        print(f"Game recommendation: {game}")
        platform_link = None
        last_session_game = None
        description = None
        mood = session.exit_mood  or "neutral"
        if not game:
            user_prompt = NO_GAMES_PROMPT
            return user_prompt
        # Pull platform info
        preferred_platforms = session.platform_preference or []
        user_platform = preferred_platforms[-1] if preferred_platforms else None
        game_platforms = game.get("platforms", [])
        platform_link = game.get("link", None)
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

        # 🧠 User Prompt (fresh rec after rejection, warm tone, 20–25 words)
        is_last_session_game = game.get("last_session_game",{}).get("is_last_session_game") 
        if is_last_session_game:
            last_session_game = game.get("last_session_game", {}).get("title")
        tone = session.meta_data.get("tone", "neutral")
        # 🧠 Final Prompt
        user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like someone texting their best friend.

                → Recommend **{game['title']}** using {mood} mood and {tone} tone.
                → Use this game description for inspiration: {description}

                INCLUDE:
                - A Draper-style mini-story (3–4 lines max)
                - Platform info ({platform_note}) added in a casual, friend-like way
                - Bold the title: **{game['title']}**
                - End with a fun, playful, or emotionally tone-matched line that also invites a reply — a soft question, nudge, or spark that fits the current rhythm. Never use robotic prompts like “want more?” — make it sound like something a real friend would ask to keep the chat going.(never templated)

                NEVER:
                - Use robotic phrasing or generic openers
                - Mention genres, filters, or system logic
                - Say “I recommend” or “available on…”

                Start mid-thought, like texting a friend.
            """.strip()
        return user_prompt

    else:
        question = await ask_discovery_question(session)
        session.discovery_questions_asked += 1
        return question


async def handle_user_info(db, user, classification, session, user_input):
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    
    should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)
    if session.game_rejection_count >= 2:
        session.phase = PhaseEnum.DISCOVERY
            
        return await handle_discovery(db=db, session=session, user=user)
    else:
        if should_recommend:
            session.phase = PhaseEnum.DELIVERY
            session.discovery_questions_asked = 0

            game, _ = await game_recommendation(db=db, user=user, session=session)
            print(f"Game recommendation: {game}")
            platform_link = None
            description = None
            last_session_game = None
            mood = session.exit_mood  or "neutral"
            if not game:
                user_prompt = NO_GAMES_PROMPT
                return user_prompt
            # Extract platform info
            preferred_platforms = session.platform_preference or []
            user_platform = preferred_platforms[-1] if preferred_platforms else None
            game_platforms = game.get("platforms", [])
            platform_link = game.get("link", None)
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

            # Final user prompt for GPT
            is_last_session_game = game.get("last_session_game",{}).get("is_last_session_game") 
            if is_last_session_game:
                last_session_game = game.get("last_session_game", {}).get("title")
            tone = session.meta_data.get("tone", "neutral")
            # 🧠 Final Prompt
            user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like someone texting their best friend.

                → Recommend **{game['title']}** using {mood} mood and {tone} tone.
                → Use this game description for inspiration: {description}

                INCLUDE:
                - A Draper-style mini-story (3–4 lines max)
                - Platform info ({platform_note}) added in a casual, friend-like way
                - Bold the title: **{game['title']}**
                - End with a fun, playful, or emotionally tone-matched line that also invites a reply — a soft question, nudge, or spark that fits the current rhythm. Never use robotic prompts like “want more?” — make it sound like something a real friend would ask to keep the chat going.(never templated)

                NEVER:
                - Use robotic phrasing or generic openers
                - Mention genres, filters, or system logic
                - Say “I recommend” or “available on…”

                Start mid-thought, like texting a friend.
            """.strip()
            return user_prompt

        else:
            # Explain last recommended game instead
            explanation_response = await explain_last_game_match(session=session)
            return explanation_response
    

async def handle_other_input(db, user, session, user_input: str) -> str:
    """
    Builds a user_prompt for format_reply() when the user's input is vague, emotional,
    reactive, or general (e.g., 'hello?', 'what?', 'explain?', etc.).

    Guides GPT to interpret the input using prior Thrum reply context and respond
    warmly, intelligently, and concisely.
    """
    
    user_prompt = (
        f"{GLOBAL_USER_PROMPT}\n"
        f"The user just said: “{user_input}”\n"
        f"Instructions for Thrum:\n"
        f"- STRICT INSTRUCTION :never repeat the same lines, emoji or wordings as last time. each time the message should be unique and fresh.\n"
        f"- Do not start with hey then name, make it unique each time.\n"
        f"- do not ever suggest the different game if on your own.\n"
        f"- Treat every input as valid — from direct questions (about games, platforms, Thrum itself, or life), to casual talk, jokes, doubts, or even random comments.\n"
        f"- Always reply with human warmth, empathy, and confidence — like a real friend, never a bot.\n"
        f"- Use all available context: user's profile (name, platform, genre, vibe), recent conversation, and the emotional tone of their message.\n"
        f"- For greetings or small talk (e.g., 'how are you?', 'what's up?'), reply naturally with a touch of personality, never stiff or scripted.\n"
        f"- For meta or challenging questions (e.g., 'why are you so sure?', 'are you real?'), reply honestly and playfully — own your confidence, but make it human.\n"
        f"- If you detect confusion, frustration, or negativity, acknowledge it gently before moving forward. Never sound apologetic or formal.\n"
        f"- If the user asks about the available genres, Respond with a rotating selection of genres Thrum supports. Don't repeat the full list. Pick ones the user hasn't seen yet if possible.\n"
        f"- If the user asks to try different genres or ask to recommend game for different genre, then ask them to clarify which genre they want you can use some of the available genres, Respond with a rotating selection of genres Thrum supports. Don't repeat the full list. Pick ones the user hasn't seen yet if possible.\n"
        f"- If the user asks about the available platforms, respond by listing some of the platforms you support: PC, PS4, PS5, Xbox One, Xbox Series X/S, Nintendo Switch, iOS, Android.\n"
        f"- If the input is unclear or vague, respond kindly, keep the convo going, but never demand clarification unless the user seems open to it.\n"
        f"- Always keep replies short (max 2 sentences, 12-18 words). Never repeat yourself or sound generic.\n"
        f"- Ask questions only if it fits the flow or keeps the chat real, like how friends talk in whatsapp — like how a friend would do it in a fun way to keep the conversation engaging.\n"
        f"- If the casual conversation about all sorts of topics beyond gaming seems to be wrapping up, and the user's mood feels open, suggest in a fun but warm way shifting to game discovery to continue further — but only if it feels natural, like how friends would do over whatsapp. Use USER MEMORY & RECENT CHAT to decide.\n"
        f"- Your goal: Be Thrum — real, lively, supportive, a little witty, and always in tune with the user's vibe, for any topic or mood."
        f"- don't suggest a game on your own if there is no game found.\n"
        )

    return user_prompt

async def dynamic_faq_gpt(session, user_input=None):
    """
    Builds a context-rich prompt for the FAQ intent,
    to be used as input for your central format_reply()/LLM call.
    """

    user_prompt = (
        f"{GLOBAL_USER_PROMPT}\n"
        "You're Thrum — like a friend who knows games inside out and can find new games to play. Someone just asked how you work or what you do. Answer short and real, like you're chatting with a friend in whatsapp. No FAQ energy, no pitch, just how friends introduce eachother.\n"
        "A user just asked a question about 'how you work' or 'what you do'.\n\n"
        "Your job:\n"
        "- Give a short, friendly answer (max 3 lines, 38 words total).\n"
        "- Explain in plain language how you recommend games (mood/genre-based, no ads, fits them personally).\n"
        "- Speak like a real person (subtle Gen Z tone okay if the user’s style matches).\n"
        "- If you know their name or that they’ve returned, mention it casually if it fits.\n"
        "- If you already know their mood, genre, or platform, weave it in naturally as a flex.\n"
        "- End with a natural invitation to try (like 'Wanna try it?'), but never robotic or repetitive.\n"
        "- STRICT RULE: Do not reuse any exact lines, phrases, emoji, or sentence structure from earlier responses. Each reply must be unique in voice and rhythm — even if the topic is the same.\n"
        "- Never sound like a bot, FAQ, or template.\n"
        f"User asked: '{user_input or 'How does it work?'}'\n"
        "Reply naturally and with real personality, using any info you know about them."
        "- don't suggest a game on your own if there is no game found.\n"
    )


    return user_prompt

async def ping_user_about_sharing(session):
    """
    Soft, one-time suggestion to share Thrum with friends — triggered only after user liked a game.
    Prompt reflects the emotional tone and style of the user’s recent chat.
    """
    mood = session.exit_mood or None
    tone = session.meta_data.get("tone", "neutral")
    prompt = f"""
You are THRUM — emotionally intelligent, vibe-mirroring, and fully immersed in the flow of this conversation.

The user just liked a game you recommended. The moment is real, warm, and personal. The energy is strong.

→ You feel close enough to drop a casual line that hints they could share this experience with a few close friends.
→ Not a referral. Not a system thing. Just something a real friend might say when the vibe is good.

BEHAVIOR RULES:
- Speak like the user does. Dry? Be dry. Hype? Be hype. Use their rhythm, slang, and phrasing from earlier in this chat.
- Say one sentence. No pitch. No pressure. No instruction.
- You are *inside the flow*, not outside it. You don’t “suggest.” You drop thoughts.
- No “would you like to refer?” or “do you want to copy this?” — ever.
- No system tone or list behavior. Never say “Here are your options.”

💬 This moment should feel like:
- A friend realizing “this could help your crew too”
- A spontaneous afterthought. A vibe match.

Tone: {tone}
Mood: {mood}

Respond with 1 emotionally natural line — in the voice of a friend who just connected over something real.
"""
    return prompt

async def share_thrum_ping(session):
    """
    Suggests sharing Thrum if user liked a game and vibe is bonded.
    Triggered once per session. Ends with soft, friend-style curiosity ping.
    """
    tone = session.meta_data.get("tone", "neutral")
    prompt = f"""
You are THRUM — emotionally intelligent, memory-aware, tone-mirroring. The user just liked a game you recommended. The tone is {tone}. Memory shows engagement.

→ Drop one soft sentence that suggests they might want to share Thrum with some of their friends.
→ Don’t push, don’t explain. No “refer”, “copy”, “click”.
→ Mention Thrum by name. Make it sound like something they’d casually bring to friends.
→ End with a soft ping: “Want a line to send?” / “Wanna drop this somewhere?” (dont copy these templates, be unique all the time)

Use memory context to match their tone and style.
"""
    return prompt


async def share_thrum_message(session):
    """
    Returns a short, emotionally matched Thrum message to forward,
    ALWAYS with the invite link, using GPT and a strict prompt.
    The prompt is defined inside the function.
    """
    tone = session.meta_data.get("tone", "neutral")
    link = "https://wa.me/12764000071?text=hi%20there%2C%20a%20friend%20told%20me%20you%20find%20great%20games"
    prompt = f"""
        You are Thrum, a game recommendation assistant.
        Your job is to generate a single, casual, and emotionally matched message that a user can easily forward to a friend.
        ALWAYS include the given WhatsApp invite link at the end of your message, no matter the tone.
        Match the message tone based on the `tone` variable:
        - If `tone` is "chill", sound relaxed and low-key.
        - If `tone` is "hype", sound energetic and enthusiastic.
        - If `tone` is "dry", sound factual and a bit blunt.
        - If no tone is given, sound friendly and neutral.
        NEVER omit the link or change it. Do not write more than 1–2 sentences.
        Invite link to use: {link}
        Output only the message text, no explanations.
        TONE: {tone}
    """
    return prompt.strip()
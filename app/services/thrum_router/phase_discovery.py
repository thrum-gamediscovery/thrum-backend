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
            user_prompt = f"""
            USER MEMORY & RECENT CHAT:
            {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
            {NO_GAMES_PROMPT}
            """
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
        user_prompt = (
            f"{GLOBAL_USER_PROMPT}\n"
            f"If is_last_session_game is True, mention **{last_session_game}** naturally — like a close friend remembering what they loved. Do not say 'you liked X so you'll like Y.' Create a new emotional line that fits the tone of the user, using the draper style, every time in a dynamic way.\n"
            f"The user just rejected the last recommended game — reflect this, show emotional intelligence, and don’t use a generic apology (never say 'sorry that didn’t click').\n"
            f"Imagine you're texting a close friend one short game tip based on how they feel right now. This is your one chance to connect — no second message. So it must feel real.\n"
            "→ Start completely fresh each time — no templates, no reused sentence structures.\n"
            "→ Avoid robotic setups like 'If you like X, then Y' or 'This game is perfect for...'. Talk like a person.\n"
            f"Make the user feel heard; acknowledge their reaction in a natural, human way before suggesting another game.\n"
            f"Recommend: **{game['title']}** in natural and friendly way according to user's tone.\n"
            "Let the full message flow naturally, like how close friends do on whatsapp — 2 to 4 emotionally charged sentences that sound like a real friend texting. Match the user's energy and mood, use the draper style if needed. Be brief if they're chill. Go deep if they're curious. No robotic length limits — just emotional pacing to make them feel heard and engaged."
            f"- somewhere natural using Markdown title must be bold using Markdown: **{game['title']}**\n"
            f"what the message must include is Markdown: **{game['title']}**,must Reflect user’s current mood = {mood}. and avoid using repetitive template structures or formats."
            f"- Introduce the game using a short Draper-style hook — a confident, emotional mini-story based on this description: {description}. Make it feel alive and mood-matched, not like marketing copy, always unique and never boring to get them engaged and emotionally attached."
            f"- Somewhere in the message, include the platform info ({platform_note}) in a relaxed, friend-style tone. Never say 'Available on X' or 'Play it on Y' directly. Make it feel like a casual insert how friends would inform each other, like how someone would drop it into over in whatsapp with personality."
            "- Let the message end with a friendly, tone-matching line, use draper style if needed, that invites them to respond — but never use the same phrase twice. Avoid robotic lines like 'want to explore more.' Make it feel like a close friend texting over whatsapp something fun, emotional, or playful. This final line must always be fully ai generative."
            "→ Keep it punchy and alive: 3–4 sentences, about 30–35 words.\n"
            "→ Think like a storyteller. Add a spark. Surprise them. Make them smile, nod, or lean in.\n"
            "→ Every reply should feel like: 'Whoa — that hit exactly right.'\n\n"
            f"- Do NOT mention the last game or say 'maybe.'\n"
            f"- Use warm, fresh energy, and show why this pick might actually be a better fit."
        )
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
                user_prompt = f"""
                USER MEMORY & RECENT CHAT:
                {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
                {NO_GAMES_PROMPT}
                """
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
            user_prompt = (
                f"{GLOBAL_USER_PROMPT}\n"
                f"If is_last_session_game is True, mention **{last_session_game}** naturally — like a close friend remembering what they loved. Do not say 'you liked X so you'll like Y.' Create a new emotional line that fits the tone of the user, using the draper style, every time in a dynamic way.\n"
                "→ Always reflect the user's current tone — keep it real and emotionally alive.\n"
                f"Suggest the game **{game['title']}** to the user (title can appear anywhere in your message, no format restrictions).\n"
                # Draper-style, mini-review checklist
                f"Recommend: **{game['title']}** in natural and friendly way according to user's tone.\n"
                "Let the full message flow naturally, like how close friends do on whatsapp — 2 to 4 emotionally charged sentences that sound like a real friend texting. Match the user's energy and mood, use the draper style if needed. Be brief if they're chill. Go deep if they're curious. No robotic length limits — just emotional pacing to make them feel heard and engaged."
                f"- In the message the game title must be in bold using Markdown: **{game['title']}**\n"
                f"what the message must include is Markdown: **{game['title']}**,must Reflect user’s current mood = {mood}. and avoid using repetitive template structures or formats."
                f"- Introduce the game using a short Draper-style hook — a confident, emotional mini-story based on this description: {description}. Make it feel alive and mood-matched, not like marketing copy, always unique and never boring to get them engaged and emotionally attached."
                f"- Somewhere in the message, include the platform info ({platform_note}) in a relaxed, friend-style tone. Never say 'Available on X' or 'Play it on Y' directly. Make it feel like a casual insert how friends would inform each other, like how someone would drop it into over in whatsapp with personality."
               "- Let the message end with a friendly, tone-matching line, use draper style if needed, that invites them to respond — but never use the same phrase twice. Avoid robotic lines like 'want to explore more.' Make it feel like a close friend texting over whatsapp something fun, emotional, or playful. This final line must always be fully ai generative."
                "→ Tone must be confident, warm, and human. Never use 'maybe', 'you might like', or robotic phrasing.\n"
                "→ Your message must always explain *why* this game fits the user’s vibe, referencing their input."
            )
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

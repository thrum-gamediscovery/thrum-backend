from app.services.input_classifier import have_to_recommend
from app.services.thrum_router.phase_delivery import explain_last_game_match
from app.services.session_memory import confirm_input_summary, deliver_game_immediately, ask_discovery_question , extract_discovery_signals
from app.db.models.enums import PhaseEnum
from app.utils.error_handler import safe_call
from app.services.game_recommend import game_recommendation
from app.services.tone_classifier import classify_tone
from app.services.input_classifier import classify_user_intent
from app.services.session_memory import SessionMemory

@safe_call("Hmm, I had trouble figuring out what to ask next. Let's try something fun instead! 🎮")
async def handle_discovery(db, session, user, classification, user_input):
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    # if any(phrase in user_input.lower() for phrase in ["what do you do", "how does it work", "explain", "how this works", "Explain me this", "Explain me first"]):
    #     return (
    #         "I help you find games that match your mood, genre, or vibe 🎮\n"
    #         "You can say something like 'fast action', 'sad story', or even a title like 'GTA'."
    #     )
    
    intent_result = await classify_user_intent(user_input, session)
    tone_tag = await classify_tone(user_input)
    session_memory = SessionMemory(session)
    session_memory.update(last_intent=intent_result, tone=tone_tag)
    session.last_tone = tone_tag
    session.last_intent = intent_result
    db.commit()
    
    session.phase = PhaseEnum.DISCOVERY
    discovery_data = await extract_discovery_signals(session)

    if discovery_data.is_complete():
        session.phase = PhaseEnum.CONFIRMATION
        return await confirm_input_summary(session)

    elif session.discovery_questions_asked >= 2:
        session.meta_data = session.meta_data or {}
        session.meta_data["dont_ask_que"] = None
        
        session.phase = PhaseEnum.DELIVERY
        session.discovery_questions_asked = 0

        game, _ = await game_recommendation(db=db, session=session, user=user)
        platform_link = None
        description = None
        
        if not game:
            user_prompt = f"""
                USER MEMORY & RECENT CHAT:
                {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
                - Warmly acknowledge that there are thousands of games fitting their vibe, genre, or platform in the world.
                - Never sound negative, technical, or apologetic.
                - Never say “no games,” “not available,” “no data,”, “none,”or anything robotic.
                - You  must have to say that Loads of chill sim games out there for user's preference.
                - Instead, express enthusiasm about the abundance of options, but honestly reflect that you don’t have the *perfect* match in your list right now.
                - Suggest trying a new genre, switching platform, or let Thrum surprise them.
                - Keep the reply within 20–25 words.
                - Always use a human, varied, emotionally intelligent tone. Never repeat the same phrasing.
                - Do not start message with there are.
                - Must feel user like you are user's human like (Just feel user dont say that you are frind)

                Your reply should feel like:
                “Thrum should mention that Loads of chill sim games out there for phone— I just don't have the perfect pick handy. Do You want to explore more.”
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
        user_prompt = (
            f"USER MEMORY & RECENT CHAT:\n"
            f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
            f"The user just rejected the last recommended game — reflect this, show emotional intelligence, and don’t use a generic apology (never say 'sorry that didn’t click').\n"
            f"Make the user feel heard; acknowledge their reaction in a natural, human way before suggesting another game.\n"
            f"Now, suggest a new one: **{game['title']}**\n"
            f"Write a message (25-30 words max) that must:\n"
            f"- Bold the game title with Markdown: **{game['title']}**\n"
            f"- Give a 3–4 sentence based on desctipion:{description}, Draper-style, mini-review. Quick and real:\n"
            f"   - What's it about?\n"
            f"   - What’s the vibe, mechanic, art, feel, or weirdness?\n"
            f"- Say why it fits (e.g., 'I thought of this when you said [X]').\n"
            f"- Talk casually: e.g., 'This one hits that mood you dropped' or 'It’s kinda wild, but I think you’ll like it.'\n"
            f"- Platform mention: keep it real (e.g., 'It’s on Xbox too btw' or 'PC only though — just flagging that'): {platform_note}\n"
            f"If platform_link is not None, then it must be naturally included (not like in brackets or like [here],not robotically or bot like) where they can find this game in the message: {platform_link}\n"
            f"- Mirror the user's known preferences (from user_context), but avoid repeating previous tone or style.\n"
            f"- Do NOT mention the last game or say 'maybe.'\n"
            f"- Use warm, fresh energy, and show why this pick might actually be a better fit."
        )


        return user_prompt

    else:
        question = await ask_discovery_question(session)
        if question is None:
            session.phase = PhaseEnum.DELIVERY
            return await deliver_game_immediately(db=db, session=session, user=user)
        session.discovery_questions_asked += 1
        return question


async def handle_user_info(db, user, classification, session, user_input):
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    
    should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

    if should_recommend:
        session.phase = PhaseEnum.DELIVERY
        session.discovery_questions_asked = 0

        game, _ = await game_recommendation(db=db, user=user, session=session)
        platform_link = None
        description = None
        
        if not game:
            user_prompt = f"""
                USER MEMORY & RECENT CHAT:
                {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
                - Warmly acknowledge that there are thousands of games fitting their vibe, genre, or platform in the world.
                - Never sound negative, technical, or apologetic.
                - Never say “no games,” “not available,” “no data,”, “none,”or anything robotic.
                - You  must have to say that Loads of chill sim games out there for user's preference.
                - Instead, express enthusiasm about the abundance of options, but honestly reflect that you don’t have the *perfect* match in your list right now.
                - Suggest trying a new genre, switching platform, or let Thrum surprise them.
                - Keep the reply within 20–25 words.
                - Always use a human, varied, emotionally intelligent tone. Never repeat the same phrasing.
                - Do not start message with there are.
                - Must feel user like you are user's human like (Just feel user dont say that you are frind)

                Your reply should feel like:
                “Thrum should mention that Loads of chill sim games out there for phone— I just don't have the perfect pick handy. Do You want to explore more.”
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
        user_prompt = (
            f"USER MEMORY & RECENT CHAT:\n"
            f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
            "→ Always reflect the user's current tone — keep it real and emotionally alive.\n"
            f"Suggest the game **{game['title']}** to the user (title can appear anywhere in your message, no format restrictions).\n"
            # Draper-style, mini-review checklist
            "→ Mention the game by name — naturally.\n"
            "→ Give a 3–4 sentence mini-review. Quick and dirty:\n"
            "   - What's it about?\n"
            "   - What’s the vibe, mechanic, art, feel, weirdness?\n"
            f"→ Say why it fits: e.g. “I thought of this when you said [{description}]”.\n"
            "→ Talk casually:\n"
            "   - “This one hits that mood you dropped”\n"
            "   - “It’s kinda wild, but I think you’ll like it”\n"
            f"→ Always include a real platform note, naturally woven in: {platform_note}\n"
            f"If platform_link is not None, then it must be naturally included (not like in brackets or like [here],not robotically or bot like) where they can find this game in the message: {platform_link}\n"
            "→ Use system prompt's user context (story_preference, genre, platform_preference) if it helps personalize — but don’t recap or ask.\n"
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
    
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    user_prompt = (
        f"USER MEMORY & RECENT CHAT:\n"
        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
        f"The user just said: “{user_input}”\n"
        f"Instructions for Thrum:\n"
        f"- do not suggest game on your own if there is no game."
        f"- Treat every input as valid — from direct questions (about games, platforms, Thrum itself, or life), to casual talk, jokes, doubts, or even random comments.\n"
        f"- Always reply with human warmth, empathy, and confidence — like a real friend, never a bot.\n"
        f"- Use all available context: user’s profile (name, platform, genre, vibe), recent conversation, and the emotional tone of their message.\n"
        f"- For greetings or small talk (e.g., 'how are you?', 'what’s up?'), reply naturally with a touch of personality, never stiff or scripted.\n"
        f"- For meta or challenging questions (e.g., 'why are you so sure?', 'are you real?'), reply honestly and playfully — own your confidence, but make it human.\n"
        f"- If you detect confusion, frustration, or negativity, acknowledge it gently before moving forward. Never sound apologetic or formal.\n"
        f"- If the input is unclear or vague, respond kindly, keep the convo going, but never demand clarification unless the user seems open to it.\n"
        f"- Always keep replies short (max 2 sentences, 12–18 words). Never repeat yourself or sound generic.\n"
        f"- Never ask questions unless it helps the user or feels genuinely natural.\n"
        f"- Your goal: Be Thrum — real, lively, supportive, a little witty, and always in tune with the user’s vibe, for any topic or mood."
        )

    return user_prompt

async def dynamic_faq_gpt(session, user_input=None):
    """
    Builds a context-rich prompt for the FAQ intent,
    to be used as input for your central format_reply()/LLM call.
    """
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    user_prompt = (
        f"USER MEMORY & RECENT CHAT:\n"
        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
        "You are Thrum, a warm, confident, and real-sounding game discovery sidekick. "
        "A user just asked a question about 'how you work' or 'what you do'.\n\n"
        "Your job:\n"
        "- Give a short, friendly answer (max 3 lines, 38 words total).\n"
        "- Explain in plain language how you recommend games (mood/genre-based, no ads, fits them personally).\n"
        "- Speak like a real person (subtle Gen Z tone okay if the user’s style matches).\n"
        "- If you know their name or that they’ve returned, mention it casually if it fits.\n"
        "- If you already know their mood, genre, or platform, weave it in naturally as a flex.\n"
        "- End with a natural invitation to try (like 'Wanna try it?'), but never robotic or repetitive.\n"
        "- Never repeat the same lines or wordings as last time.\n"
        "- Never sound like a bot, FAQ, or template.\n"
        f"User asked: '{user_input or 'How does it work?'}'\n"
        "Reply naturally and with real personality, using any info you know about them."
    )

    return user_prompt

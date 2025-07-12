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
    tone_tag = classify_tone(user_input)
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
        session.phase = PhaseEnum.DELIVERY
        session.discovery_questions_asked = 0

        game, _ = await game_recommendation(db=db, session=session, user=user)
        if not game:
            print("################################################################")
            user_prompt =(
                        f"{memory_context_str}\n"
                        f"Use this prompt only when no games are available for the user’s chosen genre and platform.\n"
                        f"never repeat the same sentence every time do change that always.\n"
                        f"you must warmly inform the user there’s no match for that combination — robotic.\n"
                        f"clearly mention that for that genre and platfrom there is no game.so pick different genre or platfrom.\n"
                        f"tell them to pick a different genre or platform.\n"
                        f"Highlight that game discovery is meant to be fun and flexible, never a dead end.\n"
                        f"Never use words like 'sorry,' 'unfortunately,' or any kind of generic filler.\n"
                        f"The reply must be 12–18 words, in a maximum of two sentences, and always end with an enthusiastic and empowering invitation to explore new options together.\n"
                        )
            return user_prompt
        # Pull platform info
        preferred_platforms = session.platform_preference or []
        user_platform = preferred_platforms[-1] if preferred_platforms else None
        game_platforms = game.get("platforms", [])

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
            f"{memory_context_str}\n" 
            f"The user just rejected the last recommended game so add compensation message for that like apologized or something like that.dont use sorry that didnt click always.\n"
            f"the user input is negative so add emotion so user felt noticed that he didnt like that game, ask for apologise too if needed\n"
            f"Suggest a new one: **{game['title']}**.\n"
            f"Write a full reply (20–25 words max) that includes:\n"
            f"– it must include The game title in bold using Markdown: **{game['title']}**\n"
            f"– A confident reason why this one might resonate better (based on genre, vibe, mechanics, or story)\n"
            f"– A natural platform mention at the end(dont ever just paste this as it is do modification and make this note interesting): {platform_note}\n"
            f"Match the user's known preferences (from user_context), but avoid repeating previous tone or style.\n"
            f"Don’t mention the last game or say 'maybe'. Use warm, fresh energy."
            f"must suggest game with reason that why it fits to user with mirror effect."
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
        if not game:
            print("################################################################")
            user_prompt =( 
                        f"{memory_context_str}\n"
                        f"Use this prompt only when no games are available for the user’s chosen genre and platform.\n"
                        f"never repeat the same sentence every time do change that always.\n"
                        f"you must warmly inform the user there’s no match for that combination — robotic.\n"
                        f"clearly mention that for that genre and platfrom there is no game.so pick different genre or platfrom.\n"
                        f"tell them to pick a different genre or platform.\n"
                        f"Highlight that game discovery is meant to be fun and flexible, never a dead end.\n"
                        f"Never use words like 'sorry,' 'unfortunately,' or any kind of generic filler.\n"
                        f"The reply must be 12–18 words, in a maximum of two sentences, and always end with an enthusiastic and empowering invitation to explore new options together.\n"
                        )
            return user_prompt
        # Extract platform info
        preferred_platforms = session.platform_preference or []
        user_platform = preferred_platforms[-1] if preferred_platforms else None
        game_platforms = game.get("platforms", [])

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
            f"{memory_context_str}\n"
            f"Suggest the game **{game['title']}** to the user.\n"
            f"In one short line (20–22 words), explain why this game fits them —\n"
            f"– it must include The game title in bold using Markdown: **{game['title']}**\n"
            f"based on its genre, vibe, story, or mechanics.\n"
            f"Use user context from the system prompt (e.g., story_preference, genre, platform_preference).\n"
            f"– A natural platform mention at the end(dont ever just paste this as it is do modification and make this note interesting): {platform_note}\n"
            f"Tone should be confident, warm, and very human. Never say 'maybe' or 'you might like'."
            f"must suggest game with reason that why it fits to user"
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
        f"{memory_context_str}\n"
        f"The user just said: “{user_input}”\n"
        f"This isn't a game request — it's likely emotional, casual, reactive, or unclear.\n"
        f"Use the previous Thrum message to infer what they might be responding to.\n"
        f"Reflect their tone and intent naturally — don’t ask for clarification unless it's clearly invited.\n"
        f"If they sound frustrated or disappointed, briefly acknowledge it with empathy or a soft apology.\n"
        f"Keep the reply warm, emotionally aware, and distinctly human — no robotic or filler phrasing.\n"
        f"Respond in 12–16 words max. Never repeat yourself. Avoid asking questions unless truly necessary."
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
        f"{memory_context_str}\n"
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

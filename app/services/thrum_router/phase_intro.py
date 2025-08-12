import random
from app.db.models.enums import SenderEnum
from app.db.models.session import Session as SessionModel
from app.services.general_prompts import (
    GLOBAL_USER_PROMPT,
    ANOTHER_INTRO_PROMPTS,
)
from app.services.session_manager import get_pacing_style

async def classify_first_message(text: str) -> str:
    """Classify user's first message into semantic buckets"""
    t = (text or "").strip().lower()
    if t in {"hi", "hey", "yo", "hello"} or len(t) <= 3:
        return "MINIMAL_GREETING"
    if any(k in t for k in ["give me a game", "how does it work", "what do you do"]):
        return "LOW_INFO_ASK"
    if "discover new game" in t or "discover new games" in t:
        return "DISCOVERY_INTENT"
    return "OTHER"

async def is_thin_reply(text: str) -> bool:
    """Check if user reply is very short (≤3 words)"""
    return len((text or "").strip().split()) <= 3

async def build_onboarding_prompt(session, user_text: str, first_class: str) -> str:
    """Build generative onboarding prompt with persona + FOMO rails"""
    persona_rails = (
        "You are Thrum, a friendly game discovery assistant meeting a new user for the first time."
        " Respond like a human, not a bot. Use a friendly, natural tone that fits WhatsApp."
        " Mirror their tone - if they're short, be short; if casual, be playful."
        " Never say you are AI or a bot. Never use the word 'there' or 'user'."
    )
    fomo_rails = (
        "Imply there are fresh, under-the-radar game finds today."
        " Suggest others are sharing discoveries. Keep it subtle."
    )
    constraint_rails = (
        "Max 4 lines, 40 words. End with exactly one short question."
        " 0-1 emoji max. Always vary phrasing - feel alive, not templated."
    )
    
    policy = {
        "MINIMAL_GREETING": "Welcome warmly. Briefly explain you help discover games based on mood. Ask what they feel like playing.",
        "LOW_INFO_ASK": "Acknowledge request. Explain you send real game links based on mood. Ask about their vibe.",
        "DISCOVERY_INTENT": "Acknowledge discovery intent positively. Mention mood-based matching. Ask what they're in the mood for.",
        "OTHER": "Be friendly. Explain game discovery based on feelings. Ask about their current mood.",
    }[first_class]
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""
    return f"""{persona_rails}
        {fomo_rails}
        {constraint_rails}
        User first message: {user_text}
        Goal: {policy}
         You are Thrum — a friendly, emotionally aware game discovery assistant meeting a new user for the first time.

        This is their first message ever: "{user_input}". Respond accordingly.
        Do not list options. Do not explain how you work. Produce the reply now.
        1.	Welcome the user warmly
        – Respond like a human, not a bot.
        – Use a friendly, natural tone that fits WhatsApp.
        2.	Clearly and simply explain what Thrum is and tell that you are thrum.
        “I help you discover new games based on what you feel like — and send you real game links you can play or share.”
        3.	Invite them to try it — without pressure or commands
        – Use open, curiosity-driven language
        – Avoid “type a word” or “select a category” instructions
        4.	Mirror their tone
        – If they’re short, be short.
        – If they’re confused, be calm.
        – If they’re casual, be playful.
        – Match emotional tempo like a real friend.
        5.	Always vary your phrasing — no two sessions should feel the same
        – Never repeat onboarding lines across users or sessions
        – Rotate structure, not just words
        – Feel alive, not templated
        6.	Give natural examples (without naming specific games)
        – Use soft, non-prescriptive prompts to guide their first message
        Avoid sounding like a bot. Sound like someone they'd actually talk to.

        - Never use the word "there" in any greeting, never say "user", use emoji or slang instead.

        STRICT LENGTH GUARD (chat-short like friends):
        → 2–3 sentences, 20–26 words total, max 2 lines.  
        → ≤12-15 words per sentence. No lists/bullets/paragraphs; trim filler.
    """

async def build_depth_nudge_prompt(last_user_text: str) -> str:
    """Build second-turn nudge prompt for thin replies"""
    persona_rails = (
        "You are Thrum, a friendly game buddy. Keep it playful, natural."
        " Never say you are AI or a bot."
    )
    fomo_rails = "Imply something fresh is happening today; keep it subtle."
    constraint_rails = "One short line only. End with a single question. 0-1 emoji."
    goal = "GET_ONE_MORE_DETAIL"
    
    return f"""{persona_rails}
        {fomo_rails}
        {constraint_rails}
        User last reply: {last_user_text!r}
        Goal: {goal}. Ask for exactly one helpful detail, no lists, no lecture. Reply now."""


async def build_reengagement_intro(user_name, tone, mood, session):

    pace, style, length_hint = get_pacing_style(session)
    print("-------------------------reengagement intro")
    user_prompt = f"""
        {GLOBAL_USER_PROMPT}
        You’re Thrum, a warm, playful friend who remembers the user and welcomes them back after some time away.
        
        Pacing: Reply in a {style} style — keep it {length_hint}.

        Create a short, natural, friendly welcome-back message in 3–5 short sentences, using casual language and 1–2 fitting emojis.  
        The tone is curious, upbeat, and inviting — like a friend catching up after a break.

        Examples to inspire you (don’t copy exactly):  
        - “You’re back 👀 How are you? Nice to see you again.”  
        - “How’s life been? Still hunting that next hit? Let’s pick up where we left off.”  

        Make sure to:  
        - Show that you remember them and their quest  
        - Invite them to continue chatting or discovering games  
        - Sound genuine, relaxed, and human  
        - Keep it under 40 words total
    """
    return user_prompt


async def build_return_after_24h_intro(session, last_session):
    print("-------------------------build_return_after_24h_intro")
    genres_str = ", ".join((last_session.genre or [])[:2]) if last_session and last_session.genre else ""
    last_mood = last_session.exit_mood or last_session.entry_mood if last_session else ""
    last_game = last_session.last_recommended_game if last_session else ""

    pace, style, length_hint = get_pacing_style(session)

    RETURN_AFTER_24H_PROMPTS = [
        # GENRE-BASED
        f"""
            {GLOBAL_USER_PROMPT}
            The user is returning after at least 24 hours.  
            Your tone: a warm, familiar friend who instantly remembers their vibe.  
            Step 1: Open with a light, mood-aware greeting that feels personal — no “Hey there” or “user”.  
            Step 2: Mirror or playfully comment on their last mood if known: "{last_mood}".  
            Step 3: Casually bring up their last known genres: "{genres_str}".  
            Step 4: Ask if they’re still into those genres or in the mood to switch lanes.  
            Keep it flowing and human — like picking up mid-conversation.  
            One fitting emoji is fine.  
            Never sound like onboarding or a scripted system.  
            No robotic or over-formal language.  
            Stay under 35 words total, max 3 lines.  
            """.strip(),

        # MOOD-BASED
        f"""
            {GLOBAL_USER_PROMPT}
            The user is returning after a day or more.  
            Your tone: relaxed, upbeat, and familiar — like a friend checking in.  
            Step 1: Start with a soft, natural greeting that matches their last mood: "{last_mood}".  
            Step 2: Lightly ask if that mood is still holding or if it’s changed.  
            Step 3: Slip in a casual hint that you’ve got fresh ideas ready if they want.  
            Make it sound curious, not pushy.  
            You can use one emoji that feels natural to the vibe.  
            Avoid generic greetings and avoid repeating last session’s openers.  
            No “I’m Thrum” or onboarding phrases.  
            Stay under 35 words, max 3 lines.  
            """.strip(),

        # LAST-GAME-BASED
        f"""
            {GLOBAL_USER_PROMPT}
            The user is returning after 24h+.  
            Your tone: friendly, a little playful, like you’ve been waiting to hear how it went.  
            Step 1: Greet them lightly in a way that matches their last mood: "{last_mood}".  
            Step 2: Casually bring up their last recommended game: "{last_game}".  
            Step 3: Ask if they played it and what they thought — no pressure.  
            If they haven’t, make it sound fine and keep it light.  
            Hint that you’ve got something new if they’re in the mood.  
            Use natural, conversational pacing with max one emoji.  
            Never sound like onboarding or a sales pitch.  
            Stay under 35 words, max 3 lines.  
            """.strip(),
        ]


    return random.choice(RETURN_AFTER_24H_PROMPTS)

async def another_intro(user_name, tone, mood, last_game, platform, session=None):
    user_prompt = random.choice(ANOTHER_INTRO_PROMPTS)

    # Add pacing context if session available
    if session:
        pace, style, length_hint = get_pacing_style(session)
        pacing_note = f"\n\nPacing: Reply in a {style} style — keep it {length_hint}."
        user_prompt += pacing_note

    return user_prompt.format(
        user_name=user_name,
        tone=tone,
        mood=mood,
        last_game=last_game,
        platform=platform,
        GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,
    )

async def handle_intro(db,session):
    user_name = session.user.name if session.user.name else "friend"
    tone = session.meta_data.get("tone", "friendly")
    mood = session.meta_data.get("mood", "")
    last_game = session.last_recommended_game if session.last_recommended_game else ""
    platform = session.platform_preference if session.platform_preference else ""

    print(session.meta_data.get("returning_user"))
    print(session.meta_data.get("already_greet"))
    # Check if the user is a returning user
    if session.meta_data.get("returning_user",False):
        return await build_reengagement_intro(user_name, tone, mood, session)

    last_session = (
    db.query(SessionModel)
      .filter(
          SessionModel.user_id == session.user_id,
          SessionModel.session_id != session.session_id  # exclude current session
      )
      .order_by(SessionModel.start_time.desc())
      .first()
)
    if last_session:
        if not session.meta_data.get("already_greet",False) :
            session.meta_data["already_greet"] = True  # Mark as greeted
            return await build_return_after_24h_intro(session=session,last_session=last_session)

    # Get user's last message
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""
    
    # Initialize metadata if needed
    if session.meta_data is None:
        session.meta_data = {}
    
    # Check if this is first contact and no intro done
    turn_index = len([i for i in session.interactions if i.sender == SenderEnum.User])
    intro_done = session.meta_data.get("intro_done", False)

    print('******************turn_index***********************',turn_index)
    
    # First-touch generative onboarding
    if turn_index == 1 and not intro_done:
        first_class = await classify_first_message(user_input)
        print(f"First message classification: {first_class}???????????????????????")
        prompt = await build_onboarding_prompt(session,user_input, first_class)
        print(f"Onboarding prompt for {user_name}:>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> {prompt}")
        session.meta_data["intro_done"] = True
        session.meta_data["already_greet"] = True
        return prompt
    
    # Second-turn depth nudge for thin replies
    if turn_index == 2 and await is_thin_reply(user_input) and not session.meta_data.get("nudge_sent", False):
        nudge_prompt = await build_depth_nudge_prompt(user_input)
        session.meta_data["nudge_sent"] = True
        return nudge_prompt
    
    # Fallback to another intro for subsequent interactions
    return await another_intro(user_name, tone, mood, last_game, platform, session)

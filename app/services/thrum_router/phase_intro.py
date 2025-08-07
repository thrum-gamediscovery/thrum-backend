import random
from app.db.models.enums import SenderEnum
from app.services.general_prompts import (
    GLOBAL_USER_PROMPT,
    ANOTHER_INTRO_PROMPTS,
)
from app.services.session_manager import get_pacing_style


async def handle_intro(session):
    user_name = session.user.name if session.user.name else "friend"
    tone = session.meta_data.get("tone", "friendly")
    mood = session.meta_data.get("mood", "")
    last_game = session.last_recommended_game if session.last_recommended_game else ""
    platform = session.platform_preference if session.platform_preference else ""

    print('test...................')
    print(session.meta_data.get("returning_user"))
    print(session.meta_data.get("already_greet"))
    # Check if the user is a returning user
    if session.meta_data.get("returning_user"):
        # return build_reengagement_intro(user_name, tone, mood, session)
        return another_intro(user_name, tone, mood, last_game, platform, session)
    
    # Ensure the 'already_greet' key exists in metadata and set it to False if it's missing
    if session.meta_data.get("already_greet") is None:
        session.meta_data["already_greet"] = False  # Initialize if not present

    # If the user has not been greeted, greet them for the first time
    if not session.meta_data.get("already_greet"):
        session.meta_data["already_greet"] = True  # Mark as greeted
        return build_first_time_intro(session)

    # If the user has already been greeted, show another intro
    return another_intro(user_name, tone, mood, last_game, platform, session)


def build_first_time_intro(session):
    print('build_first_time_intro...............................@@')
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""

    user_prompt = f"""
        You are Thrum — a friendly, emotionally aware game discovery assistant meeting a new user for the first time.

        This is their first message ever: "{user_input}". Respond accordingly.
        Goals:
        1.	Welcome the user warmly
        – Respond like a human, not a bot.
        – Use a friendly, natural tone that fits WhatsApp.
        2.	Clearly and simply explain what Thrum is
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
        – Don’t use these exactly, but aim for variety like:
        • “something short and fun”
        • “a deep experience”
        • “chill for the weekend”
        • “something I could send to a friend”
        • “a weird one I’d never find myself”

        Avoid sounding like a bot. Sound like someone they'd actually talk to.

        - Never use the word "there" in any greeting, never say "user", use emoji or slang instead.
        - Message Should Be: Max 4 lines, 40 words.
    """.strip()

    # Add pacing context if session available
    if session:
        pace, style, length_hint = get_pacing_style(session)
        pacing_note = f"\n\nPacing: Reply in a {style} style — keep it {length_hint}."
        user_prompt += pacing_note

    return user_prompt

def another_intro(user_name, tone, mood, last_game, platform, session=None):
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


def build_reengagement_intro(user_name, tone, mood, session):

    pace, style, length_hint = get_pacing_style(session)

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

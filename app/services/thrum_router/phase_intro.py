import random
from app.db.models.enums import SenderEnum
from app.services.general_prompts import (
    GLOBAL_USER_PROMPT,
    ANOTHER_INTRO_PROMPTS,
)
from app.services.session_manager import get_pacing_style

def classify_first_message(text: str) -> str:
    """Classify user's first message into semantic buckets"""
    t = (text or "").strip().lower()
    if t in {"hi", "hey", "yo", "hello"} or len(t) <= 3:
        return "MINIMAL_GREETING"
    if any(k in t for k in ["give me a game", "how does it work", "what do you do"]):
        return "LOW_INFO_ASK"
    if "discover new game" in t or "discover new games" in t:
        return "DISCOVERY_INTENT"
    return "OTHER"

def is_thin_reply(text: str) -> bool:
    """Check if user reply is very short (≤3 words)"""
    return len((text or "").strip().split()) <= 3

def build_onboarding_prompt(user_text: str, first_class: str) -> str:
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
    
    return f"""{persona_rails}
{fomo_rails}
{constraint_rails}
User first message: {user_text!r}
Goal: {policy}
Do not list options. Do not explain how you work. Produce the reply now."""

def build_depth_nudge_prompt(last_user_text: str) -> str:
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


async def handle_intro(session):
    user_name = session.user.name if session.user.name else "friend"
    tone = session.meta_data.get("tone", "friendly")
    mood = session.meta_data.get("mood", "")
    last_game = session.last_recommended_game if session.last_recommended_game else ""
    platform = session.platform_preference if session.platform_preference else ""

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
        first_class = classify_first_message(user_input)
        print(f"First message classification: {first_class}???????????????????????")
        prompt = build_onboarding_prompt(user_input, first_class)
        print(f"Onboarding prompt for {user_name}:>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> {prompt}")
        session.meta_data["intro_done"] = True
        session.meta_data["already_greet"] = True
        return prompt
    
    # Second-turn depth nudge for thin replies
    if turn_index == 2 and is_thin_reply(user_input) and not session.meta_data.get("nudge_sent", False):
        nudge_prompt = build_depth_nudge_prompt(user_input)
        session.meta_data["nudge_sent"] = True
        return nudge_prompt
    
    # Check if the user is a returning user
    if session.meta_data.get("returning_user"):
        return another_intro(user_name, tone, mood, last_game, platform, session)
    
    # Fallback to another intro for subsequent interactions
    return another_intro(user_name, tone, mood, last_game, platform, session)


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
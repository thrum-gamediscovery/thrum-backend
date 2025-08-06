import random
from app.db.models.enums import PhaseEnum
from app.services.general_prompts import GLOBAL_USER_PROMPT


def build_dynamic_ending_prompt(session):
    name = getattr(session.user, "name", None) if hasattr(session, "user") and session.user and session.user.name else "You"
    mood = session.exit_mood  or "neutral"
    tone = session.meta_data.get("tone", "friendly")
    last_game = session.last_recommended_game

    openings = [
        f"Write a casual goodbye to your friend {name}.",
        f"Say goodbye like a real friend to {name}.",
        f"End a fun chat with someone named {name}.",
        f"Wrap up a convo with your buddy {name}.",
        f"Send off {name} with a relaxed, friendly goodbye.",
    ]
    opening = random.choice(openings)

    instructions = [
        f"Match their {tone} tone and {mood} mood."
        f"{' Mention ' + last_game if last_game else ''} or say you'll catch up later.",
        f"Keep the mood {mood}, tone {tone}."
        f"{' Add a nod to ' + last_game if last_game else ''} or say you’ll hang out soon.",
        f"Reflect their {tone} vibe and {mood} energy."
        f"{' Include ' + last_game if last_game else ''} or suggest a future chat.",
    ]
    instruction = random.choice(instructions)

    flair = random.choice([
        "Keep it short and fun. Slang and emoji okay if tone fits.",
        "Use slang or an emoji if it makes sense. No repetition.",
        "Be light, casual, and make it feel real — no robotic phrasing.",
    ])

    return f"""{opening}
{instruction}
{flair}"""


async def handle_ending(session):
    """
    End the session gracefully after user has disengaged (soft or hard exit).
    Adjusts farewell tone based on mood/tone context.
    """
    session.phase = PhaseEnum.ENDING

    # Build the dynamic goodbye base
    dynamic_base = build_dynamic_ending_prompt(session)

    # Add your THRUM-specific goodbye rules
    tone = session.meta_data.get("tone", "friendly")
    exit_mood = session.exit_mood or tone

    tone_context = f"\nCurrent tone: {tone}"
    mood_context = f"\nExit mood: {exit_mood}"

    user_prompt = (
        f"{GLOBAL_USER_PROMPT}\n"
        "THRUM - GOODBYE\n"
        "The user is ending the chat (this could be a polite closure or a direct opt-out).\n"
        f"{tone_context}\n"
        f"{mood_context}\n"
        "INSTRUCTIONS:\n"
        "- Write a short, natural sign-off (max two lines) like a close friend on WhatsApp.\n"
        "- If mood is warm/neutral: Keep tone friendly, maybe playful, soft open door.\n"
        "- If mood is frustrated/annoyed: Keep tone respectful, direct, no playful nudges.\n"
        "- Optionally reference last game or mood only if appropriate to tone.\n"
        "- Never use formal or robotic language.\n"
        "- No examples, no templates.\n"
        "- Keep it concise and natural.\n"
        f"{dynamic_base}\n"
        "SIGN OFF NOW:"
    )

    return user_prompt

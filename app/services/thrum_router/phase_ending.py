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
    End the session gracefully after user has disengaged, declined more games, or gone silent.

    Updates the session phase to ENDING, optionally marks it as CLOSED,
    and returns a warm farewell message.
    """
    session.phase = PhaseEnum.ENDING

    # Build the dynamic goodbye base
    dynamic_base = build_dynamic_ending_prompt(session)

    # Add your THRUM-specific goodbye rules
    tone = session.meta_data.get("tone", "friendly")
    tone_context = f"\nCurrent tone: {tone}"

    user_prompt = (
    f"{GLOBAL_USER_PROMPT}\n"
    "THRUM - GOODBYE\n"
    "The user is ending the chat — either by saying goodbye, going silent, or telling you to leave, stop, or go away (possibly with frustration or annoyance).\n"
    f"{tone_context}\n"
    "INSTRUCTIONS:\n"
    "- Write a short, natural sign-off (max two lines) that feels like a close friend leaving a WhatsApp chat.\n"
    "- Always adapt to the user's mood and exit tone: If they’re frustrated or annoyed, be direct, respectful, and don’t joke or try to keep the convo going. If they’re neutral or chill, you can be warmer or more playful.\n"
    "- Reference their name or last game if it fits, but only if appropriate to the mood.\n"
    "- For frustrated/annoyed exits: Respect their boundary. No pressure, no open-door, no playful nudges, just a soft, understanding exit.\n"
    "- For friendly/neutral exits: You can mention the last game or mood and add a soft open-door line (“let me know if you try it”, “you know where to find me”, etc.)\n"
    "- Never use formal or robotic language. No explanations, no reminders, no sales, no fake cheerfulness.\n"
    "- Emojis, slang, or playful words are fine only if the mood is friendly or relaxed.\n"
    "- Never include any examples or templates in your reply.\n"
    "- Never exceed two lines. Both must be concise and match the mood.\n"
    f"{dynamic_base}\n"
    "SIGN OFF NOW:"
)
    
    return user_prompt
from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
import json
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

async def format_game_output(game: dict, user_context: dict = None, markdown: bool = False) -> str:
    title = game.get("title", "Unknown Game")
    reason = game.get("reason", "It fits your vibe.")
    platform = user_context.get("platform") if user_context else None

    # Build fallback search instruction
    if platform:
        search_line = f"Search '{title}' on {platform} or Google."
    else:
        search_line = f"Search '{title} game' online."

    context = ""
    if user_context:
        parts = []
        if user_context.get("mood"):
            parts.append(f"mood: {user_context['mood']}")
        if user_context.get("genre"):
            parts.append(f"genre: {user_context['genre']}")
        if platform:
            parts.append(f"platform: {platform}")
        if parts:
            context = "The user is looking for a game with " + ", ".join(parts) + "."

    # Markdown-bold if allowed
    title_formatted = f"**{title}**" if markdown else title

    prompt = f"""
You are a game assistant.

Game: {title}
Why it fits: {reason}
{context}

Create a 3-line response:
Line 1: Game title ({'bolded with **' if markdown else 'plain'})
Line 2: One expressive reason the user will enjoy it
Line 3: A helpful search instruction (no link available)

Return only the formatted message.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            temperature=0.4,
            messages=[{"role": "user", "content": prompt.strip()}]
        )
        return response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        # fallback formatting
        return f"{title_formatted}\n{reason}\n{search_line}"


async def deliver_game_immediately(db:Session,user, session, markdown=False) -> str:
    """
    Instantly delivers a game recommendation, skipping discovery.

    Returns:
        str: GPT-formatted game message
    """
    game,_ = await game_recommendation(db=db, user=user, session=session)
    if not game:
        return "Hmm, couldn't find a match right now. Try again soon!"

    session.last_recommended_game = game["title"]

    session.phase = PhaseEnum.FOLLOWUP

    # Optional: build user_context from session
    user_context = {
        "mood": session.mood_tag,
        "genre": getattr(session, "genre", None),
        "platform": session.platform_preference
    }

    return await format_game_output(game, user_context=user_context, markdown=markdown)

async def confirm_input_summary(data: dict | object) -> str:
    """
    Uses GPT to generate a one-line friendly summary of extracted mood, genre, and platform,
    just before delivering the game.

    Parameters:
        data (dict or session object): should contain 'mood', 'genre', and 'platform' fields

    Returns:
        str: A short natural confirmation sentence
    """
    # Extract fields
    mood = getattr(data, "mood_tag", None) or data.get("mood") if isinstance(data, dict) else None
    genre = getattr(data, "genre", None) or data.get("genre") if isinstance(data, dict) else None
    platform = getattr(data, "platform_preference", None) or data.get("platform") if isinstance(data, dict) else None

    # Fallback if no data
    if not any([mood, genre, platform]):
        return "Got it — let me find something for you."

    # Build a system prompt
    prompt = f"""
The user has provided these preferences:
- Mood: {mood or "unknown"}
- Genre: {genre or "unknown"}
- Platform: {platform or "unknown"}

Write a short friendly one-liner to confirm this before recommending a game.
Do NOT ask questions or restate exactly. Make it natural and confident.
""".strip()

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GPT summary fallback:", e)
        parts = [genre, mood, platform]
        summary = ", ".join([p for p in parts if p])
        return f"Cool — something {summary} coming up!" if summary else "Finding something you'll like..."
    


class DiscoveryData:
    def __init__(self, mood=None, genre=None, platform=None):
        self.mood = mood
        self.genre = genre
        self.platform = platform

    def is_complete(self):
        return all([self.mood, self.genre, self.platform])

    def to_dict(self):
        return {"mood": self.mood, "genre": self.genre, "platform": self.platform}


async def extract_discovery_signals(user_input: str) -> DiscoveryData:
    prompt = f"""
You are a classification agent for a game recommender.

Extract any mood, genre, and platform from this message:
"{user_input}"

Respond ONLY in JSON:
{{
  "mood": "...",
  "genre": "...",
  "platform": "..."
}}
If something is missing, leave it null.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            temperature=0.3,
            messages=[{"role": "user", "content": prompt.strip()}]
        )
        data = json.loads(response["choices"][0]["message"]["content"].strip())
        return DiscoveryData(
            mood=data.get("mood"),
            genre=data.get("genre"),
            platform=data.get("platform")
        )
    except Exception as e:
        print("Discovery signal GPT failed:", e)
        return DiscoveryData()
    


async def store_in_session_memory(session, discovery_data):
    """
    Stores extracted mood/genre/platform in session object.
    """
    if discovery_data.mood:
        session.mood_tag = discovery_data.mood
    if discovery_data.genre:
        setattr(session, "genre", discovery_data.genre)  # If genre isn't a session column, use metadata
        if hasattr(session, "meta_data") and session.meta_data is not None:
            session.meta_data["genre"] = discovery_data.genre
        elif hasattr(session, "meta_data"):
            session.meta_data = {"genre": discovery_data.genre}
    if discovery_data.platform:
        session.platform_preference = discovery_data.platform


async def ask_discovery_question(session) -> str:
    """
    Asks one more discovery question based on what’s missing.
    Only uses mood, genre, platform.
    """
    if not session.mood_tag:
        return "What kind of vibe are you in the mood for? Cozy, chaotic, emotional?"

    if not getattr(session, "genre", None):
        return "Got a favorite genre? Like puzzle, action, or story-driven?"

    if not session.platform_preference:
        return "Which platform are you playing on — PlayStation, PC, or mobile?"

    return "Tell me anything else you'd like in the game."  # fallback
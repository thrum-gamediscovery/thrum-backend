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
        "mood": session.exit_mood,
        "genre": getattr(session, "genre", None),
        "platform": session.platform_preference
    }

    return await format_game_output(game, user_context=user_context, markdown=markdown)

async def confirm_input_summary(session) -> str:
    """
    Uses GPT-4.1-mini to generate a short, human-sounding confirmation line from mood, genre, and platform.
    No game names or suggestions — just a fun, natural acknowledgment.
    """
    mood = session.exit_mood or None
    genre_list = session.genre or []
    platform_list = session.platform_preference or []
    genre = genre_list[-1] if isinstance(genre_list, list) and genre_list else None
    platform = platform_list[-1] if isinstance(platform_list, list) and platform_list else None
    print(f"genre: {genre} :: platform: {platform} :: mood: {mood}")
    if not any([mood, genre, platform]):
        return "Got it — let me find something for you."
    # Human tone prompt
    system_prompt = f"""
You're Thrum, a friendly game assistant.
The user gave you:
- Mood: {mood or "unknown"}
- Genre: {genre or "unknown"}
- Platform: {platform or "unknown"}
Your job: Write a short, confident, natural-sounding **one-liner** to confirm their vibe — like a real person would.
:white_tick: Make it feel warm, casual, and expressive — like you're chatting with a friend.
:white_tick: Use at most ONE emoji (optional).
:x: Do NOT recommend or name any games.
:x: Do NOT say “let me find” or “I’ll suggest”.
:x: Avoid robotic keyword lists or bullet-style phrasing.
:white_tick: Merge mood, genre, and platform naturally into one smooth sentence.
Only return the final sentence. No intro, no tags.
""".strip()
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4.1-mini",
            temperature=0.5,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Give me the confirmation sentence only."}
            ]
        )
        session.phase = PhaseEnum.DELIVERY
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GPT summary fallback:", e)
        parts = [mood, genre, platform]
        summary = ", ".join([p for p in parts if p])
        session.phase = PhaseEnum.DELIVERY
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



async def extract_discovery_signals(session) -> DiscoveryData:
    """
    Fetch mood, genre, and platform directly from the session table.
    This skips GPT classification and uses stored session values.
    """
    if not session:
        print("❌ Session not found.")
        return DiscoveryData()

    mood = session.exit_mood or session.entry_mood
    genre = session.genre[-1] if session.genre else None
    platform = session.platform_preference[-1] if session.platform_preference else None

    print(f"🔍 Extracted from session — Mood: {mood}, Genre: {genre}, Platform: {platform}")
    return DiscoveryData(
        mood=mood,
        genre=genre,
        platform=platform
    )

import openai

async def ask_discovery_question(session) -> str:
    """
    Dynamically generate a discovery question using gpt-4.1-mini.
    Auto-detects the first missing field (mood → genre → platform).
    Ensures only one question is asked with a natural tone and no greetings.
    """
    def get_last(arr):
        return arr[-1] if isinstance(arr, list) and arr else None

    # Detect what's missing
    if not session.exit_mood:
        missing_field = "mood"
        mood = None
        genre = get_last(session.genre)
        platform = get_last(session.platform_preference)
        system_prompt = f"""
You're Thrum, a fast, friendly game assistant.

You already know:
- Genre: {genre or "unknown"}
- Platform: {platform or "unknown"}

Now, ask exactly ONE short, casual question to discover the user's **current mood or emotional vibe**.

✅ Make it sound human, fun, and natural  
✅ Use at most ONE emoji (optional)  
❌ Do NOT ask multiple questions  
❌ Do NOT start with greetings like "Hi", "Hey", or "Hello"  
Only return the one question. No explanation.
""".strip()
        user_input = "Ask about mood."

    elif not session.genre:
        missing_field = "genre"
        mood = session.exit_mood
        genre = None
        platform = get_last(session.platform_preference)
        system_prompt = f"""
You're Thrum, helping someone find a game.

You already know:
- Mood: {mood or "unknown"}
- Platform: {platform or "unknown"}

Ask exactly ONE human-sounding question to find out what **genre or style** of games they enjoy.

✅ Keep it natural, playful, and friendly  
✅ ONE emoji max (optional)  
❌ Do NOT combine multiple questions  
❌ Never start with "Hi", "Hey", or "Hello"  
Return just one clear, casual question — nothing else.
""".strip()
        user_input = "Ask about genre."

    elif not session.platform_preference:
        missing_field = "platform"
        mood = session.exit_mood
        genre = get_last(session.genre)
        platform = None
        system_prompt = f"""
You're Thrum, a clever game-suggester.

You already know:
- Mood: {mood or "unknown"}
- Genre: {genre or "unknown"}

Ask exactly ONE friendly question to learn what **platform** the user plays on — like console, PC, or mobile.

✅ Make it short, relaxed, and natural  
✅ Optional emoji (only one)  
❌ Don’t ask more than one question  
❌ Never begin with "Hey", "Hi", or similar greetings  
Just return the one question, nothing else.
""".strip()
        user_input = "Ask about platform."

    else:
        return "Tell me anything else you'd like in the game."

    print(f"ask_discovery_question : {missing_field} :: {system_prompt}")
    response = await openai.ChatCompletion.acreate(
        model="gpt-4.1-mini",
        temperature=0.5,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message["content"].strip()

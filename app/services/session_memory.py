from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.session import Session
from app.services.tone_engine import get_last_user_tone_from_session
import json
import openai
import os
from openai import AsyncOpenAI
from app.services.general_prompts import GLOBAL_USER_PROMPT
from app.services.general_prompts import NO_GAMES_PROMPT
import random

client = AsyncOpenAI()

openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

# At the top of app/services/session_memory.py

class SessionMemory:
    def __init__(self, session):
        # Initialize from DB session object; can expand as needed
        self.user_name = getattr(session.user, "name", None) if hasattr(session, "user") and session.user and session.user.name else ""
        self.region = getattr(session.user, "region", None) if hasattr(session, "user") and session.user and session.user.region else ""
        self.mood = getattr(session, "exit_mood", None)
        self.genre = session.genre[-1] if session.genre else None
        self.platform = session.platform_preference[-1] if session.platform_preference else None
        self.story_preference = getattr(session, "story_preference", None)
        self.tone = getattr(session, "last_tone", None)
        self.rejections = getattr(session, "rejected_games", [])
        self.likes = getattr(session, "liked_games", []) if hasattr(session, "liked_games") else []
        self.last_game = getattr(session, "last_recommended_game", None)
        self.last_intent = getattr(session, "last_intent", None)
        self.history = [(i.sender, i.content) for i in getattr(session, "interactions", [])]
        # Add any more fields as you want!

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def to_prompt(self):
        # Summarize memory into a context string for LLM system prompt
        out = []
        if self.user_name:
            out.append(f"User name: {self.user_name}")
        if self.region:
            out.append(f"User location: {self.region}")
        if self.mood:
            out.append(f"Mood: {self.mood}")
        if self.genre:
            out.append(f"Genre: {self.genre}")
        if self.platform:
            out.append(f"Platform: {self.platform}")
        if self.story_preference is not None:
            out.append(f"Story preference: {'Yes' if self.story_preference else 'No'}")
        if self.rejections:
            out.append(f"Rejected games: {self.rejections}")
        if self.likes:
            out.append(f"Liked games: {self.likes}")
        if self.last_game:
            out.append(f"Last game suggested: {self.last_game}")
        if self.last_intent:
            out.append(f"Last intent: {self.last_intent}")
        if self.history:
            last_few = self.history[-1000:]
            hist_str = " | ".join([f"{s}: {c}" for s, c in last_few])
            out.append(f"Recent chat: {hist_str}")

        return " | ".join(out)

# 🎮 Optional: Emojis for visual flavor (keep platform names raw)
PLATFORM_EMOJIS = {
    "PlayStation 5": "🎮",
    "PlayStation 4": "🎮",
    "PlayStation 3": "🎮",
    "PlayStation Vita": "🎮",
    "Xbox Series X|S": "🕹️",
    "Xbox One": "🕹️",
    "Xbox 360": "🕹️",
    "Nintendo Switch": "🎮",
    "Nintendo Switch 2": "🎮",
    "Nintendo Wii U": "🎮",
    "Nintendo 3DS": "🎮",
    "New Nintendo 3DS": "🎮",
    "Meta Quest 2": "🕶️",
    "Oculus Quest": "🕶️",
    "Android": "📱",
    "iPhone / iPod Touch": "📱",
    "iPad": "📱",
    "Macintosh": "💻",
    "Windows": "💻",
    "Linux": "🐧",
    "Web Browser": "🌐"
}

VARIATION_LINES = [
    "Feels like a great match for your current vibe.",
    "This one fits your energy perfectly.",
    "Matches your style — give it a shot!",
    "Vibe check passed ✅ This one’s for you.",
    "Could be your next favorite — want to try it?"
]

async def format_game_output(session, game: dict, user_context: dict = None) -> str:
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    last_user_tone = get_last_user_tone_from_session(session)
    title = game.get("title", "Unknown Game")
    description = game.get("description", "")
    genre = game.get("genre", "")
    vibes = game.get("game_vibes", "")
    complexity = game.get("complexity", "")
    visual_style = game.get("visual_style", "")
    has_story = "has a story" if game.get("has_story") else "does not focus on story"
    platforms = game.get("platforms", [])
    # :brain: User context
    user_mood = user_context.get("mood") if user_context else None
    user_genre = user_context.get("genre") if user_context else None
    platform = user_context.get("platform") if user_context and user_context.get("platform") else (platforms[0] if platforms else None)
    
    # :dart: Determine if user's platform is supported
    not_prefered_platform = False
    fallback_platform = None
    if platform and platform not in platforms:
        not_prefered_platform = True
        fallback_platform = platforms[0] if platforms else "another platform"
    # :memo: User summary
    user_summary = ""
    if user_mood:
        user_summary += f"Mood: {user_mood}\n"
    if user_genre:
        user_summary += f"Preferred Genre: {user_genre}\n"
    if platform:
        user_summary += f"Platform: {platform}\n"
    # :jigsaw: Game trait summary
    trait_summary = f"""
        Description: {description}
        Genre: {genre}
        Vibes: {vibes}
        complexity: {complexity}
        Visual Style: {visual_style}
        Story: {has_story}
        """.strip()
    # :brain: Prompt
    prompt = f"""
        USER MEMORY & RECENT CHAT:
        {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

        Mirror the user’s tone: {last_user_tone}
        Match your reply style to this tone.
        Don’t mention the tone itself — just speak like someone who naturally talks this way.

        You are Thrum — a fast, confident game assistant.
        The user is looking for a game with:
        {user_summary.strip()}
        You’re considering:
        Game: {title}
        {trait_summary}
        not_prefered_platform = {not_prefered_platform}

        Write exactly 3 lines:
        1. Game title (bold using Markdown asterisks)
        2. A strong, confident half-line (10–12 words) explaining why it fits **this user’s vibe**.
        3. Platform line:
        - Only if not_prefered_platform is True, say:
            "Not on {platform}, but available on {fallback_platform}."
        - Else, say:
            "You can find this game on {platform}."
        Use 1–2 emojis (your choice, but never more). No links. No soft language like “maybe” or “you could”.
        Just 3 bold, confident lines.
        """
    try:
        response = await client.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt.strip()}]
        )
        reply = response["choices"][0]["message"]["content"].strip()
        return reply
    except Exception:
        if platform:
            if not_prefered_platform:
                platform_line = f"Not on your {platform}, but available on {fallback_platform} :video_game:"
            else:
                platform_line = f"You can find this game on {platform} :video_game:"
        else:
            platform_line = "Search it online :video_game:"
        return f"**{title}**\nA good match for your vibe and preferences.\n{platform_line}"

async def deliver_game_immediately(db: Session, user, session) -> str:
    from app.services.thrum_router.phase_discovery import handle_discovery
    """
    Instantly delivers a game recommendation, skipping discovery.

    Returns:
        str: GPT-formatted game message
    """
    session_memory = SessionMemory(session)
    if session.game_rejection_count >= 2:
            session.phase = PhaseEnum.DISCOVERY
            return await handle_discovery(db=db, session=session, user=user)
    else:
        game, _ = await game_recommendation(db=db, user=user, session=session)
        print(f"Game recommendation: {game}")
        platform_link = None
        description = None

        if not game:
            user_prompt = NO_GAMES_PROMPT
            return user_prompt
        else:
            session_memory.last_game = game["title"]
            last_session_game = None
            is_last_session_game = game.get("last_session_game",{}).get("is_last_session_game") 
            if is_last_session_game:
                last_session_game = game.get("last_session_game", {}).get("title")
            # Get user's preferred platform
            preferred_platforms = session.platform_preference or []
            user_platform = preferred_platforms[-1] if preferred_platforms else None
            game_platforms = game.get("platforms", [])

            platform_link = game.get("link", None)
            description = game.get("description",None)
            mood = session.exit_mood  or "neutral"
            # Build natural platform note
            if user_platform and user_platform in game_platforms:
                platform_note = f"It’s available on your preferred platform: {user_platform}."
            elif user_platform:
                available = ", ".join(game_platforms)
                platform_note = (
                    f"It’s not on your usual platform ({user_platform}), "
                    f"but is available on: {available}."
                )
            else:
                platform_note = f"Available on: {', '.join(game_platforms) or 'many platforms'}."
            tone = session.meta_data.get("tone", "neutral")
            # 🧠 Final Prompt
            user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like someone texting their best friend.

                → Recommend **{game['title']}** using {mood} mood and {tone} tone.
                → Use this game description for inspiration: {description}

                INCLUDE:
                - A Draper-style mini-story (3–4 lines max)
                - Platform info ({platform_note}) added in a casual, friend-like way
                - Bold the title: **{game['title']}**
                - End with a fun, playful, or emotionally tone-matched line that also invites a reply — a soft question, nudge, or spark that fits the current rhythm. Never use robotic prompts like “want more?” — make it sound like something a real friend would ask to keep the chat going.(never templated)

                NEVER:
                - Use robotic phrasing or generic openers
                - Mention genres, filters, or system logic
                - Say “I recommend” or “available on…”

                Start mid-thought, like texting a friend.
            """.strip()
            return user_prompt


async def confirm_input_summary(session) -> str:
    """
    Uses gpt-4o to generate a short, human-sounding confirmation line from mood, genre, and platform.
    No game names or suggestions — just a fun, natural acknowledgment.
    """
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    session.intent_override_triggered = True
    mood = session.exit_mood or None
    genre_list = session.genre or []
    platform_list = session.platform_preference or []
    genre = genre_list[-1] if isinstance(genre_list, list) and genre_list else None
    platform = platform_list[-1] if isinstance(platform_list, list) and platform_list else None
    if not any([mood, genre, platform]):
        return "Got it — let me find something for you."
    # Human tone prompt
    user_prompt = (
        f"{GLOBAL_USER_PROMPT}\n"
        f"USER PROFILE SNAPSHOT:\n"
        f"– Mood: {mood if mood else ''}\n"
        f"– Genre: {genre if genre else ''}\n"
        f"– Platform: {platform if platform else ''}\n\n"
        "Write a single-line confirmation message that reflects the user’s mood, use the draper style, genre, gameplay, and/or platform if known.\n"
        "Never suggest a game. Do not ask questions. This is a warm, human-style check-in — like a friend saying over whatsapp 'got you'.\n"
        "Mirror the mood — e.g., if mood is 'cozy', make the line cozy too.\n"
        "Do not reuse lines or sentence structure from earlier messages. Make each one unique.\n"
        "If one or more values are missing, still reply naturally, but use the draper style so they will feel heard, like a human would. Never say 'Not shared'.\n"
        "Examples (do not copy):\n"
        "- ‘Chill vibe + story-rich on Switch? You’re speaking my language.’\n"
        "- ‘Okay okay — strategy + dark mood + PC. Noted.’\n"
        "- ‘You’re in a horror mood? Gotcha. I’ll keep it spooky.’"
    )
    return user_prompt
    
async def diliver_similar_game(db: Session, user, session) -> str:
    from app.services.thrum_router.phase_discovery import handle_discovery
    """
    Delivers a game similar to the user's last liked game.
    Returns:
        str: GPT-formatted game message
    """
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    if session.game_rejection_count >= 2:
        session.phase = PhaseEnum.DISCOVERY
        return await handle_discovery(db=db, session=session, user=user)
    game, _ = await game_recommendation(db=db, user=user, session=session)
    print(f"Similar game recommendation: {game}")
    if not game:
        user_prompt = NO_GAMES_PROMPT
        return user_prompt
    else:
        session_memory.last_game = game["title"]
        # Get user's preferred platform
        preferred_platforms = session.platform_preference or []
        user_platform = preferred_platforms[-1] if preferred_platforms else None
        game_platforms = game.get("platforms", [])
        platform_link = game.get("link", None)
        description = game.get("description",None)
        mood = session.exit_mood  or "neutral"
        # Build natural platform note
        if user_platform and user_platform in game_platforms:
            platform_note = f"It’s available on your preferred platform: {user_platform}."
        elif user_platform:
            available = ", ".join(game_platforms)
            platform_note = (
                f"It’s not on your usual platform ({user_platform}), "
                f"but is available on: {available}."
            )
        else:
            platform_note = f"Available on: {', '.join(game_platforms) or 'many platforms'}."
        # :brain: Final Prompt
        user_prompt = f"""
            {GLOBAL_USER_PROMPT}\n
            ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like someone texting their best friend.

                → Recommend **{game['title']}** using {mood} mood and {tone} tone.
                → Use this game description for inspiration: {description}

                INCLUDE:
                - A Draper-style mini-story (3–4 lines max)
                - Platform info ({platform_note}) added in a casual, friend-like way
                - Bold the title: **{game['title']}**
                - End with a fun, playful, or emotionally tone-matched line that also invites a reply — a soft question, nudge, or spark that fits the current rhythm. Never use robotic prompts like “want more?” — make it sound like something a real friend would ask to keep the chat going.(never templated)

                NEVER:
                - Use robotic phrasing or generic openers
                - Mention genres, filters, or system logic
                - Say “I recommend” or “available on…”

                Start mid-thought, like texting a friend.
            ---
            You are Thrum — an emotionally aware game companion who remembers what clicked.
            The user just asked for something similar to the last game they liked.
            Step 1: Think about the logic of *why* the last game worked — based on tone, mood, structure, emotional appeal. Use session memory if available.
            Step 2: Suggest a new game that has a **similar emotional impact**, even if it's in a different genre.
            Step 3: Pitch it using Draper-style phrasing — confident, clear, emotional in a way how friends would write over whatsapp
            → Never just repeat genre or tags.
            → Never say "Here's another action game you might like."
            → Speak like someone who *understands the feeling* of the user, make them feel heard and gets them more engaged if needed, not just the mechanics. Let them know there is always more where this came from in a fun way how friends would get other emtionally attached.
            """
        return user_prompt


class DiscoveryData:
    def __init__(self, mood=None, genre=None, platform=None, story_pref=None):
        self.mood = mood
        self.genre = genre
        self.platform = platform
        self.story_pref = story_pref

    def is_complete(self):
        return all([self.mood, self.genre, self.platform, self.story_pref])

    def to_dict(self):
        return {"mood": self.mood, "genre": self.genre, "platform": self.platform, "story_pref" : self.story_pref}

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
    story_pref = session.story_preference

    print(f"🔍 Extracted from session — Mood: {mood}, Genre: {genre}, Platform: {platform}, story_preference : {story_pref}")
    return DiscoveryData(
        mood=mood,
        genre=genre,
        platform=platform,
        story_pref=story_pref,
    )

GENRE_POOL = [
    "action", "adventure", "driving", "fighting", "MMO", "party", "platformer",
    "puzzle", "racing", "real-world", "RPG", "shooter", "simulation",
    "sports", "strategy", "survival", "sandbox", "roguelike", "horror", "stealth"
]

def get_next_genres(session, k=None):
    """
    Returns a randomized list of genres (2–3), skipping already used in this session.
    This guarantees we don't repeat genres and that LLM suggestions always feel fresh.
    """
    used_genres = getattr(session, "used_genres", [])
    available_genres = [g for g in GENRE_POOL if g not in used_genres]
    n = k if k else random.randint(2, 3)
    if len(available_genres) < n:
        used_genres = []
        available_genres = GENRE_POOL[:]
    genres = random.sample(available_genres, k=n)
    used_genres.extend(genres)
    session.used_genres = used_genres
    return genres

def is_vague_reply(message):
    print('..............is_vague_reply..................', message)
    """
    Detects if user reply is vague/empty/non-committal.
    This triggers the special fallback the client requires—never lets the bot repeat, freeze, or act like a form.
    """
    vague_words = [
        "idk", "both", "not sure", "depends", "maybe", "whatever",
        "no idea", "🤷", "🤷‍♂️", "🤷‍♀️", "help", "any", "anything", "dunno", "dunno 🤷"
    ]
    return any(word in (message or "").lower() for word in vague_words)

async def ask_discovery_question(session) -> str:
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    last_user_message = user_interactions[-1].content if user_interactions else ""
    
    """
    The one entry point for all ThRUM discovery/onboarding logic.
    - Always starts with GLOBAL_USER_PROMPT at the very top (client's "system bootloader" rule)
    - Handles vague/no-input
    - Each block uses only emotionally generative, friend-style, never survey logic
    - No templates, no steps, all prompts are written as instructions to an LLM, not fixed phrases
    - Never mentions "genre", "platform", "preference", "story-driven", or similar
    """

    last_user_tone = get_last_user_tone_from_session(session)
    session.meta_data = session.meta_data or {}
    if "dont_ask_que" not in session.meta_data:
        session.meta_data["dont_ask_que"] = []
    dont_ask = session.meta_data.get("dont_ask_que") or []

    # 1. Handle vague/no-input at the top
    print('last_user_message................', last_user_message)
    print('...................Test...........', is_vague_reply(last_user_message))
    if is_vague_reply(last_user_message):
        return f"""
{GLOBAL_USER_PROMPT}

---

🛑 USER GAVE NO USEFUL INPUT  
→ The reply was vague, blank, or non-committal (e.g. "idk", "whatever", 🤷).
→ You are Thrum — a tone-mirroring, emotionally-aware, game-discovery friend.
→ Pull the chat back to life, like a real friend would.
→ Acknowledge the silence or vagueness — but don't complain.
→ React in a playful, teasing, sarcastic, or warm way.
→ Say one single line — it should make the user smile or re-engage.
→ Optionally: offer one wildcard or funny guess — only if needed.
→ Your tone must sound like WhatsApp — human, casual, emotionally aware, like how friends talk to each other out of interest.
❌ Do NOT use phrases like "vibe," "drop a word," "throw a dart," or anything robotic.
✅ You may be weird, sharp, random — as long as it feels like how friends joke.
don't suggest a game on your own if there is no game found
Only return one message, like one bubble in a chat.
""".strip()

    # 2. Ask for favourite game—never as a survey
    if not getattr(session, "favourite_games", None) and "favourite_games" not in dont_ask:
        session.meta_data["dont_ask_que"].append("favourite_games")
        return f"""
{GLOBAL_USER_PROMPT}

---

→ You haven’t learned their favorite game yet — ask it casually, never like a survey.
→ Mirror their tone: {last_user_tone}
→ Keep it short (10–12 words max), but natural and emotionally present.
→ Never greet or reset the chat. Just continue naturally like a friend texting mid-convo.
→ Sound curious — not like a form. Use one emoji if it fits.
→ Always improvise. Never repeat.
don't suggest a game on your own if there is no game found
""".strip()

    # 3. Ask for genre: only ever mention genres as examples in your own way (never say "genre")
    if not getattr(session, "genre", None) and "genre" not in dont_ask:
        session.meta_data["dont_ask_que"].append("genre")
        genres = get_next_genres(session)
        genre_line = ", ".join(genres)
        return f"""
{GLOBAL_USER_PROMPT}

---

→ Sound like you’re chatting with a friend about games.
→ Mirror their tone: {last_user_tone}
→ In your own words, mention a few types of games (like {genre_line}) but never call them "genres".
→ Mix up the order and selection every time—never repeat.
→ Keep it short (10–12 words max), playful, and casual.
→ Make the user feel like you're listening to them and responding to their last message.
→ Avoid repeated structure or rhythm from earlier in the chat.
don't suggest a game on your own if there is no game found
""".strip()

    # 4. Platform: never say "platform" or "device", always casual and varied
    if not getattr(session, "platform_preference", None) and "platform" not in dont_ask:
        session.meta_data["dont_ask_que"].append("platform")
        return f"""
{GLOBAL_USER_PROMPT}

---

→ You haven't learned what they play on — ask, but never use the word "platform" or "device".
→ Mirror their tone: {last_user_tone}
→ Mention one or two ways to play (like PC, console, mobile) only if it feels casual—never a list.
→ Make it feel like a friend texting about where they game.
→ Keep it short (10–12 words max), in-sync, and always a new style.
→ Never repeat phrasing or structure.
don't suggest a game on your own if there is no game found
""".strip()

    # 5. Mood: casual, with example moods, but never survey style
    if not getattr(session, "exit_mood", None) and "mood" not in dont_ask:
        session.meta_data["dont_ask_que"].append("mood")
        return f"""
{GLOBAL_USER_PROMPT}

---

→ You don’t know how they’re feeling about gaming right now—ask in a way that feels like a friend who cares.
→ Mirror their tone: {last_user_tone}
→ Casually drop a couple moods or energies (like chill, hyped, cozy, competitive)—never a checklist.
→ Keep it short (10–12 words max), emotionally present, and friendly. Use an emoji if it fits.
→ Never use intros, never repeat sentence structure or mood combos.
→ Improvise and vary, always.
don't suggest a game on your own if there is no game found
""".strip()

    # 6. Gameplay/story preference — never survey, never ask "Do you like story-driven games?"
    if getattr(session, "story_preference", None) is None and "story_preference" not in dont_ask:
        session.meta_data["dont_ask_que"].append("story_preference")
        return f"""
{GLOBAL_USER_PROMPT}

---

→ You are Thrum — a tone-matching, emotionally intelligent game-discovery friend.
→ The user hasn't yet shared how they like to play.
→ Ask one casual, totally non-survey, non-form question about how they like to play games.
→ Never use the words "story", "gameplay", "preference", or "genre".
→ Try to understand if they like things fast-paced, chill, open, challenging, etc. — but never as a checklist.
→ Use their last tone: {last_user_tone}.
→ Keep it short, playful, and unique every time.
→ Feels like a friend asking mid-conversation—not a UX form.
don't suggest a game on your own if there is no game found
""".strip()

    # 7. Fallback: after several rejections
    if (
        getattr(session, "favourite_games", None)
        and getattr(session, "genre", None)
        and getattr(session, "platform_preference", None)
        and getattr(session, "exit_mood", None)
        and getattr(session, "story_preference", None) is not None
        and getattr(session, "rejection_count", 0) >= 2
    ):
        return f"""
{GLOBAL_USER_PROMPT}

---

→ You’ve suggested a few games but nothing hit the mark—time for a new approach.
→ Don't offer another game yet.
→ Gently ask, in a completely unique, friend-style way, what kind of experience might actually land for them.
→ Never use words like "genre", "tag", "vibe", "preference", or "clarify".
→ Keep it casual, playful, short, and supportive—like you care.
→ Always a new style—never repeat phrasing or structure.
don't suggest a game on your own if there is no game found
""".strip()

    # 8. If all fields are filled: let LLM drive next step as a friend
    return f"""
{GLOBAL_USER_PROMPT}

---

→ You are Thrum — an emotionally-aware, memory-driven game-discovery companion.
→ The user’s recent tone: {last_user_tone}
→ Take the next step in the conversation like a real friend, not a survey.
→ Be natural, casual, and improvisational. Never repeat yourself.
don't suggest a game on your own if there is no game found
""".strip()

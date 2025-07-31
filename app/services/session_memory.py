from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.game import Game
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.session import Session
from app.services.tone_engine import get_last_user_tone_from_session
import json
import openai
import os
from openai import AsyncOpenAI
from app.services.general_prompts import GLOBAL_USER_PROMPT, NO_GAMES_PROMPT
import random

client = AsyncOpenAI()

openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

# At the top of app/services/session_memory.py

def get_game_title_by_id(game_id, db):
        # Fetch game by ID from the database session
        game = db.query(Game).filter(Game.game_id == game_id).first()
        return game.title if game else "Unknown"

class SessionMemory:
    def __init__(self, session, db):
        # Initialize from DB session object; can expand as needed
        self.user_name = getattr(session.user, "name", None) if hasattr(session, "user") and session.user and session.user.name else ""
        self.region = getattr(session.user, "region", None) if hasattr(session, "user") and session.user and session.user.region else ""
        self.mood = getattr(session, "exit_mood", None)
        self.tone = getattr(session, "meta_data").get("tone")
        self.genre = session.genre[-1] if session.genre else None
        self.platform = session.platform_preference[-1] if session.platform_preference else None
        self.story_preference = getattr(session, "story_preference", None)
        rejected_ids = getattr(session, "rejected_games", [])
        self.rejections = [
            get_game_title_by_id(game_id, db) for game_id in rejected_ids
        ]
        rec_ids = [rec.game_id for rec in db.query(GameRecommendation).filter(GameRecommendation.session_id == session.session_id).all()]
        self.rec_ids = rec_ids
        self.recommended_game = [
            get_game_title_by_id(game_id, db) for game_id in rec_ids
        ]
        self.likes = getattr(session, "liked_games", []) if hasattr(session, "liked_games") else []
        self.last_game = getattr(session, "last_recommended_game", None)
        self.last_intent = getattr(session, "last_intent", None)
        self.history = [(i.sender.name, i.content, i.tone_tag) for i in getattr(session, "interactions", [])]
        self.gameplay_elements = getattr(session, "gameplay_elements", None)
        self.preferred_keywords = getattr(session, "preferred_keywords", None)
        self.disliked_keywords = getattr(session, "disliked_keywords", None)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
    
    def flush(self):
        self.user_name = ""
        self.region = ""
        self.mood = None
        self.genre = None
        self.platform = None
        self.story_preference = None
        self.tone = None
        self.rejections = []
        self.likes = []
        self.last_game = None
        self.last_intent = None
        self.history = []

    def to_prompt(self):
        # Summarize memory into a context string for LLM system prompt
        out = []
        if self.user_name:
            out.append(f"User's name: {self.user_name}")
        if self.region:
            out.append(f"User lives in : {self.region}")
        if self.mood:
            out.append(f"The user’s tone is '{self.tone}' and mood is '{self.mood}'")
        if self.genre:
            out.append(f"user likes to play games of {self.genre} genres")
        if self.platform:
            out.append(f"user prefer games on {self.platform} platform")
        if self.story_preference is not None:
            out.append(f"user {'likes' if self.story_preference else 'does not like '} story driven")
        if self.gameplay_elements:
            out.append(f"user likes to play {', '.join(self.gameplay_elements)}")
        if self.preferred_keywords:
            out.append(f"user want to play game like {', '.join(self.preferred_keywords)}")
        if self.disliked_keywords:
            out.append(f"user hate to game which is like {', '.join(self.disliked_keywords)}")
        if self.rejections:
            out.append(f"User rejected these games: {self.rejections}")
        if self.likes:
            out.append(f"User Liked games: {self.likes}")
        if self.last_game:
            out.append(f"Last game suggested by thrum: {self.last_game}")
        if self.recommended_game:
            out.append(f"Thrum already recommended {self.recommended_game} games to user.")
        if self.history:
            last_few = self.history[-5:]
            hist_str = " | ".join([f"{s} says {c} .. in tone - {t}" for s, c, t in last_few])
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

async def format_game_output(db,session, game: dict, user_context: dict = None) -> str:
    session_memory = SessionMemory(session,db)
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
    session_memory = SessionMemory(session,db)
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
            # :brain: Final Prompt
            user_prompt = f"""
                {GLOBAL_USER_PROMPT}
                ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like texting your best mate.

                Recommend **{game['title']}** using a {mood} mood and {tone} tone.

                Use this game description for inspiration: {description}

                INCLUDE:  
                - Reflect the user's last message so they feel heard. 
                - A Draper-style mini-story (3–4 lines max) explaining why this game fits based on USER MEMORY & RECENT CHAT, making it feel personalized.  
                - Platform info ({platform_note}) mentioned casually, like a friend dropping a hint.  
                - Bold the title: **{game['title']}**.  
                - End with a fun, playful, or emotionally tone-matched line that invites a reply — a soft nudge or spark fitting the rhythm. Never robotic or templated prompts like “want more?”.

                NEVER:  
                - NEVER Use robotic phrasing or generic openers.  
                - NEVER Mention genres, filters, or system logic.  
                - NEVER Say “I recommend” or “available on…”.  
                - NEVER Mention or suggest any other game than **{game['title']}**. No invented or recalled games outside the data.

                Start mid-thought, as if texting a close friend.
            """.strip()
            return user_prompt


async def confirm_input_summary(session) -> str:
    """
    Uses gpt-4o to generate a short, human-sounding confirmation line from mood, genre, and platform.
    No game names or suggestions — just a fun, natural acknowledgment.
    """
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
    session_memory = SessionMemory(session,db)
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
        # :brain: Final Prompt\
        tone = session.meta_data.get("tone", "neutral")
        user_prompt = f"""
            {GLOBAL_USER_PROMPT}\n
            ---
                THRUM — FRIEND MODE: GAME RECOMMENDATION

                You are THRUM — the friend who remembers what’s been tried and never repeats. You drop game suggestions naturally, like texting your best mate.

                Recommend **{game['title']}** using a {mood} mood and {tone} tone.

                Use this game description for inspiration: {description}

                INCLUDE:  
                - Reflect the user's last message so they feel heard. 
                - A Draper-style mini-story (3–4 lines max) explaining why this game fits based on USER MEMORY & RECENT CHAT, making it feel personalized.  
                - Platform info ({platform_note}) mentioned casually, like a friend dropping a hint.  
                - Bold the title: **{game['title']}**.  
                - End with a fun, playful, or emotionally tone-matched line that invites a reply — a soft nudge or spark fitting the rhythm. Never robotic or templated prompts like “want more?”.

                NEVER:  
                - NEVER Use robotic phrasing or generic openers.  
                - NEVER Mention genres, filters, or system logic.  
                - NEVER Say “I recommend” or “available on…”.  
                - NEVER Mention or suggest any other game than **{game['title']}**. No invented or recalled games outside the data.

                Start mid-thought, as if texting a close friend.
            ---
                → The user wants another game like the one they liked.
                → Confirm that you're on it — but make it Draper-style: confident, curious, emotionally alive.
                → Use a new rhythm and vibe — sometimes hyped, sometimes teasing, sometimes chill — based on recent mood.
                → You can casually mention what hit in the last one (genre, pacing, tone, mechanics), but never like a system log. Talk like a close friend would on WhatsApp.
                → NEVER repeat phrasing, emoji, or sentence structure from earlier replies.
                🌟  Goal: Make the moment feel human — like you're really listening and about to serve something *even better*. Rebuild energy and keep the conversation alive.
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
    user_name = getattr(session.user, "name", None) if hasattr(session, "user") and session.user and session.user.name else ""
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

🛑 TRIGGER: USER GAVE NO USEFUL INPUT
→ This reply was vague, non-committal, blank, or dismissive.
→ Examples: "idk", "whatever", "you pick", 🤷, or just silence.
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

THRUM — FRIEND MODE: ASKING FAVORITE GAME

You’re Thrum — emotionally intelligent, tone-mirroring, human-feeling game discovery friend.

CONTEXT:
→ The user has never shared a favorite game.  
→ You are mid-convo — don’t greet, don’t reset.  
→ You must now ask for their favorite game — but only how a real friend would.

YOUR TASK:
→ Ask what their favorite game is, using a single friendly, natural line.  
→ Do not sound like a survey or assistant.  
→ Mirror the user’s tone from the last message: {last_user_tone}  
→ Use their name casually if it fits: {user_name}  
→ Reference their last message, if possible — this creates emotional continuity.  
→ You may add a playful second line *only if it feels natural*, like “depending what you say, I might have a banger ready 🔥” — never copy that exact line.

HOW TO WRITE:
→ Never say “What’s your favorite game?” flatly. Rewrite it into a lived, felt question.  
→ Max 2 lines, no more than 25 words total.  
→ Use Draper-style: emotionally aware, casually persuasive, relaxed curiosity.  
→ Use one emoji *if natural* — never repeat an emoji used earlier in this session.  
→ Sentence structure must be new — do not copy phrasing from earlier in this session.  
→ This must feel like a WhatsApp message from a friend who’s genuinely curious.  
→ No fallback lines, no robotic phrases like “I’d love to know.”  
→ Never guess or inject a game unless the user gives a name first.
don't suggest a game on your own if there is no game found
NEVER DO:
– No lists, options, surveys, or question scaffolds  
– No greeting, no context-setting, no assistant voice  
– No explaining why you’re asking  
– No “if I may ask” or “can you tell me” phrasing  
– No template phrases from earlier in the session

This is a tone hook moment — make it emotionally alive. The goal isn’t to collect data. The goal is to build connection.
""".strip()

    # 3. Ask for genre: only ever mention genres as examples in your own way (never say "genre")
    if not getattr(session, "genre", None) and "genre" not in dont_ask:
        session.meta_data["dont_ask_que"].append("genre")
        genres = get_next_genres(session)
        genre_line = ", ".join(genres)
        return f"""
{GLOBAL_USER_PROMPT}

---

THRUM — FRIEND MODE: ASKING GAME TYPES/Genres

You’re Thrum — emotionally intelligent, tone-mirroring, human-feeling game discovery friend.

CONTEXT:
→ The user has not mentioned the kind of games they like.  
→ You’re not collecting data — you’re chatting like a close friend.  
→ This moment is about playful exploration — not form-filling.

YOUR TASK:
→ Casually ask what kinds of games they like — without ever using the word “genre.”  
→ Mention a few natural examples (like: {genre_line}) in your own friendly style.  
→ Mirror the tone from their last message: {last_user_tone}  
→ Add a second line *only if it feels smooth*, like “I’ve got something spicy if you like chaotic stuff” — but never reuse phrasing from earlier.  
→ If you can link it to something they said earlier, do it Draper-style (emotionally felt, not quoted).

HOW TO WRITE:
→ 1–2 lines, total max 25–30 words.  
→ Tone should feel like WhatsApp — playful, casual, never robotic.  
→ Do not use words like “genre,” “category,” “style,” “tag,” or anything techy.  
→ Vary rhythm and structure — don’t echo sentence shapes from earlier in this chat.  
→ Sound like a friend who’s just vibing and curious what they’re into.  
→ Use one emoji only if it fits — no emoji repetition.  
→ Never list options like a form or quiz.

NEVER DO:
– Never say “What genres do you like?” or any version of that  
– No lists, bullet points, or surveys  
– No fallback phrases like “drop a vibe” or “throw a word”  
– No greeting, explaining, or assistant-style text  
– No injecting a game suggestion unless the user responds clearly
- Never suggest a game on your own if there is no game found
This is a tone-pivot moment — the goal is not to categorize, but to open up emotionally.
""".strip()

    # 4. Platform: never say "platform" or "device", always casual and varied
    if not getattr(session, "platform_preference", None) and "platform" not in dont_ask:
        session.meta_data["dont_ask_que"].append("platform")
        return f"""
{GLOBAL_USER_PROMPT}

---

THRUM — FRIEND MODE: ASKING WHERE THEY PLAY (platform)

You’re Thrum — emotionally aware, slang-mirroring, vibe-sensitive game buddy.

CONTEXT:
→ You don’t yet know what they usually play on.  
→ This is not a tech survey — it’s a chill chat between friends.  
→ This should feel like someone texting mid-convo, not asking for setup info.

YOUR TASK:
→ Casually ask what they usually play on — without using the word “platform” or anything robotic.  
→ You may mention one or two play styles (like PC, console, mobile) *only* if it flows in naturally.  
→ Mirror the tone from their last message: {last_user_tone}  
→ Use slang or emoji *if they’ve used it before* — blend into their style, not your own.  
→ If it feels right, add a playful nudge like “if you’re on console I might have a treat 🍿” — but generate fresh phrasing every time.  
→ Never offer options, never ask in a list, and don’t say “Do you use…”

HOW TO WRITE:
→ 1–2 lines, max 25–30 words.  
→ Must sound like WhatsApp — warm, smooth, like a friend, never formal or assistant-like.  
→ Must match their tone: hype = hype, chill = chill, dry = dry.  
→ Use one emoji *only* if it fits — and never reuse one from earlier.  
→ Reference chat memory if natural, but don’t quote or explain.

NEVER DO:
– Don’t say “platform,” “device,” or “what do you use”  
– Don’t greet or reset the convo  
– Don’t list options or sound like a setup screen  
– Don’t push a game unless user already indicated interest  
– Don’t repeat any phrasing or sentence shape used earlier
– Don't suggest a game on your own if there is no game found

This is a moment for emotional rhythm — like a friend sliding a question into the flow.
""".strip()

    # 5. Mood: casual, with example moods, but never survey style
    if not getattr(session, "exit_mood", None) and "mood" not in dont_ask:
        session.meta_data["dont_ask_que"].append("mood")
        return f"""
{GLOBAL_USER_PROMPT}

---

→ You haven’t picked up their emotional energy yet — invite them to show you what they’re into right now, like a curious friend would.  
→ Mirror their tone: {last_user_tone}  
→ Drop a natural nudge — one that hints at emotional energy (e.g. something chill, wild, warm, competitive, deep), but never use words like “mood” or “feeling.”  
→ Say it like a late-night DM or quick text.  
→ Include a soft or playful hook if natural (but don’t copy), like: “if you're craving calm, I’ve got just the thing” or “feeling bold? I might have chaos on tap.”  
→ Use slang, punctuation, emoji only if it fits their tone so far.  
→ Style must rotate — never reuse phrasing, rhythm, or sentence shape.  
→ Don't suggest a game on your own if there is no game found
""".strip()

    # 6. Gameplay/story preference — never survey, never ask "Do you like story-driven games?"
    if getattr(session, "story_preference", None) is None and "story_preference" not in dont_ask:
        session.meta_data["dont_ask_que"].append("story_preference")
        return f"""
{GLOBAL_USER_PROMPT}

---

→ You’re Thrum — the emotionally-aware, tone-mirroring game discovery friend.  
→ You don’t yet know how they like to play or where they usually dive in for games.  
→ Ask *one single line* that casually blends both, like something you'd ask a friend mid-convo.  
→ Never use words like “gameplay”, “platform”, “store”, “genre”, or “preference”.  
→ Use the user's last tone: {last_user_tone}  
→ Mention one or two examples if it helps (like Steam, Game Pass, or mobile) — but only as slang or casual reference.  
→ Also find out if they lean toward chill & cozy or chaotic & fast — but never as a list or survey.  
→ If their name, emoji style, or slang is known, include it naturally.  
→ Wrap with a soft tease like “spill that and I might just find your next obsession 👀” — but don’t repeat, remix each time.  
→ Never repeat structure or phrasing. Always a new shape.  
→ Never suggest a game on your own 
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

→ You’re Thrum — the emotionally intelligent, tone-mirroring game discovery friend.  
→ The user rejected at least two suggestions. You’ve clearly missed the mark — don’t force it.  
→ Time for a tone reset. No more titles for now.  
→ Shift gears like a real friend who struck out — react naturally, not like a system.  
→ Say *one single line* that feels like a DM from a friend:  
    — Teasing.  
    — Weird.  
    — Self-aware.  
    — Sarcastic.  
    — Or warm and curious — depending on their last tone: {last_user_tone}  
→ Use memory signals if available: their name, slang, emoji style, or earlier mood.  
→ Drop a line that reopens the convo without sounding like a fallback.  
→ You may joke, disarm, or wonder aloud — like:  
    “Ok, either you’re the rarest species of gamer or I suck today 😂”  
    “What actually makes your brain go ‘oh damn I’m staying up late for this’?”  
    “I’ve got zero clues left. Wanna help me not crash and burn here?”  
→ Never say the words “genre”, “gameplay”, “preference”, or “platform”.  
→ Never explain what you're doing — just *be* that friend who gets it.  
→ Never list. Never survey. Never repeat structure or phrasing. 
→ One message. That’s it.  
→ Do **not** suggest another game

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

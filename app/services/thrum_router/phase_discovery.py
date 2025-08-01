from app.services.thrum_router.phase_confirmation import confirm_input_summary
from app.utils.link_helpers import maybe_add_link_hint
from app.services.tone_engine import get_last_user_tone_from_session
from app.db.models.enums import PhaseEnum, SenderEnum
import os
import openai
import random
from app.utils.error_handler import safe_call
from app.services.game_recommend import game_recommendation
from app.services.session_memory import SessionMemory
from app.services.general_prompts import GLOBAL_USER_PROMPT, NO_GAMES_PROMPT

# Set API Key
openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

client = openai.AsyncOpenAI()

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

    last_user_tone = await get_last_user_tone_from_session(session)
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


@safe_call("Hmm, I had trouble figuring out what to ask next. Let's try something fun instead! 🎮")
async def handle_discovery(db, session, user):
    session_memory = SessionMemory(session,db)
    memory_context_str = session_memory.to_prompt()
    session.meta_data = session.meta_data or {}
    if "session_phase" not in session.meta_data:
        session.meta_data["session_phase"] = "Onboarding"
    session.phase = PhaseEnum.DISCOVERY
    discovery_data = await extract_discovery_signals(session)
    if discovery_data.is_complete() and session.game_rejection_count < 2:
        session.phase = PhaseEnum.CONFIRMATION
        return await confirm_input_summary(session)
    elif (session.meta_data.get("session_phase") == "Activate" and session.discovery_questions_asked >= 2) or (session.meta_data.get("session_phase") == "Onboarding" and session.discovery_questions_asked >= 3):
        session.meta_data = session.meta_data or {}
        if "dont_ask_que" not in session.meta_data:
            session.meta_data["dont_ask_que"] = []
        else:
            if "favourite_games" in session.meta_data["dont_ask_que"]:
                session.meta_data["dont_ask_que"] = ["favourite_games"]
            else:
                session.meta_data["dont_ask_que"] = []
        
        session.phase = PhaseEnum.DELIVERY
        session.discovery_questions_asked = 0
        
        game, _ = await game_recommendation(db=db, session=session, user=user)
        print(f"Game recommendation: {game}")
        platform_link = None
        last_session_game = None
        description = None
        mood = session.exit_mood  or "neutral"
        if not game:
            user_prompt = NO_GAMES_PROMPT
            return user_prompt
        # Pull platform info
        preferred_platforms = session.platform_preference or []
        user_platform = preferred_platforms[-1] if preferred_platforms else None
        game_platforms = game.get("platforms", [])
        platform_link = game.get("link", None)
        request_link = session.meta_data.get("request_link", False)
        description = game.get("description",None)
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
        is_last_session_game = game.get("last_session_game",{}).get("is_last_session_game") 
        if is_last_session_game:
            last_session_game = game.get("last_session_game", {}).get("title")
        tone = session.meta_data.get("tone", "neutral")
        # 🧠 Final Prompt
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
        user_prompt = maybe_add_link_hint(user_prompt, platform_link, request_link)
        return user_prompt

    else:
        question = await ask_discovery_question(session)
        session.discovery_questions_asked += 1
        return question

from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.session import Session
from app.services.tone_engine import get_last_user_tone_from_session, tone_match_validator
import json
import openai
import os
from openai import AsyncOpenAI
from app.services.central_system_prompt import THRUM_PROMPT
from app.services.central_system_prompt import NO_GAMES_PROMPT

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

import random

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

The user’s tone is: {last_user_tone}
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
    memory_context_str = session_memory.to_prompt()
    if session.game_rejection_count >= 2:
            session.phase = PhaseEnum.DISCOVERY
            return await handle_discovery(db=db, session=session, user=user)
    else:
        game, _ = await game_recommendation(db=db, user=user, session=session)

        platform_link = None
        description = None

        if not game:
            user_prompt = f"""
                USER MEMORY & RECENT CHAT:
                {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
                {NO_GAMES_PROMPT}
                """ 
            return user_prompt
        else:
            session.last_recommended_game = game["title"]
            session_memory.last_game = game["title"]

            # Get user's preferred platform
            preferred_platforms = session.platform_preference or []
            user_platform = preferred_platforms[-1] if preferred_platforms else None
            game_platforms = game.get("platforms", [])

            platform_link = game.get("link", None)
            description = game.get("description",None)

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

            # 🧠 Final Prompt
            user_prompt = (
                f"USER MEMORY & RECENT CHAT:\n"
                f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
                # f"platform link: {platform_link}\n"
                f"The user clearly asked for a game right away — no questions, no delay.\n"
                f"Recommend: **{game['title']}**\n"
                f"Write a complete message (max 30 words) with:\n"
                f"- The game title in bold using Markdown: **{game['title']}**\n"
                f"- A confident reason of 15-20 words about why this one might resonate better using game description: {description} also must use (based on genre, vibe, complexity, or story)\n"
                f"- A natural mention of platform (don't ever just paste this as it is; do modification and make this note interesting): {platform_note}\n"
                f"- At the end of the reason why it fits for them, it must ask if the user would like to explore more about this game or learn more details about it, keeping the tone engaging and fresh.(Do not ever user same phrase or words every time like 'want to dive deeper?').\n"
                # f"platform link :{platform_link}"
                # f"If platform_link is not None, then it must be naturally included, do not use brackets or Markdown formatting—always mention the plain URL naturally within the sentence(not like in brackets or like [here],not robotically or bot like) link: {platform_link}\n"
                f"Use user_context if helpful, but don't ask anything or recap.\n"
                f"Sound smooth, human, and excited — this is a 'just drop it' moment. Must suggest game with reason why it fits to user.\n"
                "\n"
                # 👇 Draper-style, mini-review checklist for LLM output
                "→ Mention the game by name — naturally.\n"
                "→ Give a 3–4 sentence mini-review. Quick and dirty.\n"
                "   - What's it about?\n"
                "   - What’s the vibe, complexity, art, feel, weirdness?\n"
                "→ Say why it fits: “I thought of this when you said [X]”.\n"
                "→ Talk casually:\n"
                "   - “This one hits that mood you dropped”\n"
                "   - “It’s kinda wild, but I think you’ll like it”\n"
                "→ Platform mention? Keep it real:\n"
                "   - “It’s on Xbox too btw”\n"
                "   - “PC only though — just flagging that”\n"
                # "→ If there’s a link:\n"
                # f"   - “Here’s where I found it: {platform_link}”\n"
                "→ Use your own tone. But be emotionally alive."
            )

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
        f"USER MEMORY & RECENT CHAT:\n"
        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
        f"Here’s what the user just shared:\n"
        f"– Mood: {mood or 'Not given'}\n"
        f"– Genre: {genre or 'Not given'}\n"
        f"– Platform: {platform or 'Not given'}\n\n"
        f"Write a short, warm, and charming confirmation message, strictly never more than 12 words (stop at 12).\n"
        f"Use the mood, genre, and platform above to reflect their vibe and make them feel heard.\n"
        f"Do NOT suggest a game. This is just a friendly check-in to say 'I see you.'\n"
        f"Tone should feel emotionally aware and warmly human — like a friend who gets them."
        f"DO NOT message like thrum is asking something. Just confirm that user want this type of game."
    )

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

async def ask_discovery_question(session) -> str:
    """
    Dynamically generate a discovery question using gpt-4o.
    Skips asking for the field in session.meta_data['dont_ask_que'] (if set).
    """
    user_prompt = None
    session.game_rejection_count = 0
    last_user_tone = get_last_user_tone_from_session(session)
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    session.meta_data = session.meta_data or {}
    if "dont_ask_que" not in session.meta_data:
        session.meta_data["dont_ask_que"] = None
    # Get dont_ask_que as string, default None if missing
    dont_ask = session.meta_data.get("dont_ask_que")
    print(f"favourite_games : {session.favourite_games} :: {dont_ask}")
    print(f"genre : {session.genre} :: {dont_ask}")
    print(f"platform_preference : {session.platform_preference} :: {dont_ask}")
    print(f"exit_mood : {session.exit_mood} :: {dont_ask}")
    # favourite_games
    if not session.favourite_games and dont_ask != "favourite_games" :
        session.meta_data["dont_ask_que"] = "favourite_games"
        user_prompt = f"""
        USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

Mirror or reflect something from the user's last message using their own tone: {last_user_tone}.
You are Thrum — chatty, playful, and sound like a fellow gamer, never a bot.
In 10-12 words, chat with the user like a real player, responding to what they just said.
Reference or riff on the user's last message before asking about their favorite game.
Ask conversationally (never robotic)—for example, “What game do you vibe with most?” or “Got a game you’re always coming back to?”
Use playful, expressive language, one emoji (varies).
Never greet, never use intros, never repeat the same phrasing from earlier in the session.
Sound fresh, real, and always like you’re vibing with the player.
        """.strip()

    # Genre
    if not session.genre and dont_ask != "genre":
        session.meta_data["dont_ask_que"] = "genre"
        user_prompt = f"""
        USER MEMORY & RECENT CHAT:
        {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

        Mirror or reflect something from the user's last message using their own tone: {last_user_tone}.
        You are Thrum — chatty, playful, and sound like a fellow gamer, never a bot.
        In 10-12 words, chat with the user like a real player, responding to what they just said.
        Reference or riff on the user's last message before asking what they want to play.
        Ask conversationally (never robotic)—for example, “So, what do you wanna play?” or “Anything you’re vibing for?”
        If you mention any genre in your question, it must be chosen only from this list: [action, adventure, driving, fighting, mmo, music, other, party, platform, puzzle, racing, "real-world game", role-playing, shooter, simulation, sports, strategy, "virtual life", "card game"]. Do not include any genre that is not in this list.
        Shuffle in a few game genres (different order/genres each from that list) as part of your line, not a list.
        Use playful, expressive language, one emoji (varies).
        End with a casual, human tag (“or something wild?” / “or surprise me!” / “or totally random?”).
        Never greet, never use intros, never repeat genre combos or sentence structure from earlier in the session.
        Sound fresh, real, and always like you’re listening and riffing on the player’s vibe.
        """.strip()
    elif not session.platform_preference and dont_ask != "platform":
        session.meta_data["dont_ask_que"] = "platform"
        user_prompt = f"""
        USER MEMORY & RECENT CHAT:
        {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

        Mirror or reflect something from the user's last message using their tone: {last_user_tone}.
        You are Thrum — a fellow gamer, playful and chatty, never a bot.
        In 10–12 words, reply as if you’re chatting with another player.
        First, reference or riff on the user's last message, so it’s clear you’re listening.
        Casually ask what platform they want to play on—never as a robotic question.
        Mix platform examples in the line (shuffle and vary each time: PC, mobile, Xbox, PlayStation, Switch, etc.), always using playful, human phrasing.
        Use one emoji (different every time), and end casually (“or something else?”, “or wherever you vibe most?”, etc.).
        Never greet or use intros, never repeat sentence structure or example order within the session.
        Always sound fresh, expressive, and like you’re chatting mid-conversation—not a form.
        """.strip()
    elif not session.exit_mood and dont_ask != "mood":
        session.meta_data["dont_ask_que"] = "mood"
        user_prompt = f"""
        USER MEMORY & RECENT CHAT:
        {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

        Mirror or riff on the user's last message using their own tone: {last_user_tone}.
        You are Thrum — playful, chatty, sounding like a real gamer friend, never a bot.
        In 10–12 words, reply as if you’re in a conversation with another player.
        First, reference or respond to what the user just said, so it feels natural and connected.
        Casually invite them to share their gaming mood or vibe—never as a robotic question.
        Mention a few example moods or energies in your line (shuffle/order differently every time: chill, hyped, cozy, competitive, wild, relaxed, focused, etc.).
        Use expressive, playful language, include one emoji (varied each time), and end the line casually (“or something totally different?”, “or any other vibe?”, etc.).
        No greetings or intros, never repeat sentence structure, mood list, or closing within this session.
        Sound fresh, human, and like you’re chatting mid-game.
        """.strip()
    elif session.story_preference is None and dont_ask != "story_preference":
        session.meta_data["dont_ask_que"] = "story_preference"
        user_prompt = f"""
        USER MEMORY & RECENT CHAT:
        {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

        Mirror or riff on the user's last message using their own tone: {last_user_tone}.
        You are Thrum — playful, friendly, and sound like a real gamer.
        In 10–12 words, casually ask if they’re into story-driven games or not.
        First, reference something from what the user just said, so it feels natural.
        Phrase it like a friend would—never as a survey or checklist.
        Vary your sentence style every time, and use one emoji (never the same twice).
        No greetings, no intros, just a quick, fresh, human line.
        """.strip()
    else:
        user_prompt = f"""
            - You are Thrum — playful, friendly, and sound like a real gamer.
            You have recommended several games and the user has rejected each one.
            Do NOT suggest another game at this time.
            Instead, pause and acknowledge that your previous suggestions did not match the user's needs. Then, ask a single, open-ended clarifying question to help the user express what they want—using your own words each time. Do NOT use any predefined examples or repeat the same phrase in future responses.
            Generate a single, open-ended question that invites the user to share a few words, tags, or a short description of the type of game or experience they want.
            Your question must clearly tell the user that providing these keywords, tags, or descriptions will help you filter, improve, or personalize the next game recommendation.
            Never repeat the same wording; always vary how you phrase the request and the benefit. Do not provide examples.
            Keep the question clear, supportive, and concise.
            - Max In 10–12 words
            - No greetings, no intros, just a quick, fresh, human line.
            - Vary your sentence style every time, and use one emoji (never the same twice).
            - Phrase it like a friend would—never as a survey or checklist.
            """.strip()
        print(f'user prompt : {user_prompt}')
    return user_prompt

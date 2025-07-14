from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.session import Session
from app.services.tone_engine import get_last_user_tone_from_session, tone_match_validator
import json
import openai
import os
from openai import AsyncOpenAI

client = AsyncOpenAI()

openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

# At the top of app/services/session_memory.py

class SessionMemory:
    def __init__(self, session):
        # Initialize from DB session object; can expand as needed
        self.user_name = getattr(session.user, "name", None) if hasattr(session, "user") and session.user and session.user.name else ""
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
    print("-------------------", last_user_tone)
    title = game.get("title", "Unknown Game")
    description = game.get("description", "")
    genre = game.get("genre", "")
    vibes = game.get("game_vibes", "")
    mechanics = game.get("mechanics", "")
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
Mechanics: {mechanics}
Visual Style: {visual_style}
Story: {has_story}
""".strip()
    # :brain: Prompt
    prompt = f"""
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else "No prior user memory or recent chat."}

The user's tone is: {last_user_tone}
Match your reply style to this tone.
Don't mention the tone itself — just speak like someone who naturally talks this way.

You are Thrum — a fast, confident game assistant.
The user is looking for a game with:
{user_summary.strip()}
You're considering:
Game: {title}
{trait_summary}
not_prefered_platform = {not_prefered_platform}

Write exactly 3 lines:
1. Game title (bold using Markdown asterisks)
2. A strong, confident half-line (10'12 words) explaining why it fits **this user's vibe**.
3. Platform line:
   - Only if not_prefered_platform is True, say:
     "Not on {platform}, but available on {fallback_platform}."
   - Else, say:
     "You can find this game on {platform}."
Use 1'2 emojis (your choice, but never more). No links. No soft language like “maybe” or “you could”.
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
    """
    Instantly delivers a game recommendation, skipping discovery.

    Returns:
        str: GPT-formatted game message
    """
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    game, _ = await game_recommendation(db=db, user=user, session=session)

    platform_link = None
    description = None

    if not game:
        print("-----------------------------------------------------------")
        user_prompt = (
            f"USER MEMORY & RECENT CHAT:\n"
            f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
            "The user asked for a genre + platform combo that doesn't exist in the database.\n"
            "IF THERE'S NO MATCH:\n"
            "→ Say it with confidence + humor:\n"
            "  - “That combo? Doesn’t even exist yet 😅”\n"
            "  - “You might be onto something new.”\n"
            "  - “You should develop it yourself 😉”\n"
            "→ Then:\n"
            "  - “Want to try some other genres instead?”\n"
            "  - “Wanna flip the vibe completely?”\n"
            "Keep it playful, confident, and warm. Never use robotic or generic language. Gently nudge the user to try something new."
        )
        return user_prompt
    else:
        session.last_recommended_game = game["title"]

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
            # 👇 Draper-style, mini-review checklist for LLM output
            f"→ Mention the game by name — naturally.\n"
            f"→ Give a 3–4 sentence mini-review. Quick and dirty.\n"
            f"   - What's it about?\n"
            f"   - What’s the vibe, mechanic, art, feel, weirdness?\n"
            f"→ Say why it fits: “I thought of this when you said [X]”.\n"
            f"→ Talk casually:\n"
            f"   - “This one hits that mood you dropped”\n"
            f"   - “It’s kinda wild, but I think you’ll like it”\n"
            f"→ Platform mention? Keep it real:\n"
            f"   - “It’s on Xbox too btw”\n"
            f"   - “PC only though — just flagging that”\n"
            f"→ If there’s a link:\n"
            f"   - “Here’s where I found it: {platform_link}”\n"
            f"→ Use your own tone. But be emotionally alive."
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
        f"- Mood: {mood or 'Not given'}\n"
        f"- Genre: {genre or 'Not given'}\n"
        f"- Platform: {platform or 'Not given'}\n\n"
        f"Write a short, warm, and charming confirmation message, never more than 12 words (stop at 12).\n"
        f"Use the mood, genre, and platform above to reflect their vibe and make them feel heard.\n"
        f"Do NOT suggest a game. This is just a friendly check-in to say 'I see you.'\n"
        f"Tone should feel emotionally aware and warmly human — like a friend who gets them."
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
    Now adds freedom-language to each question (e.g. 'or something totally different?')
    """
    user_promt = None
    last_user_tone = get_last_user_tone_from_session(session)
    def get_last(arr):
        return arr[-1] if isinstance(arr, list) and arr else None
    
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    
    if not session.genre:
        mood = session.exit_mood
        platform = get_last(session.platform_preference)
        
        user_promt = f"""
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else "No prior user memory or recent chat."}
    
Speak entirely in the user's tone: {last_user_tone}.  
Use their style, energy, and attitude naturally. Do not describe or name the tone — just talk like that.

Don't mention the tone itself — just speak like someone who naturally talks this way.
You're Thrum — helping someone discover the perfect game.

You already know:
- Mood: {mood or "unknown"}
- Platform: {platform or "unknown"}

Ask ONE fun, casual question to find the user's **preferred game genre**.
ask question of 10-12 words only.
✅ Mention a few examples: e.g. puzzle, action, life-sim, party chaos  
✅ End with something like “or something totally different?”  
✅ Keep tone relaxed and expressive  
✅ Use max one emoji  
❌ Don’t use greetings

🧠 Example styles:
- Are you in the mood for platformers, chill sims, sneaky shooters — or something totally different? 🕹️
- Puzzlers? Action? Party chaos? Or something totally offbeat?
- Looking for strategy, sports, role-playing… or just whatever breaks the rules?
""".strip()

    elif not session.platform_preference:
        mood = session.exit_mood
        genre = get_last(session.genre)
        user_promt = f"""
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else "No prior user memory or recent chat."}
    
Speak entirely in the user's tone: {last_user_tone}.  
Use their style, energy, and attitude naturally. Do not describe or name the tone — just talk like that.

Don’t mention the tone itself — just speak like someone who naturally talks this way.
You're Thrum — a fast, friendly game suggester.

You already know:
- Mood: {mood or "unknown"}
- Genre: {genre or "unknown"}

Ask ONE casual, human question to discover the **platform** the user prefers.
ask question of 10-12 words only.
✅ Mention real examples: PS5, Switch, mobile, browser, VR  
✅ Add a free-choice option like “or something else entirely?”  
✅ Use natural tone  
✅ 1 emoji max  
❌ Never say hello or ask more than one question

🧠 Example styles:
- Do you usually game on PlayStation, Switch, or mobile — or something else entirely? 🎮
- Is it Xbox, VR, mobile taps… or some off-the-map setup?
- PS5 or Switch? Or do you roll with browser games and retro consoles?
""".strip()
        
    elif not session.exit_mood:
        genre = get_last(session.genre)
        platform = get_last(session.platform_preference)
        user_promt = f"""
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else "No prior user memory or recent chat."}
    
Speak entirely in the user's tone: {last_user_tone}.  
Use their style, energy, and attitude naturally. Do not describe or name the tone — just talk like that.

Don't mention the tone itself — just speak like someone who naturally talks this way.
You're Thrum — a playful, emotionally smart game assistant.

You already know:
- Genre: {genre or "unknown"}
- Platform: {platform or "unknown"}

Ask ONE friendly, expressive question to discover the user’s **current mood or emotional vibe**.
ask question of 10-12 words only.
✅ Use casual, human language  
✅ Mention some example moods (e.g. “emotional”, “competitive”, “funny”)  
✅ Add a soft ending like “or something totally different?”  
✅ One emoji max  
❌ No greetings, no double questions

🧠 Example styles:
- What mood are you in — emotional, competitive, or funny? Or something totally different? 🎮
- Feeling chill, chaotic, or in a story-rich kinda headspace… or something else entirely?
- What’s the vibe today — sneaky, calm, cozy? Or are we breaking all the molds?
""".strip()
    else:
        return None
    
    return user_promt
from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
import json
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

async def format_game_output(game: dict, user_context: dict = None) -> str:
    title = game.get("title", "Unknown Game")
    description = game.get("description", "")
    genre = game.get("genre", "")
    vibes = game.get("game_vibes", "")
    mechanics = game.get("mechanics", "")
    visual_style = game.get("visual_style", "")
    has_story = "has a story" if game.get("has_story") else "does not focus on story"
    platforms = game.get("platforms", [])
    # Get user context
    user_mood = user_context.get("mood") if user_context else None
    user_genre = user_context.get("genre") if user_context else None
    platform = user_context.get("platform") if user_context and user_context.get("platform") else (platforms[0] if platforms else None)
    # Construct search line
    if platform:
        search_line = f"Search '{title}' on {platform} or Google."
    else:
        search_line = f"Search '{title} game' online."
    # Summarize user context
    user_summary = ""
    if user_mood:
        user_summary += f"Mood: {user_mood}\n"
    if user_genre:
        user_summary += f"Preferred Genre: {user_genre}\n"
    if platform:
        user_summary += f"Platform: {platform}\n"
    # Game trait summary
    trait_summary = f"Description: {description}\nGenre: {genre}\nVibes: {vibes}\nMechanics: {mechanics}\nVisual Style: {visual_style}\nStory: {has_story}"
    # Final GPT prompt
    prompt = f"""
You are Thrum — a fast, confident game assistant.
The user is looking for a game with:
{user_summary.strip()}
You’re considering:
Game: {title}
{trait_summary}
Write exactly 3 lines:
1. Game title (complusary bold)
2. A strong half-line (10–12 words) explaining why it fits **this user’s vibe** use confident language and should sound like it is perfect fit for this user.
3. A clear platform-specific search instruction like “Search 'Half-Life' on Steam”
Avoid weak phrases like “maybe”, “you could”, or “might like”.
use 1-2 emojis, no links. Just 3 direct lines.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            temperature=0.4,
            messages=[{"role": "user", "content": prompt.strip()}]
        )
        reply = response["choices"][0]["message"]["content"].strip()
        return reply
    except Exception:
        return f"{title}\nA good match for your vibe and preferences.\n{search_line}"



async def deliver_game_immediately(db:Session,user, session) -> str:
    """
    Instantly delivers a game recommendation, skipping discovery.

    Returns:
        str: GPT-formatted game message
    """
    game,_ = await game_recommendation(db=db, user=user, session=session)
    if not game:
        return "Hmm, couldn't find a match right now. Try again soon!"
    else:

        session.last_recommended_game = game["title"]

        session.phase = PhaseEnum.FOLLOWUP
        session.followup_triggered = True

    # Optional: build user_context from session
    user_context = {
        "mood": session.exit_mood,
        "genre": getattr(session, "genre", None),
        "platform": session.platform_preference
    }

    return await format_game_output(game, user_context=user_context)

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
        session.intent_override_triggered = True
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GPT summary fallback:", e)
        parts = [mood, genre, platform]
        summary = ", ".join([p for p in parts if p])
        session.phase = PhaseEnum.DELIVERY
        session.intent_override_triggered = True

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

async def ask_discovery_question(session) -> str:
    """
    Dynamically generate a discovery question using gpt-4.1-mini.
    Now adds freedom-language to each question (e.g. 'or something totally different?')
    """
    def get_last(arr):
        return arr[-1] if isinstance(arr, list) and arr else None
    
    if not session.genre:
        missing_field = "genre"
        mood = session.exit_mood
        platform = get_last(session.platform_preference)
        system_prompt = f"""
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
        user_input = "Ask about genre."

    elif not session.exit_mood:
        missing_field = "mood"
        genre = get_last(session.genre)
        platform = get_last(session.platform_preference)
        system_prompt = f"""
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
        user_input = "Ask about mood."

    elif not session.platform_preference:
        missing_field = "platform"
        mood = session.exit_mood
        genre = get_last(session.genre)
        system_prompt = f"""
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
        user_input = "Ask about platform."

    else:
        return "Tell me anything else you'd like in the game."

    print(f"ask_discovery_question: {missing_field}")
    response = await openai.ChatCompletion.acreate(
        model="gpt-4.1-mini",
        temperature=0.65,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message["content"].strip()
from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
import json
import openai
import os
import random

openai.api_key = os.getenv("OPENAI_API_KEY")

async def format_game_output(game: dict, user_context: dict = None) -> str:
    title = game.get("title", "Unknown Game")
    description = game.get("description", "")
    platforms = game.get("platforms", [])
    platform = user_context.get("platform") if user_context and user_context.get("platform") else (platforms[0] if platforms else None)
    
    # Natural game presentation templates based on examples
    templates = [
        f"Cool. Just dropping in with a quick game rec — {title}. {description[:80]}...",
        f"Here's another mellow one: {title}. {description[:60]}...",
        f"One last one for now: {title}. {description[:70]}...",
        f"Here's a wild card: {title}. {description[:65]}...",
        f"If you liked that, you might love {title} — {description[:70]}..."
    ]
    
    # Add search instruction naturally
    search_suggestions = [
        f"Want me to send a steam link?" if platform and "PC" in str(platform) else None,
        f"Search '{title}' on {platform}" if platform else None,
        f"Want a link to check it out?",
        f"Ever heard of it?"
    ]
    
    base_rec = random.choice(templates)
    search_line = random.choice([s for s in search_suggestions if s is not None]) if any(search_suggestions) else "Worth a look!"
    
    return f"{base_rec}\n\n{search_line}"

async def deliver_game_immediately(db:Session,user, session) -> str:
    """
    Instantly delivers a game recommendation, skipping discovery.
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
    Natural confirmation responses based on examples
    """
    # Natural confirmation responses based on examples
    confirmations = [
        "Good call. Journey is great for switching off without feeling empty.",
        "Perfect. Loads of good fits there.",
        "Gotcha. Handy to know for those bite-sized suggestions.",
        "Cool — something chill coming up!",
        "Nice — I'll keep PC picks coming.",
        "Fair enough — not everything clicks.",
        "Got it — let me find something for you."
    ]
    
    session.phase = PhaseEnum.DELIVERY
    session.intent_override_triggered = True
    return random.choice(confirmations)

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
    Natural discovery questions based on conversation examples
    """
    def get_last(arr):
        return arr[-1] if isinstance(arr, list) and arr else None
    
    # Natural question variations based on examples
    if not session.genre:
        questions = [
            "Are you in the mood for something relaxing like this, or more high-energy today?",
            "You feeling like something chill or something with action today?",
            "Are you more into shooters or strategy-type stuff?",
            "Mind if I ask what kind of shooters do work for you?",
            "You mentioned unwinding—do you usually lean toward games with a bit of story, or more gameplay-focused stuff?"
        ]
        return random.choice(questions)
    
    elif not session.platform_preference:
        questions = [
            "Quick one, just so I don't send anything unplayable: what do you usually play on?",
            "BTW—what do you usually play on?",
            "Quick question. what platform do you usually play on?",
            "Just curious—do you ever play on mobile when you're not at your desk? Or stick to PC?",
            "Do you usually play on mobile, or do you game elsewhere too?"
        ]
        return random.choice(questions)
    
    elif not session.exit_mood:
        questions = [
            "But out of curiosity — are you in the mood for something relaxing like this, or more high-energy today?",
            "Is it the building, the pacing, the chaos—or just the whole thing together that works for you?",
            "What mood are you in — emotional, competitive, funny, or something totally different?",
            "You feeling chill, chaotic, or in a story-rich kinda headspace?"
        ]
        return random.choice(questions)
    
    # Fallback to GPT for edge cases
    system_prompt = f"""
You're Thrum — casual, friendly game recommender. Ask a natural follow-up question like:

"Also, I can remember your name for next time if you like — want me to?"
"Oh, and when do you usually find time to play? Evening? Weekend afternoons?"
"Want me to remember your name for next time, or keep it anonymous?"

Keep it conversational and human. One question only.
"""
    
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4.1-mini",
            temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": "Ask a natural follow-up question"}
            ]
        )
        return response.choices[0].message["content"].strip()
    except Exception:
        return "Also, I can remember your name for next time if you like — want me to?"
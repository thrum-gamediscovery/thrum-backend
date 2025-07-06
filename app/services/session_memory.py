from app.services.game_recommend import game_recommendation
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
from app.services.conversation_learning import ThrumMemory, ConversationFlow, get_personalized_game_recommendation
from app.services.session_utils import get_asked_questions, mark_question_asked, has_asked_question
import json
import openai
import os
import random

openai.api_key = os.getenv("OPENAI_API_KEY")

async def format_game_output(game: dict, user_context: dict = None, session=None) -> str:
    title = game.get("title", "Unknown Game")
    description = game.get("description", "")
    platforms = game.get("platforms", [])
    platform = user_context.get("platform") if user_context and user_context.get("platform") else (platforms[0] if platforms else None)
    
    # Context-aware templates based on conversation flow
    mood = user_context.get("mood", "").lower() if user_context else ""
    interaction_count = len(session.interactions) if session and session.interactions else 0
    
    if "relax" in mood or "chill" in mood:
        templates = [
            f"Cool. Just dropping in with a quick game rec — {title}. {description[:50]}...",
            f"Here's another mellow one: {title}. {description[:45]}...",
            f"Perfect for unwinding: {title}. {description[:50]}..."
        ]
    elif "action" in mood or "energy" in mood:
        templates = [
            f"Alright — if you're in the mood for something punchy, {title}. {description[:50]}...",
            f"Here's a wild card: {title}. {description[:45]}...",
            f"This one's got some kick: {title}. {description[:50]}..."
        ]
    else:
        templates = [
            f"Cool. Just dropping in with a quick game rec — {title}. {description[:50]}...",
            f"Here's something different: {title}. {description[:45]}...",
            f"You might dig this: {title}. {description[:50]}..."
        ]
    
    # Natural follow-up based on platform and context
    followups = []
    if platform and "PC" in str(platform):
        followups.extend(["Want me to send a steam link?", "Ever heard of it?"])
    elif platform and "mobile" in str(platform).lower():
        followups.extend(["Want a link to check it out?", "Ring a bell?"])
    else:
        followups.extend(["Ever heard of it?", "Sound familiar?", "Worth a look!"])
    
    base_rec = random.choice(templates)
    followup = random.choice(followups)
    
    return f"{base_rec}\n\n{followup}"

async def deliver_game_immediately(db:Session,user, session) -> str:
    """
    Instantly delivers a personalized game recommendation using memory layer.
    """
    game,_ = await game_recommendation(db=db, user=user, session=session)
    if not game:
        return "Hmm, couldn't find a match right now. Try again soon!"
    else:
        session.last_recommended_game = game["title"]
        session.phase = PhaseEnum.FOLLOWUP
        session.followup_triggered = True

    # Use memory-aware recommendation formatting
    return get_personalized_game_recommendation(db, user, session, game)

async def confirm_input_summary(session) -> str:
    """
    Memory-aware confirmation responses
    """
    from app.services.conversation_learning import ThrumMemory
    
    # Use memory layer for contextual responses
    memory = ThrumMemory(None, None, session)
    profile = memory.get_user_profile()
    
    mood = session.exit_mood or session.entry_mood
    platform = profile["platform"]
    
    # Context-specific confirmations
    if mood and "relax" in mood.lower():
        confirmations = [
            "Good call. Perfect for switching off without feeling empty.",
            "Nice — something mellow coming up.",
            "Got it — chill vibes it is."
        ]
    elif platform and "PC" in str(platform):
        confirmations = [
            "Perfect. Loads of good fits there.",
            "Nice — I'll keep PC picks coming.",
            "Cool — PC has some great options."
        ]
    elif platform and "mobile" in str(platform).lower():
        confirmations = [
            "Gotcha. Handy to know for those bite-sized suggestions.",
            "Perfect for on-the-go gaming.",
            "Mobile has some hidden gems."
        ]
    else:
        confirmations = [
            "Got it — let me find something good for you.",
            "Cool — I've got some ideas.",
            "Alright, let me dig up something perfect."
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
    Context-aware discovery questions that avoid repetition
    """
    interaction_count = len(session.interactions) if session.interactions else 0
    asked_questions = get_asked_questions(session)
    
    # Mood/genre questions
    if not session.genre and "mood" not in asked_questions:
        questions = [
            "Are you in the mood for something relaxing, or more high-energy today?",
            "You feeling like something chill or something with action?",
            "What's the vibe — story-heavy or pure gameplay?"
        ]
        mark_question_asked(session, "mood")
        return random.choice(questions)
    
    # Platform questions
    elif not session.platform_preference and "platform" not in asked_questions:
        questions = [
            "Quick one — what do you usually play on?",
            "Just curious—do you ever play on mobile or stick to one platform?",
            "What's your go-to gaming setup?"
        ]
        mark_question_asked(session, "platform")
        return random.choice(questions)
    
    # Natural conversation builders
    elif interaction_count >= 3 and "name" not in asked_questions:
        mark_question_asked(session, "name")
        return "Also, I can remember your name for next time if you like — want me to?"
    
    elif interaction_count >= 5 and "playtime" not in asked_questions:
        mark_question_asked(session, "playtime")
        return "Oh, and when do you usually find time to play? Evening? Weekend afternoons?"
    
    # Fallback - keep it natural
    return "Tell me a bit more about what you're in the mood for?"
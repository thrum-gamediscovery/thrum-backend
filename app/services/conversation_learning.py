"""
Thrum Learning & Improvement Layer
Handles memory, personalization, and natural conversation flow
"""
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session
from app.db.models.interaction import Interaction
from app.db.models.enums import SenderEnum
from app.services.session_utils import get_asked_questions, mark_question_asked, has_asked_question
import random

class ThrumMemory:
    """
    Simulates memory for mini-LLMs by tracking user preferences and conversation patterns
    """
    
    def __init__(self, db: DBSession, user, session):
        self.db = db
        self.user = user
        self.session = session
        
    def get_user_profile(self) -> dict:
        """
        Build comprehensive user profile for personalization
        """
        profile = {
            "name": getattr(self.user, "name", None),
            "platform": self.session.platform_preference[-1] if self.session and self.session.platform_preference else None,
            "mood_tags": [],
            "reject_tags": [],
            "story_pref": getattr(self.session, "story_preference", None),
            "playtime": getattr(self.user, "playtime", None),
            "interaction_count": len(self.session.interactions) if self.session else 0,
            "asked_questions": get_asked_questions(self.session)
        }
        
        # Extract mood patterns
        if self.session:
            if self.session.entry_mood:
                profile["mood_tags"].append(self.session.entry_mood)
            if self.session.exit_mood:
                profile["mood_tags"].append(self.session.exit_mood)
                
        return profile
    
    def should_avoid_repetition(self, question_type: str) -> bool:
        """
        Check if we've already asked this type of question
        """
        return has_asked_question(self.session, question_type)
    
    def mark_question_asked(self, question_type: str):
        """
        Mark a question type as asked to avoid repetition
        """
        mark_question_asked(self.session, question_type)
    
    def get_contextual_acknowledgment(self, user_input: str) -> str:
        """
        Generate contextual acknowledgments based on conversation history
        """
        user_lower = user_input.lower()
        profile = self.get_user_profile()
        
        # Context-specific responses
        if "relaxing" in user_lower or "chill" in user_lower:
            return "Good call. Perfect for switching off without feeling empty."
        elif "pc" in user_lower and profile["platform"] != "PC":
            return "Perfect. Loads of good fits there."
        elif "mobile" in user_lower:
            return "Gotcha. Handy to know for those bite-sized suggestions."
        elif any(word in user_lower for word in ["don't like", "hate", "not into"]):
            return "Fair enough — not everything clicks."
        elif "fortnite" in user_lower:
            return "Respect. Fortnite's kind of its own genre at this point 😄"
        elif "story" in user_lower and "love" in user_lower:
            return "Same here. Nothing better than a quiet game that still sticks with you."
        else:
            return random.choice(["Got it.", "Cool.", "Nice.", "Makes sense."])
    
    def get_natural_transition(self) -> str:
        """
        Get natural conversation transitions that build on context
        """
        profile = self.get_user_profile()
        
        # Priority-based transitions
        if not profile["name"] and not self.should_avoid_repetition("name") and profile["interaction_count"] >= 3:
            self.mark_question_asked("name")
            return "Also, I can remember your name for next time if you like — want me to?"
        
        elif not profile["platform"] and not self.should_avoid_repetition("platform"):
            self.mark_question_asked("platform")
            return "Quick one — what do you usually play on?"
        
        elif not profile["playtime"] and not self.should_avoid_repetition("playtime") and profile["interaction_count"] >= 5:
            self.mark_question_asked("playtime")
            return "Oh, and when do you usually find time to play? Evening? Weekend afternoons?"
        
        else:
            # Natural conversation continuers
            return random.choice([
                "How's that sound?",
                "Ring a bell?",
                "Worth a look?",
                "Sound good?"
            ])
    
    def build_context_for_llm(self, base_prompt: str) -> str:
        """
        Build memory-aware context for LLM prompts
        """
        profile = self.get_user_profile()
        recent_interactions = []
        
        if self.session and self.session.interactions:
            recent_interactions = [
                interaction.content for interaction in self.session.interactions[-3:]
            ]
        
        context = f"""
User Profile:
- Name: {profile['name'] or 'Unknown'}
- Platform: {profile['platform'] or 'Unknown'}
- Mood: {', '.join(profile['mood_tags']) if profile['mood_tags'] else 'Unknown'}
- Interactions: {profile['interaction_count']}
- Asked questions: {profile['asked_questions']}

Recent conversation:
{chr(10).join(recent_interactions[-2:]) if recent_interactions else 'None'}

Personality: Casual, friendly, remembers context, avoids repetition

{base_prompt}
"""
        return context

class ConversationFlow:
    """
    Manages natural conversation flow and prevents repetitive interactions
    """
    
    def __init__(self, memory: ThrumMemory):
        self.memory = memory
    
    def get_mood_aware_game_intro(self, game: dict, mood: str = None) -> str:
        """
        Generate mood-aware game introductions
        """
        title = game.get("title", "Unknown Game")
        description = game.get("description", "")[:50]
        
        if mood and "relax" in mood.lower():
            templates = [
                f"Cool. Just dropping in with a quick game rec — {title}. {description}...",
                f"Here's another mellow one: {title}. {description}...",
                f"Perfect for unwinding: {title}. {description}..."
            ]
        elif mood and "action" in mood.lower():
            templates = [
                f"Alright — if you're in the mood for something punchy, {title}. {description}...",
                f"Here's a wild card: {title}. {description}...",
                f"This one's got some kick: {title}. {description}..."
            ]
        else:
            templates = [
                f"Cool. Just dropping in with a quick game rec — {title}. {description}...",
                f"Here's something different: {title}. {description}...",
                f"You might dig this: {title}. {description}..."
            ]
        
        return random.choice(templates)
    
    def get_platform_aware_followup(self, platform: str = None) -> str:
        """
        Generate platform-specific follow-ups
        """
        if platform and "PC" in str(platform):
            if not self.memory.should_avoid_repetition("steam"):
                self.memory.mark_question_asked("steam")
                return "Want me to send a steam link?"
            else:
                return "Ever heard of it?"
        elif platform and "mobile" in str(platform).lower():
            return "Want a link to check it out?"
        else:
            return random.choice(["Ever heard of it?", "Sound familiar?", "Worth a look!"])
    
    def should_ask_personal_question(self) -> tuple[bool, str]:
        """
        Determine if we should ask a personal question and which one
        """
        profile = self.memory.get_user_profile()
        
        if not profile["name"] and not self.memory.should_avoid_repetition("name") and profile["interaction_count"] >= 3:
            return True, "name"
        elif not profile["playtime"] and not self.memory.should_avoid_repetition("playtime") and profile["interaction_count"] >= 5:
            return True, "playtime"
        
        return False, None

def create_memory_aware_response(db: DBSession, user, session, user_input: str, base_response: str = None) -> str:
    """
    Factory function to create memory-aware responses
    """
    memory = ThrumMemory(db, user, session)
    flow = ConversationFlow(memory)
    
    # If we have a base response, enhance it with context
    if base_response:
        return base_response
    
    # Otherwise, generate contextual acknowledgment
    return memory.get_contextual_acknowledgment(user_input)

def get_personalized_game_recommendation(db: DBSession, user, session, game: dict) -> str:
    """
    Generate personalized game recommendations based on user profile
    """
    memory = ThrumMemory(db, user, session)
    flow = ConversationFlow(memory)
    profile = memory.get_user_profile()
    
    # Generate mood-aware intro
    mood = profile["mood_tags"][-1] if profile["mood_tags"] else None
    game_intro = flow.get_mood_aware_game_intro(game, mood)
    
    # Add platform-aware follow-up
    platform_followup = flow.get_platform_aware_followup(profile["platform"])
    
    return f"{game_intro}\n\n{platform_followup}"
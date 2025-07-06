from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session
from app.db.models.interaction import Interaction
from app.db.models.enums import SenderEnum
import random

class ConversationMemory:
    """
    Handles natural conversation memory and context for Thrum
    """
    
    def __init__(self, db: DBSession, user, session):
        self.db = db
        self.user = user
        self.session = session
        
    def get_user_context(self) -> dict:
        """
        Build user context for natural responses
        """
        return {
            "name": getattr(self.user, "name", None),
            "mood": self.session.exit_mood if self.session else None,
            "platform": self.session.platform_preference[-1] if self.session and self.session.platform_preference else None,
            "genre": self.session.genre[-1] if self.session and self.session.genre else None,
            "last_game": self.session.last_recommended_game if self.session else None,
            "interaction_count": len(self.session.interactions) if self.session else 0
        }
    
    def get_conversation_history(self, limit: int = 5) -> list:
        """
        Get recent conversation history for context
        """
        if not self.session or not self.session.interactions:
            return []
            
        recent_interactions = self.session.interactions[-limit:]
        return [
            {
                "sender": interaction.sender.value,
                "content": interaction.content,
                "timestamp": interaction.timestamp
            }
            for interaction in recent_interactions
        ]
    
    def should_ask_name(self) -> bool:
        """
        Determine if we should ask for the user's name
        """
        return (
            not getattr(self.user, "name", None) and 
            self.session and 
            len(self.session.interactions) >= 3
        )
    
    def should_ask_playtime(self) -> bool:
        """
        Determine if we should ask about playtime preferences
        """
        return (
            not getattr(self.user, "playtime", None) and
            self.session and
            len(self.session.interactions) >= 5
        )
    
    def get_natural_transition(self) -> str:
        """
        Get contextual conversation transitions that avoid repetition
        """
        asked_questions = getattr(self.session, 'asked_questions', []) or []
        
        if self.should_ask_name() and "name" not in asked_questions:
            return "Also, I can remember your name for next time if you like — want me to?"
        elif self.should_ask_playtime() and "playtime" not in asked_questions:
            return "Oh, and when do you usually find time to play? Evening? Weekend afternoons?"
        elif not self.session.platform_preference and "platform" not in asked_questions:
            return "Just curious—do you ever play on mobile when you're not at your desk?"
        else:
            # Natural conversation continuers
            transitions = [
                "How's that sound?",
                "Ring a bell?",
                "Worth a look?",
                "Sound good or want something different?"
            ]
            return random.choice(transitions)
    
    def get_personalized_greeting(self) -> str:
        """
        Get personalized greeting based on user context and history
        """
        name = getattr(self.user, "name", None)
        interaction_count = len(self.session.interactions) if self.session and self.session.interactions else 0
        
        if name:
            if interaction_count == 0:
                return f"Nice to meet you properly, {name} 🙌"
            else:
                greetings = [
                    f"Hey {name} 👋 Back for more game recs?",
                    f"Hey {name} — what's the vibe today?",
                    f"Alright {name}, ready for another rec?"
                ]
                return random.choice(greetings)
        
        return None
    
    def get_acknowledgment_response(self, user_input: str) -> str:
        """
        Get contextual acknowledgment responses that build on conversation
        """
        user_lower = user_input.lower()
        
        # Specific contextual responses
        if "relaxing" in user_lower or "chill" in user_lower:
            return "Good call. Perfect for switching off without feeling empty."
        elif "pc" in user_lower and "gaming" in user_lower:
            return "Perfect. Loads of good fits there."
        elif "mobile" in user_lower:
            return "Gotcha. Handy to know for those bite-sized suggestions."
        elif any(word in user_lower for word in ["don't like", "hate", "not into"]):
            return "Fair enough — not everything clicks."
        elif "fortnite" in user_lower:
            return "Respect. Fortnite's kind of its own genre at this point 😄"
        elif "story" in user_lower and "love" in user_lower:
            return "Same here. Nothing better than a quiet game that still sticks with you."
        elif "evening" in user_lower or "night" in user_lower:
            return "Perfect timing for some good gaming."
        else:
            # Generic but natural acknowledgments
            acknowledgments = [
                "Got it.",
                "Cool.",
                "Nice.",
                "Makes sense.",
                "I hear you.",
                "Solid."
            ]
            return random.choice(acknowledgments)
    
    def get_natural_question_followup(self, topic: str) -> str:
        """
        Get natural follow-up questions based on topic
        """
        followups = {
            "platform": [
                "Just curious—do you ever play on mobile when you're not at your desk? Or stick to PC?",
                "Do you usually play on mobile, or do you game elsewhere too?",
                "Quick one, just so I don't send anything unplayable: what do you usually play on?"
            ],
            "mood": [
                "Are you in the mood for something relaxing like this, or more high-energy today?",
                "You feeling like something chill or something with action today?",
                "What mood are you in — emotional, competitive, funny, or something totally different?"
            ],
            "genre": [
                "Are you more into shooters or strategy-type stuff?",
                "Mind if I ask what kind of shooters do work for you?",
                "You mentioned unwinding—do you usually lean toward games with a bit of story, or more gameplay-focused stuff?"
            ],
            "story": [
                "You mentioned unwinding—do you usually lean toward games with a bit of story, or more gameplay-focused stuff?",
                "Bit of both, but I love a good story",
                "Do you usually go for games with story or ones that skip it?"
            ]
        }
        
        return random.choice(followups.get(topic, ["Tell me more about that."]))
    
    def build_context_prompt(self, base_prompt: str) -> str:
        """
        Build memory-aware context for natural responses
        """
        context = self.get_user_context()
        history = self.get_conversation_history(3)
        asked_questions = getattr(self.session, 'asked_questions', []) or []
        
        context_info = f"""
User Context:
- Name: {context['name'] or 'Unknown'}
- Mood: {context['mood'] or 'Unknown'}  
- Platform: {context['platform'] or 'Unknown'}
- Genre: {context['genre'] or 'Unknown'}
- Interactions: {context['interaction_count']}
- Asked questions: {asked_questions}

Recent conversation:
{chr(10).join([f"{h['sender']}: {h['content']}" for h in history[-3:]])}

Personality: Casual, friendly, remembers context, avoids repetition

{base_prompt}
"""
        return context_info
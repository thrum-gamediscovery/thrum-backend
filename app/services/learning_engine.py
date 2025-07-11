from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
import json

class UserLearningProfile:
    def __init__(self, user, session):
        self.user = user
        self.session = session
        self.profile = self._load_profile()
    
    def _load_profile(self):
        """Load user learning profile"""
        return {
            "platform": self._get_platform(),
            "mood_tags": list(self.user.mood_tags.values()) if self.user.mood_tags else [],
            "reject_tags": self.user.reject_tags.get("genre", []) if self.user.reject_tags else [],
            "story_pref": self.user.story_pref,
            "playtime": self.user.playtime,
            "name": self.user.name,
            "interaction_count": len(self.session.interactions),
            "rejected_games": self.session.rejected_games or [],
            "last_game": self.session.last_recommended_game,
            "engagement_level": self._calculate_engagement()
        }
    
    def _get_platform(self):
        if self.session.platform_preference:
            return self.session.platform_preference[-1]
        if self.user.platform_prefs:
            return list(self.user.platform_prefs.values())[-1]
        return None
    
    def _calculate_engagement(self):
        interactions = len(self.session.interactions)
        if interactions >= 8: return "high"
        if interactions >= 4: return "medium"
        return "low"
    
    def log_feedback(self, accepted=None, rejected_game=None, mood=None):
        """Log user feedback for learning"""
        feedback = {
            "session_id": str(self.session.session_id),
            "user_id": str(self.user.user_id),
            "timestamp": datetime.utcnow().isoformat(),
            "mood_inferred": mood or self.session.exit_mood,
            "rec_accepted": accepted,
            "rec_rejected": rejected_game,
            "engagement_score": self._calculate_engagement(),
            "interaction_phase": str(self.session.phase)
        }
        
        # Store in session metadata for now
        if not self.session.meta_data:
            self.session.meta_data = {}
        
        self.session.meta_data["learning_feedback"] = feedback
        flag_modified(self.session, "meta_data")
    
    def update_preferences(self, **kwargs):
        """Update user preferences based on conversation"""
        for key, value in kwargs.items():
            if key == "mood" and value:
                today = datetime.utcnow().date().isoformat()
                self.user.mood_tags[today] = value
                flag_modified(self.user, "mood_tags")
            elif key == "platform" and value:
                today = datetime.utcnow().date().isoformat()
                if not self.user.platform_prefs:
                    self.user.platform_prefs = {}
                self.user.platform_prefs[today] = [value]
                flag_modified(self.user, "platform_prefs")
            elif key == "story_pref" and value is not None:
                self.user.story_pref = value
            elif key == "playtime" and value:
                self.user.playtime = value
            elif key == "name" and value:
                self.user.name = value

def build_personalized_context(user, session):
    """Build context for dynamic responses"""
    profile = UserLearningProfile(user, session)
    
    context = {
        "user_profile": profile.profile,
        "conversation_stage": _determine_conversation_stage(session),
        "next_question_type": _get_next_question_type(profile.profile),
        "personalization_level": _get_personalization_level(profile.profile)
    }
    
    return context

def _determine_conversation_stage(session):
    """Determine what stage of conversation we're in"""
    interactions = len(session.interactions)
    
    if interactions <= 2:
        return "greeting"
    elif interactions <= 4:
        return "discovery"
    elif interactions <= 6:
        return "recommendation"
    else:
        return "conclusion"

def _get_next_question_type(profile):
    """Determine what to ask next based on missing info"""
    missing = []
    
    if not profile.get("platform"):
        missing.append("platform")
    if not profile.get("mood_tags"):
        missing.append("mood")
    if profile.get("story_pref") is None:
        missing.append("story_preference")
    if not profile.get("playtime"):
        missing.append("playtime")
    if not profile.get("name"):
        missing.append("name")
    
    return missing[0] if missing else "recommendation"

def _get_personalization_level(profile):
    """Determine how personalized we can be"""
    known_items = sum([
        bool(profile.get("platform")),
        bool(profile.get("mood_tags")),
        bool(profile.get("name")),
        profile.get("story_pref") is not None,
        bool(profile.get("playtime"))
    ])
    
    if known_items >= 4: return "high"
    if known_items >= 2: return "medium"
    return "low"
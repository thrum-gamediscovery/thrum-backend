from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

class ContextEnhancer:
    def __init__(self, user, session):
        self.user = user
        self.session = session

    def enhance_conversation_context(self) -> Dict:
        """Build rich context for more natural conversations"""
        
        context = {
            "user_personality": self._analyze_user_personality(),
            "conversation_flow": self._analyze_conversation_flow(),
            "preference_confidence": self._calculate_preference_confidence(),
            "interaction_patterns": self._analyze_interaction_patterns(),
            "recommendation_history": self._get_recommendation_context()
        }
        
        return context

    def _analyze_user_personality(self) -> Dict:
        """Analyze user's communication style and preferences"""
        personality = {
            "communication_style": "casual",
            "enthusiasm_level": "medium",
            "detail_preference": "moderate",
            "decision_speed": "normal"
        }
        
        if not self.session.interactions:
            return personality
        
        recent_messages = [i.content for i in self.session.interactions[-5:] if i.sender.name == "User"]
        
        # Analyze communication style
        total_length = sum(len(msg) for msg in recent_messages)
        avg_length = total_length / len(recent_messages) if recent_messages else 0
        
        if avg_length > 100:
            personality["communication_style"] = "detailed"
            personality["detail_preference"] = "high"
        elif avg_length < 20:
            personality["communication_style"] = "brief"
            personality["detail_preference"] = "low"
        
        # Analyze enthusiasm
        enthusiasm_indicators = ['!', '😊', '🎮', 'awesome', 'cool', 'love', 'amazing']
        enthusiasm_count = sum(
            sum(indicator in msg.lower() for indicator in enthusiasm_indicators)
            for msg in recent_messages
        )
        
        if enthusiasm_count > 3:
            personality["enthusiasm_level"] = "high"
        elif enthusiasm_count == 0:
            personality["enthusiasm_level"] = "low"
        
        return personality

    def _analyze_conversation_flow(self) -> Dict:
        """Analyze the natural flow of conversation"""
        flow = {
            "stage": "introduction",
            "momentum": "building",
            "topic_consistency": "focused",
            "user_initiative": "responsive"
        }
        
        interaction_count = len(self.session.interactions)
        
        # Determine conversation stage
        if interaction_count <= 2:
            flow["stage"] = "introduction"
        elif interaction_count <= 6:
            flow["stage"] = "discovery"
        elif interaction_count <= 12:
            flow["stage"] = "recommendation"
        else:
            flow["stage"] = "ongoing"
        
        # Analyze momentum
        if interaction_count > 0:
            recent_timestamps = [i.timestamp for i in self.session.interactions[-3:] if i.timestamp]
            if len(recent_timestamps) >= 2:
                time_gaps = [
                    (recent_timestamps[i] - recent_timestamps[i-1]).total_seconds()
                    for i in range(1, len(recent_timestamps))
                ]
                avg_gap = sum(time_gaps) / len(time_gaps)
                
                if avg_gap < 30:  # Quick responses
                    flow["momentum"] = "high"
                elif avg_gap > 300:  # Slow responses
                    flow["momentum"] = "low"
        
        return flow

    def _calculate_preference_confidence(self) -> Dict:
        """Calculate confidence in user preferences"""
        confidence = {
            "mood": 0.0,
            "genre": 0.0,
            "platform": 0.0,
            "overall": 0.0
        }
        
        # Mood confidence
        if self.session.exit_mood:
            confidence["mood"] = 0.8
        elif self.user.mood_tags:
            confidence["mood"] = 0.6
        
        # Genre confidence
        if self.user.genre_prefs:
            genre_mentions = sum(len(genres) for genres in self.user.genre_prefs.values())
            confidence["genre"] = min(genre_mentions * 0.2, 1.0)
        
        # Platform confidence
        if self.user.platform_prefs:
            platform_mentions = sum(len(platforms) for platforms in self.user.platform_prefs.values())
            confidence["platform"] = min(platform_mentions * 0.3, 1.0)
        
        # Overall confidence
        confidence["overall"] = (confidence["mood"] + confidence["genre"] + confidence["platform"]) / 3
        
        return confidence

    def _analyze_interaction_patterns(self) -> Dict:
        """Analyze user's interaction patterns"""
        patterns = {
            "response_style": "balanced",
            "question_frequency": "normal",
            "preference_sharing": "gradual",
            "feedback_style": "constructive"
        }
        
        if not self.session.interactions:
            return patterns
        
        user_messages = [i.content for i in self.session.interactions if i.sender.name == "User"]
        
        # Analyze question frequency
        question_count = sum(msg.count('?') for msg in user_messages)
        if question_count > len(user_messages) * 0.5:
            patterns["question_frequency"] = "high"
        elif question_count == 0:
            patterns["question_frequency"] = "low"
        
        # Analyze preference sharing
        preference_keywords = ['like', 'love', 'prefer', 'want', 'need', 'enjoy']
        preference_mentions = sum(
            sum(keyword in msg.lower() for keyword in preference_keywords)
            for msg in user_messages
        )
        
        if preference_mentions > len(user_messages):
            patterns["preference_sharing"] = "open"
        elif preference_mentions == 0:
            patterns["preference_sharing"] = "reserved"
        
        return patterns

    def _get_recommendation_context(self) -> Dict:
        """Get context about previous recommendations"""
        context = {
            "total_recommendations": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "last_recommendation": None,
            "recommendation_success_rate": 0.0
        }
        
        if self.session.game_recommendations:
            context["total_recommendations"] = len(self.session.game_recommendations)
            
            # Count accepted/rejected
            for rec in self.session.game_recommendations:
                if hasattr(rec, 'accepted') and rec.accepted is True:
                    context["accepted_count"] += 1
                elif hasattr(rec, 'accepted') and rec.accepted is False:
                    context["rejected_count"] += 1
            
            # Calculate success rate
            if context["total_recommendations"] > 0:
                context["recommendation_success_rate"] = context["accepted_count"] / context["total_recommendations"]
        
        if self.session.last_recommended_game:
            context["last_recommendation"] = self.session.last_recommended_game
        
        return context

    def get_conversation_suggestions(self) -> List[str]:
        """Get suggestions for natural conversation flow"""
        context = self.enhance_conversation_context()
        suggestions = []
        
        # Based on conversation stage
        stage = context["conversation_flow"]["stage"]
        confidence = context["preference_confidence"]["overall"]
        
        if stage == "introduction" and confidence < 0.3:
            suggestions.append("Ask about their current mood or gaming vibe")
            suggestions.append("Inquire about their preferred gaming platform")
        
        elif stage == "discovery" and confidence < 0.7:
            suggestions.append("Dig deeper into their genre preferences")
            suggestions.append("Ask about recent games they've enjoyed")
        
        elif stage == "recommendation" and confidence > 0.6:
            suggestions.append("Provide a specific game recommendation")
            suggestions.append("Explain why the game matches their preferences")
        
        elif stage == "ongoing":
            suggestions.append("Ask for feedback on previous recommendations")
            suggestions.append("Explore new gaming interests")
        
        return suggestions

def create_context_enhancer(user, session):
    """Factory function to create context enhancer"""
    return ContextEnhancer(user, session)
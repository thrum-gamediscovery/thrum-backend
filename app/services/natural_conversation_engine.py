from openai import OpenAI
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
from app.services.context_enhancer import create_context_enhancer

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class NaturalConversationEngine:
    def __init__(self, user, session, db):
        self.user = user
        self.session = session
        self.db = db
        self.conversation_memory = self._build_conversation_memory()
        self.user_profile = self._build_user_profile()
        self.context_enhancer = create_context_enhancer(user, session)

    def _build_conversation_memory(self) -> List[Dict]:
        """Build recent conversation history for context"""
        memory = []
        recent_interactions = self.session.interactions[-8:] if self.session.interactions else []
        
        for interaction in recent_interactions:
            role = "user" if interaction.sender.name == "User" else "assistant"
            memory.append({
                "role": role,
                "content": interaction.content,
                "timestamp": interaction.timestamp.isoformat() if interaction.timestamp else None
            })
        return memory

    def _build_user_profile(self) -> Dict:
        """Build comprehensive user profile for context"""
        profile = {
            "name": self.user.name,
            "interaction_count": len(self.session.interactions),
            "preferences": {},
            "recent_activity": {}
        }
        
        # Recent preferences
        today = datetime.utcnow().date().isoformat()
        if self.user.platform_prefs:
            recent_platforms = []
            for platform_list in list(self.user.platform_prefs.values())[-2:]:
                recent_platforms.extend(platform_list)
            profile["preferences"]["platforms"] = list(set(recent_platforms))
        
        if self.user.genre_prefs:
            recent_genres = []
            for genre_list in list(self.user.genre_prefs.values())[-2:]:
                recent_genres.extend(genre_list)
            profile["preferences"]["genres"] = list(set(recent_genres))
        
        if self.user.mood_tags:
            recent_moods = list(self.user.mood_tags.values())[-3:]
            profile["preferences"]["recent_moods"] = recent_moods
        
        # Session context
        profile["recent_activity"] = {
            "current_mood": self.session.exit_mood,
            "last_recommended_game": self.session.last_recommended_game,
            "rejected_games": len(self.session.rejected_games or []),
            "session_length": len(self.session.interactions)
        }
        
        return profile

    async def process_message(self, user_input: str) -> str:
        """Process user message and generate natural response"""
        print(f"🧠 Processing: {user_input}")
        
        # Analyze user input for intent and information
        analysis = await self._analyze_input(user_input)
        print(f"📊 Analysis: {analysis}")
        
        # Update user profile based on analysis
        await self._update_profile(analysis)
        
        # Generate contextual response
        response = await self._generate_response(user_input, analysis)
        print(f"💬 Response: {response}")
        
        return response

    async def _analyze_input(self, user_input: str) -> Dict:
        """Analyze user input for intent, preferences, and context"""
        
        system_prompt = f"""You are analyzing user input for a game recommendation conversation.

CONVERSATION CONTEXT:
{json.dumps(self.user_profile, indent=2)}

RECENT CONVERSATION:
{json.dumps(self.conversation_memory[-4:], indent=2)}

Analyze the user's message and extract:
1. Intent (greeting, game_request, preference_sharing, feedback, question, casual_chat)
2. Preferences mentioned (mood, genre, platform, etc.)
3. Emotional tone (excited, casual, frustrated, curious, etc.)
4. Information provided (name, age, location, etc.)
5. Game feedback (if responding to a recommendation)

Return JSON:
{{
    "intent": "primary intent",
    "preferences": {{
        "mood": "extracted mood or null",
        "genre": "extracted genre or null", 
        "platform": "extracted platform or null",
        "game_vibe": "how they want the game to feel"
    }},
    "personal_info": {{
        "name": "extracted name or null",
        "age": "extracted age or null",
        "location": "extracted location or null"
    }},
    "game_feedback": {{
        "game_mentioned": "specific game mentioned or null",
        "reaction": "positive/negative/neutral or null",
        "reason": "why they liked/disliked it"
    }},
    "emotional_tone": "detected emotional tone",
    "conversation_stage": "early/getting_to_know/recommending/following_up/ending"
}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            print(f"Analysis error: {e}")
            return {"intent": "casual_chat", "preferences": {}, "personal_info": {}, "game_feedback": {}, "emotional_tone": "neutral", "conversation_stage": "early"}

    async def _update_profile(self, analysis: Dict):
        """Update user profile based on analysis"""
        changes_made = False
        today = datetime.utcnow().date().isoformat()
        
        # Update personal info
        personal_info = analysis.get("personal_info", {})
        if personal_info.get("name") and not self.user.name:
            self.user.name = personal_info["name"]
            changes_made = True
        
        # Update preferences
        preferences = analysis.get("preferences", {})
        
        if preferences.get("mood"):
            self.session.exit_mood = preferences["mood"]
            if not self.user.mood_tags:
                self.user.mood_tags = {}
            self.user.mood_tags[today] = preferences["mood"]
            flag_modified(self.user, "mood_tags")
            changes_made = True
        
        if preferences.get("platform"):
            if not self.user.platform_prefs:
                self.user.platform_prefs = {}
            self.user.platform_prefs.setdefault(today, []).append(preferences["platform"])
            flag_modified(self.user, "platform_prefs")
            changes_made = True
        
        if preferences.get("genre"):
            if not self.user.genre_prefs:
                self.user.genre_prefs = {}
            self.user.genre_prefs.setdefault(today, []).append(preferences["genre"])
            flag_modified(self.user, "genre_prefs")
            changes_made = True
        
        # Handle game feedback
        game_feedback = analysis.get("game_feedback", {})
        if game_feedback.get("reaction") == "negative" and self.session.last_recommended_game:
            # Add to rejected games
            if not self.session.rejected_games:
                self.session.rejected_games = []
            self.session.rejected_games.append(self.session.last_recommended_game)
            flag_modified(self.session, "rejected_games")
            changes_made = True
        
        if changes_made:
            self.db.commit()

    async def _generate_response(self, user_input: str, analysis: Dict) -> str:
        """Generate natural, contextual response"""
        
        intent = analysis.get("intent", "casual_chat")
        conversation_stage = analysis.get("conversation_stage", "early")
        emotional_tone = analysis.get("emotional_tone", "neutral")
        
        # Build enhanced context for response generation
        enhanced_context = self.context_enhancer.enhance_conversation_context()
        context = {
            "user_profile": self.user_profile,
            "conversation_memory": self.conversation_memory[-3:],
            "current_analysis": analysis,
            "enhanced_context": enhanced_context,
            "conversation_suggestions": self.context_enhancer.get_conversation_suggestions(),
            "session_stats": {
                "total_interactions": len(self.session.interactions),
                "games_recommended": len(self.session.game_recommendations or []),
                "games_rejected": len(self.session.rejected_games or [])
            }
        }
        
        system_prompt = f"""You are Thrum, a friendly game discovery assistant. You have natural conversations that feel human and engaging.

PERSONALITY:
- Casual, enthusiastic, and genuinely interested in helping
- Use emojis naturally but not excessively  
- Remember what users tell you and reference it
- Ask follow-up questions that show you're listening
- Adapt your energy to match the user's vibe

CURRENT CONTEXT:
{json.dumps(context, indent=2)}

CONVERSATION GUIDELINES:
- If this is early conversation, focus on getting to know them
- If they've shared preferences, acknowledge and build on them
- If they need a game recommendation, be specific and explain why
- If they're giving feedback, respond thoughtfully and adjust
- Keep responses conversational and under 50 words
- Always sound like you're genuinely interested in their gaming journey

RESPONSE STYLE:
- Match their energy level ({emotional_tone})
- Reference previous conversation naturally
- Ask ONE good follow-up question when appropriate
- Be specific about games when recommending
- Show you understand their preferences"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *self.conversation_memory[-4:],
                    {"role": "user", "content": user_input}
                ],
                max_tokens=150,
                temperature=0.8,
                presence_penalty=0.3
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Response generation error: {e}")
            return self._generate_fallback_response(user_input, intent)

    def _generate_fallback_response(self, user_input: str, intent: str) -> str:
        """Generate fallback responses when AI fails"""
        user_input_lower = user_input.lower()
        name = f" {self.user.name}" if self.user.name else ""
        
        if intent == "greeting" or any(word in user_input_lower for word in ['hello', 'hi', 'hey']):
            return f"Hey there{name}! 😊 I'm Thrum, your game buddy. What kind of vibe are you going for today?"
        
        elif intent == "game_request" or "game" in user_input_lower:
            if self.user_profile["preferences"]:
                return "Based on what you've told me, let me find something perfect for your vibe! 🎮"
            else:
                return "I'd love to help! Tell me your current mood - are you feeling chill, hyped, or something else? 🌈"
        
        elif any(word in user_input_lower for word in ['chill', 'relax', 'calm']):
            return "Nice! For a chill vibe, what platform do you usually play on? 🎮"
        
        else:
            return "I'm here to help you discover amazing games! What's your vibe today? 🎲"

async def create_natural_conversation_engine(user, session, db):
    """Factory function to create natural conversation engine"""
    return NaturalConversationEngine(user, session, db)
import openai
import os
from typing import Dict, List
import json

openai.api_key = os.getenv("OPENAI_API_KEY")

class IntelligentAI:
    def __init__(self, user, session):
        self.user = user
        self.session = session
        self.conversation_history = self._build_conversation_history()
        self.user_context = self._build_user_context()
    
    def _build_conversation_history(self) -> List[Dict]:
        """Build conversation history for AI context"""
        history = []
        for interaction in self.session.interactions[-10:]:  # Last 10 messages
            role = "user" if interaction.sender.name == "User" else "assistant"
            history.append({
                "role": role,
                "content": interaction.content
            })
        return history
    
    def _build_user_context(self) -> str:
        """Build comprehensive user context"""
        context_parts = []
        
        if self.user.name:
            context_parts.append(f"User's name: {self.user.name}")
        
        # Platform preferences
        if self.user.platform_prefs:
            platforms = list(self.user.platform_prefs.values())[-1] if self.user.platform_prefs else []
            if platforms:
                context_parts.append(f"Plays on: {', '.join(platforms)}")
        
        # Mood history
        if self.user.mood_tags:
            recent_moods = list(self.user.mood_tags.values())[-3:]
            context_parts.append(f"Recent moods: {', '.join(recent_moods)}")
        
        # Genre preferences
        if self.user.genre_prefs:
            genres = list(self.user.genre_prefs.values())[-1] if self.user.genre_prefs else []
            if genres:
                context_parts.append(f"Likes: {', '.join(genres)}")
        
        # Rejected content
        if self.user.reject_tags:
            rejected = self.user.reject_tags.get("genre", [])
            if rejected:
                context_parts.append(f"Dislikes: {', '.join(rejected)}")
        
        # Session context
        context_parts.append(f"Interaction count: {len(self.session.interactions)}")
        context_parts.append(f"Rejected games: {len(self.session.rejected_games or [])}")
        
        if self.session.last_recommended_game:
            context_parts.append(f"Last recommended: {self.session.last_recommended_game}")
        
        return " | ".join(context_parts)
    
    async def generate_intelligent_response(self, user_input: str) -> str:
        """Generate intelligent, context-aware response"""
        
        system_prompt = f"""You are Thrum, an intelligent game discovery assistant. You have a natural conversation style like a knowledgeable friend who really understands games and people.

CONVERSATION CONTEXT:
{self.user_context}

YOUR PERSONALITY:
- Talk naturally with emojis and casual language
- Ask ONE intelligent question at a time based on what the user just said
- Never repeat questions or use the same phrasing twice
- Be genuinely curious about their gaming preferences
- Make smart connections between what they say and game recommendations
- Remember everything they've told you and reference it naturally

INTELLIGENCE RULES:
- If they mention a game, ask intelligent follow-up questions about what they liked
- If they mention a mood, dig deeper into what that means for gaming
- If they mention a platform, understand the implications for game types
- Connect their responses to build a complete picture of their gaming personality
- Ask questions that show you understand gaming culture and preferences

RESPONSE STYLE:
- Keep responses under 40 words
- Be conversational, not robotic
- Show genuine interest in their gaming journey
- Use their name when you know it
- Reference previous parts of the conversation naturally"""

        messages = [
            {"role": "system", "content": system_prompt},
            *self.conversation_history[-6:],  # Recent conversation context
            {"role": "user", "content": user_input}
        ]
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o",
            messages=messages,
            temperature=0.9,
            max_tokens=80,
            presence_penalty=0.6,
            frequency_penalty=0.8
        )
        
        return response.choices[0].message.content.strip()
    
    async def analyze_user_intent(self, user_input: str) -> Dict:
        """Analyze user intent and extract information intelligently"""
        
        analysis_prompt = f"""Analyze this user message and extract information intelligently:

USER CONTEXT: {self.user_context}
USER MESSAGE: "{user_input}"

Extract and return JSON with:
{{
    "mood": "detected mood (chill, hyped, creative, story-focused, etc.)",
    "platform": "mentioned platform (PC, mobile, Switch, PlayStation, Xbox)",
    "genre_interest": "any genre mentioned or implied",
    "game_mentioned": "specific game they mentioned",
    "preference_revealed": "any preference they revealed",
    "question_type": "what they're asking about",
    "engagement_level": "high/medium/low based on their response length and enthusiasm",
    "next_intelligent_question": "what would be the smartest follow-up question based on their message"
}}

Be intelligent about implications - if they say "I love Zelda" that implies they like adventure/exploration games."""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o",
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        try:
            return json.loads(response.choices[0].message.content.strip())
        except:
            return {}
    
    async def generate_game_recommendation_with_reasoning(self, game_data: Dict) -> str:
        """Generate intelligent game recommendation with human-like reasoning"""
        
        recommendation_prompt = f"""You're recommending a game to someone. Be intelligent about WHY this game fits them.

USER CONTEXT: {self.user_context}
GAME TO RECOMMEND: {game_data.get('title', 'Unknown')}
GAME INFO: {json.dumps(game_data, indent=2)}

Generate a natural recommendation that:
- Shows you understand their gaming personality
- Explains WHY this specific game fits them
- References their previous preferences naturally
- Sounds like a knowledgeable friend's recommendation
- Includes the game title in **bold**
- Keeps it under 50 words
- Uses casual, enthusiastic language

Make it feel personal and intelligent, not generic."""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o",
            messages=[{"role": "user", "content": recommendation_prompt}],
            temperature=0.8,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()

async def create_intelligent_ai(user, session) -> IntelligentAI:
    """Factory function to create intelligent AI instance"""
    return IntelligentAI(user, session)
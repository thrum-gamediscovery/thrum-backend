import openai
import os
from typing import List, Dict
import json

openai.api_key = os.getenv("OPENAI_API_KEY")

class ChatGPTConversationEngine:
    def __init__(self, user, session):
        self.user = user
        self.session = session
        self.conversation_history = self._build_conversation_history()
        self.system_context = self._build_system_context()
    
    def _build_conversation_history(self) -> List[Dict]:
        """Build full conversation history like ChatGPT"""
        history = []
        
        for interaction in self.session.interactions:
            role = "user" if interaction.sender.name == "User" else "assistant"
            history.append({
                "role": role,
                "content": interaction.content
            })
        
        return history
    
    def _build_system_context(self) -> str:
        """Build comprehensive system context"""
        
        user_info = []
        if self.user.name:
            user_info.append(f"User's name: {self.user.name}")
        
        if self.user.mood_tags:
            recent_moods = list(self.user.mood_tags.values())[-3:]
            user_info.append(f"Recent moods: {', '.join(recent_moods)}")
        
        if self.user.genre_prefs:
            genres = []
            for genre_list in self.user.genre_prefs.values():
                genres.extend(genre_list)
            if genres:
                user_info.append(f"Likes: {', '.join(set(genres))}")
        
        if self.user.platform_prefs:
            platforms = []
            for platform_list in self.user.platform_prefs.values():
                platforms.extend(platform_list)
            if platforms:
                user_info.append(f"Plays on: {', '.join(set(platforms))}")
        
        if self.session.rejected_games:
            user_info.append(f"Rejected: {', '.join(self.session.rejected_games[-3:])}")
        
        if self.session.last_recommended_game:
            user_info.append(f"Last recommended: {self.session.last_recommended_game}")
        
        user_context = " | ".join(user_info) if user_info else "New user"
        
        return f"""You are Thrum, a friendly game discovery assistant on WhatsApp. You talk like a real person, not a bot.

PERSONALITY:
- Casual, friendly, enthusiastic about games
- Use emojis naturally but not excessively
- Talk like you're texting a friend
- Remember everything from the conversation
- Be genuinely helpful and excited about games

USER CONTEXT: {user_context}

CONVERSATION STYLE:
- Keep responses natural and conversational
- Reference previous parts of our conversation
- Ask follow-up questions that show you're listening
- Make game recommendations based on what you know about them
- Use their name when you know it
- Be encouraging and positive

RULES:
- Never repeat yourself or ask the same question twice
- Always remember what they've told you
- Build on previous conversation naturally
- Keep responses under 100 words unless they ask for details
- End conversations naturally when they seem satisfied"""
    
    async def generate_response(self, user_input: str) -> str:
        """Generate ChatGPT-style response with full memory"""
        
        # Build messages for ChatGPT
        messages = [
            {"role": "system", "content": self.system_context}
        ]
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o",
                messages=messages,
                temperature=0.8,
                max_tokens=150,
                presence_penalty=0.6,
                frequency_penalty=0.8
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return "Sorry, I'm having trouble connecting right now. Try again in a moment!"
    
    async def update_user_preferences(self, user_input: str):
        """Extract and update user preferences from conversation"""
        
        analysis_prompt = f"""Analyze this message and extract any user preferences:

USER MESSAGE: "{user_input}"
CURRENT CONTEXT: {self.system_context}

Extract any of these if mentioned:
- Mood/feeling (chill, hyped, bored, happy, etc.)
- Game genres (puzzle, action, RPG, etc.)
- Platform (mobile, PC, Switch, etc.)
- Gaming preferences (story-driven, multiplayer, etc.)
- Personal info (name, gaming habits, etc.)

Return JSON format:
{{
    "mood": "detected mood or null",
    "genres": ["list of genres or empty"],
    "platform": "platform or null",
    "name": "name if mentioned or null",
    "story_preference": true/false/null,
    "other_preferences": ["any other gaming preferences"]
}}"""
        
        try:
            analysis_response = await openai.ChatCompletion.acreate(
                model="gpt-4o",
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            analysis = json.loads(analysis_response.choices[0].message.content.strip())
            
            # Update user preferences
            from datetime import datetime
            from sqlalchemy.orm.attributes import flag_modified
            
            today = datetime.utcnow().date().isoformat()
            
            if analysis.get('mood'):
                self.session.exit_mood = analysis['mood']
                self.user.mood_tags[today] = analysis['mood']
                flag_modified(self.user, "mood_tags")
            
            if analysis.get('genres'):
                if not self.user.genre_prefs:
                    self.user.genre_prefs = {}
                self.user.genre_prefs.setdefault(today, []).extend(analysis['genres'])
                flag_modified(self.user, "genre_prefs")
            
            if analysis.get('platform'):
                if not self.user.platform_prefs:
                    self.user.platform_prefs = {}
                self.user.platform_prefs.setdefault(today, []).append(analysis['platform'])
                flag_modified(self.user, "platform_prefs")
            
            if analysis.get('name'):
                self.user.name = analysis['name'].title()
            
            if analysis.get('story_preference') is not None:
                self.user.story_pref = analysis['story_preference']
                
        except Exception as e:
            print(f"Preference extraction error: {e}")
            # Fallback to simple keyword extraction
            await self._simple_preference_extraction(user_input)
    
    async def _simple_preference_extraction(self, user_input: str):
        """Simple fallback preference extraction"""
        from datetime import datetime
        from sqlalchemy.orm.attributes import flag_modified
        
        input_lower = user_input.lower()
        today = datetime.utcnow().date().isoformat()
        
        # Extract mood
        mood_keywords = {
            'chill': ['chill', 'calm', 'relaxed'],
            'hyped': ['hyped', 'excited', 'pumped'],
            'happy': ['happy', 'good', 'great'],
            'bored': ['bored', 'meh', 'nothing']
        }
        
        for mood, keywords in mood_keywords.items():
            if any(keyword in input_lower for keyword in keywords):
                self.session.exit_mood = mood
                self.user.mood_tags[today] = mood
                flag_modified(self.user, "mood_tags")
                break
        
        # Extract platform
        if any(word in input_lower for word in ['mobile', 'phone']):
            if not self.user.platform_prefs:
                self.user.platform_prefs = {}
            self.user.platform_prefs.setdefault(today, []).append('Mobile')
            flag_modified(self.user, "platform_prefs")
        elif any(word in input_lower for word in ['pc', 'computer']):
            if not self.user.platform_prefs:
                self.user.platform_prefs = {}
            self.user.platform_prefs.setdefault(today, []).append('PC')
            flag_modified(self.user, "platform_prefs")

async def create_chatgpt_engine(user, session):
    """Factory function to create ChatGPT conversation engine"""
    return ChatGPTConversationEngine(user, session)
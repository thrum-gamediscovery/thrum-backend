from openai import OpenAI
import os
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm.attributes import flag_modified

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class SmartConversationEngine:
    def __init__(self, user, session, db):
        self.user = user
        self.session = session
        self.db = db

    async def process_conversation(self, user_input: str) -> str:
        """Process conversation using GPT to extract info and respond naturally"""
        
        # Get current context
        context = self._build_context()
        
        # Use GPT to extract information and generate response
        extraction_response = await self._extract_and_respond(user_input, context)
        
        # Update user profile based on GPT extraction
        await self._update_profile_from_gpt(extraction_response.get('extracted_info', {}))
        
        return extraction_response.get('response', "Hey! I'm Thrum, your game buddy. What's on your mind?")

    async def _extract_and_respond(self, user_input: str, context: str) -> Dict:
        """Use GPT to extract information and generate response"""
        
        system_prompt = f"""You are Thrum, a smart game discovery assistant. Your job is to:
1. Extract any user information (name, mood, platform, genre preferences, etc.)
2. Generate a natural, engaging response
3. Remember and reference previous context

Current Context:
{context}

Respond with JSON in this format:
{{
    "response": "Your natural conversational response",
    "extracted_info": {{
        "name": "extracted name or null",
        "mood": "extracted mood or null", 
        "platform": "extracted platform or null",
        "genre": "extracted genre preference or null",
        "sentiment": "positive/neutral/negative",
        "intent": "greeting/question/request/etc"
    }}
}}

Be conversational, friendly, and smart. Extract information naturally without being obvious about it."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            return result
            
        except Exception as e:
            print(f"GPT extraction error: {e}")
            return {
                "response": "I'm here to help you discover amazing games! What's your vibe today?",
                "extracted_info": {}
            }

    async def _update_profile_from_gpt(self, extracted_info: Dict):
        """Update user profile based on GPT extraction"""
        changes_made = False
        
        # Update name
        if extracted_info.get('name') and not self.user.name:
            self.user.name = extracted_info['name']
            changes_made = True
        
        # Update mood
        if extracted_info.get('mood'):
            self.session.exit_mood = extracted_info['mood']
            changes_made = True
        
        # Update platform
        if extracted_info.get('platform'):
            from datetime import datetime
            today = datetime.utcnow().date().isoformat()
            
            if not self.user.platform_prefs:
                self.user.platform_prefs = {}
            self.user.platform_prefs.setdefault(today, []).append(extracted_info['platform'])
            flag_modified(self.user, "platform_prefs")
            
            if not self.session.platform_preference:
                self.session.platform_preference = []
            self.session.platform_preference.append(extracted_info['platform'])
            flag_modified(self.session, "platform_preference")
            changes_made = True
        
        # Update genre
        if extracted_info.get('genre'):
            from datetime import datetime
            today = datetime.utcnow().date().isoformat()
            
            if not self.user.genre_prefs:
                self.user.genre_prefs = {}
            self.user.genre_prefs.setdefault(today, []).append(extracted_info['genre'])
            flag_modified(self.user, "genre_prefs")
            changes_made = True
        
        if changes_made:
            self.db.commit()

    def _build_context(self) -> str:
        """Build current user context"""
        context_parts = []
        
        if self.user.name:
            context_parts.append(f"User name: {self.user.name}")
        
        if self.user.platform_prefs:
            platforms = []
            for platform_list in self.user.platform_prefs.values():
                platforms.extend(platform_list)
            if platforms:
                context_parts.append(f"Known platforms: {', '.join(set(platforms))}")
        
        if self.session.exit_mood:
            context_parts.append(f"Current mood: {self.session.exit_mood}")
        
        if self.user.genre_prefs:
            genres = []
            for genre_list in self.user.genre_prefs.values():
                genres.extend(genre_list)
            if genres:
                context_parts.append(f"Preferred genres: {', '.join(set(genres))}")
        
        if self.session.last_recommended_game:
            context_parts.append(f"Last recommended: {self.session.last_recommended_game}")
        
        return "\n".join(context_parts) if context_parts else "New conversation - no previous context"
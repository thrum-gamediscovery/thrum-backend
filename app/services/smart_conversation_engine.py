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
        print(f"🤖 SmartConversationEngine processing: {user_input}")
        
        context = self._build_context()
        extraction_response = await self._extract_and_respond(user_input, context)
        
        # Update user profile
        await self._update_profile_from_gpt(extraction_response.get('extracted_info', {}))
        
        response = extraction_response.get('response', "Hey! I'm Thrum, your game buddy. What's your vibe? 🎮")
        print(f"✅ Response: {response}")
        return response

    async def _extract_and_respond(self, user_input: str, context: str) -> Dict:
        """Use GPT to extract information and generate response"""
        
        interaction_count = len(self.session.interactions)
        
        system_prompt = f"""You are Thrum, an engaging game discovery assistant. Be conversational and ask ONE smart follow-up question.

Context: {context}
Interaction #{interaction_count + 1}

Rules:
- Extract info naturally
- Ask intelligent follow-ups based on what they say
- Reference previous context when relevant
- Keep responses under 40 words
- Use emojis sparingly but effectively
- Sound like a knowledgeable gaming friend

Respond with JSON:
{{
    "response": "Your engaging response with ONE follow-up question",
    "extracted_info": {{
        "name": "name if mentioned",
        "mood": "mood/vibe if expressed",
        "platform": "platform if mentioned",
        "genre": "genre if mentioned",
        "engagement_level": "high/medium/low"
    }}
}}

Make it feel like a natural conversation, not an interview."""

        try:
            # Add recent conversation history for better context
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add last 3 interactions for context
            for interaction in self.session.interactions[-3:]:
                role = "user" if interaction.sender.name == "User" else "assistant"
                messages.append({"role": role, "content": interaction.content})
            
            messages.append({"role": "user", "content": user_input})
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=120,
                temperature=0.8
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            return result
            
        except Exception as e:
            print(f"GPT extraction error: {e}")
            # Smart fallback based on input
            fallback_response = self._generate_fallback_response(user_input)
            return {
                "response": fallback_response,
                "extracted_info": {}
            }
    
    def _generate_fallback_response(self, user_input: str) -> str:
        """Generate smart fallback when GPT fails"""
        input_lower = user_input.lower()
        
        if any(word in input_lower for word in ['hi', 'hello', 'hey']):
            return "Hey! 👋 I'm Thrum, your game discovery buddy. What's your current vibe?"
        elif any(word in input_lower for word in ['chill', 'relax']):
            return "Chill vibes! 😌 What platform do you usually game on?"
        elif any(word in input_lower for word in ['action', 'intense']):
            return "Action mood! 🔥 PC, console, or mobile gaming?"
        else:
            return "Tell me more! What kind of gaming energy are you feeling? 🎮"

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
        """Build concise user context"""
        context = []
        
        if self.user.name:
            context.append(f"Name: {self.user.name}")
        
        if self.session.exit_mood:
            context.append(f"Mood: {self.session.exit_mood}")
        
        # Recent platforms
        if self.user.platform_prefs:
            recent_platforms = list(self.user.platform_prefs.values())[-1:]
            if recent_platforms:
                platforms = list(set([p for sublist in recent_platforms for p in sublist]))
                context.append(f"Platforms: {', '.join(platforms)}")
        
        # Recent genres
        if self.user.genre_prefs:
            recent_genres = list(self.user.genre_prefs.values())[-1:]
            if recent_genres:
                genres = list(set([g for sublist in recent_genres for g in sublist]))
                context.append(f"Likes: {', '.join(genres)}")
        
        if self.session.last_recommended_game:
            context.append(f"Last rec: {self.session.last_recommended_game}")
        
        interaction_count = len(self.session.interactions)
        context.append(f"Interactions: {interaction_count}")
        
        return " | ".join(context) if context else "New user"
import openai
import os
from typing import Dict, List
import random

openai.api_key = os.getenv("OPENAI_API_KEY")

class InteractiveConversationEngine:
    def __init__(self, user, session):
        self.user = user
        self.session = session
        self.missing_info = self._get_missing_info()
    
    def _get_missing_info(self) -> List[str]:
        """Determine what information we still need to gather"""
        missing = []
        
        # Check mood
        if not self.session.exit_mood and not self.session.entry_mood:
            missing.append("mood")
        
        # Check genre preferences
        if not self.user.genre_prefs or not any(self.user.genre_prefs.values()):
            missing.append("genre")
        
        # Check platform
        if not self.user.platform_prefs and not self.session.platform_preference:
            missing.append("platform")
        
        # Check tone/energy level
        if not self.session.meta_data or not self.session.meta_data.get("user_energy"):
            missing.append("energy")
        
        # Check story preference
        if self.user.story_pref is None:
            missing.append("story_preference")
        
        return missing
    
    async def generate_interactive_response(self, user_input: str) -> str:
        """Generate interactive response that naturally gathers missing info"""
        
        # Determine conversation strategy
        interaction_count = len(self.session.interactions)
        strategy = self._determine_strategy(user_input, interaction_count)
        
        if strategy == "greeting_with_mood_check":
            return await self._generate_greeting_with_mood()
        elif strategy == "genre_discovery":
            return await self._generate_genre_question(user_input)
        elif strategy == "energy_check":
            return await self._generate_energy_question(user_input)
        elif strategy == "platform_discovery":
            return await self._generate_platform_question(user_input)
        elif strategy == "story_preference":
            return await self._generate_story_question(user_input)
        elif strategy == "recommendation_with_followup":
            return await self._generate_recommendation_with_questions(user_input)
        else:
            return await self._generate_natural_followup(user_input)
    
    def _determine_strategy(self, user_input: str, interaction_count: int) -> str:
        """Determine conversation strategy based on context"""
        
        if interaction_count <= 1:
            return "greeting_with_mood_check"
        
        # Check what we're missing and prioritize
        if "mood" in self.missing_info and interaction_count <= 3:
            return "genre_discovery"  # Ask about genre to infer mood
        
        if "energy" in self.missing_info and interaction_count <= 4:
            return "energy_check"
        
        if "platform" in self.missing_info and interaction_count <= 5:
            return "platform_discovery"
        
        if "story_preference" in self.missing_info and interaction_count <= 6:
            return "story_preference"
        
        # If we have enough info, make recommendation but ask follow-up
        if len(self.missing_info) <= 2 or interaction_count >= 4:
            return "recommendation_with_followup"
        
        return "natural_followup"
    
    async def _generate_greeting_with_mood(self) -> str:
        """Generate greeting that naturally asks about mood/vibe"""
        
        greetings = [
            "Hey! 👋 I'm Thrum - I find games that match your exact vibe. What's your gaming mood today? Chill, hyped, or something else?",
            "Hi there! 🎮 I'm your game discovery buddy. Are you feeling like something relaxing, action-packed, or maybe creative today?",
            "Hey! I help people find their perfect game match. What kind of energy are you bringing today - zen mode or ready for chaos? 😄",
            "Hi! 👋 I'm Thrum, your gaming matchmaker. Are you in the mood for something cozy, intense, or totally different today?"
        ]
        
        return random.choice(greetings)
    
    async def _generate_genre_question(self, user_input: str) -> str:
        """Generate natural genre discovery question"""
        
        prompt = f"""User said: "{user_input}"

Generate a natural, enthusiastic response that:
- Acknowledges their mood/vibe
- Asks about their favorite game genres in a fun way
- Gives 3-4 genre options as examples
- Sounds like an excited gaming friend
- Uses emojis and casual language
- Keep it under 200 words

Examples of genres to mention: action, puzzle, RPG, indie, horror, cozy, strategy, adventure"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=80
        )
        
        return response.choices[0].message.content.strip()
    
    async def _generate_energy_question(self, user_input: str) -> str:
        """Generate question about user's energy/tone"""
        
        prompt = f"""User said: "{user_input}"

Generate a natural response that asks about their current energy level/gaming tone:
- Are they feeling high-energy or low-key?
- Want something intense or chill?
- Fast-paced or slow and thoughtful?
- Make it sound like a friend asking
- Use emojis and keep it conversational
- Under 35 words"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=70
        )
        
        return response.choices[0].message.content.strip()
    
    async def _generate_platform_question(self, user_input: str) -> str:
        """Generate natural platform discovery question"""
        
        prompt = f"""User said: "{user_input}"

Generate a casual question about what they play games on:
- PC, mobile, console, etc.
- Make it sound natural and friendly
- Maybe reference how different platforms have different vibes
- Use emojis
- Under 30 words"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=60
        )
        
        return response.choices[0].message.content.strip()
    
    async def _generate_story_question(self, user_input: str) -> str:
        """Generate question about story preference"""
        
        prompt = f"""User said: "{user_input}"

Ask if they prefer games with deep stories or more gameplay-focused games:
- Make it sound natural and conversational
- Give examples of both types
- Sound enthusiastic about both options
- Use emojis
- Under 35 words"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=70
        )
        
        return response.choices[0].message.content.strip()
    
    async def _generate_recommendation_with_questions(self, user_input: str) -> str:
        """Generate game recommendation but continue asking questions"""
        
        from app.services.game_recommend import game_recommendation
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        try:
            game, _ = await game_recommendation(db=db, user=self.user, session=self.session)
            
            if game:
                self.session.last_recommended_game = game["title"]
                
                # Still ask follow-up questions to keep conversation interactive
                followup_questions = [
                    f"Ever played anything like **{game['title']}** before? What did you think?",
                    f"**{game['title']}** has that perfect vibe! Do you usually play solo or with friends?",
                    f"**{game['title']}** should hit the spot! Are you more of a weekend gamer or daily player?",
                    f"**{game['title']}** is calling your name! What's your usual gaming setup like?"
                ]
                
                recommendation = f"Perfect match: **{game['title']}**! {random.choice(followup_questions)}"
                return recommendation
            
        finally:
            db.close()
        
        return await self._generate_natural_followup(user_input)
    
    async def _generate_natural_followup(self, user_input: str) -> str:
        """Generate natural conversation continuation"""
        
        context = f"""
        User: {self.user.name or 'User'}
        Mood: {self.session.exit_mood or 'unknown'}
        Platform: {self.session.platform_preference or 'unknown'}
        Interactions: {len(self.session.interactions)}
        Missing info: {', '.join(self.missing_info)}
        """
        
        prompt = f"""Context: {context}
User said: "{user_input}"

Generate a natural, engaging response that:
- Keeps the conversation flowing
- Shows genuine interest in their gaming preferences
- Asks about something we don't know yet
- Sounds like an enthusiastic gaming friend
- Uses emojis and casual language
- Under 40 words"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=80
        )
        
        return response.choices[0].message.content.strip()

async def create_interactive_engine(user, session):
    """Factory function to create interactive conversation engine"""
    return InteractiveConversationEngine(user, session)
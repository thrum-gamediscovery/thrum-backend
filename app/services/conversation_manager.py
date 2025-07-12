from typing import Optional
from app.services.natural_conversation_engine import create_natural_conversation_engine
from app.services.game_recommend import game_recommendation
from app.services.interaction_tracker import create_interaction_tracker
from app.utils.error_handler import safe_call

class ConversationManager:
    def __init__(self, user, session, db):
        self.user = user
        self.session = session
        self.db = db

    @safe_call("I'm here to help you find amazing games! What's your vibe today? 🎮")
    async def process_conversation(self, user_input: str) -> str:
        """Main conversation processing with natural flow"""
        print(f"🎯 ConversationManager processing: {user_input}")
        
        # Create natural conversation engine and interaction tracker
        engine = await create_natural_conversation_engine(self.user, self.session, self.db)
        tracker = await create_interaction_tracker(self.user, self.session, self.db)
        
        # Check if user needs a game recommendation
        should_recommend = await self._should_recommend_game(user_input, engine)
        
        if should_recommend:
            # Generate game recommendation with natural explanation
            response = await self._generate_game_recommendation(user_input, engine)
        else:
            # Continue natural conversation
            response = await engine.process_message(user_input)
        
        # Log the interaction
        await tracker.log_interaction(user_input, response)
        
        return response

    async def _should_recommend_game(self, user_input: str, engine) -> bool:
        """Determine if user is ready for a game recommendation"""
        user_input_lower = user_input.lower()
        
        # Direct game requests
        if any(phrase in user_input_lower for phrase in [
            'recommend', 'suggest', 'give me a game', 'find me', 'what should i play'
        ]):
            return True
        
        # Check if we have enough info and user seems ready
        has_mood = bool(self.session.exit_mood or self.user.mood_tags)
        has_preferences = bool(
            self.user.genre_prefs or 
            self.user.platform_prefs or 
            self.session.platform_preference
        )
        
        # If we have basic info and user is engaging, offer recommendation
        interaction_count = len(self.session.interactions)
        if interaction_count >= 2 and (has_mood or has_preferences):
            # Check if they're asking follow-up questions or seem ready
            if any(word in user_input_lower for word in [
                'yeah', 'yes', 'sure', 'okay', 'sounds good', 'perfect'
            ]):
                return True
        
        return False

    async def _generate_game_recommendation(self, user_input: str, engine) -> str:
        """Generate game recommendation with natural conversation"""
        try:
            # Get game recommendation
            game_data, confidence = await game_recommendation(
                db=self.db, 
                user=self.user, 
                session=self.session
            )
            
            if not game_data:
                return await engine.process_message(user_input)
            
            # Update session with recommendation
            self.session.last_recommended_game = game_data.get("title")
            self.db.commit()
            
            # Generate natural recommendation response
            return await self._format_recommendation_response(game_data, confidence, engine)
            
        except Exception as e:
            print(f"Recommendation error: {e}")
            return await engine.process_message(user_input)

    async def _format_recommendation_response(self, game_data: dict, confidence: float, engine) -> str:
        """Format game recommendation in natural conversation style"""
        
        # Build context for natural recommendation
        user_context = {
            "name": self.user.name,
            "mood": self.session.exit_mood,
            "preferences": {
                "platforms": self._get_recent_platforms(),
                "genres": self._get_recent_genres()
            },
            "interaction_style": self._get_interaction_style()
        }
        
        recommendation_prompt = f"""Generate a natural game recommendation response as Thrum.

GAME TO RECOMMEND:
Title: {game_data.get('title', 'Unknown')}
Genre: {game_data.get('genre', [])}
Description: {game_data.get('description', '')[:200]}
Platforms: {game_data.get('platforms', [])}
Game Vibes: {game_data.get('game_vibes', [])}

USER CONTEXT:
{user_context}

STYLE GUIDELINES:
- Sound excited about this specific match
- Explain WHY this game fits their vibe
- Reference their preferences naturally
- Keep it conversational and under 60 words
- Use **bold** for the game title
- Include relevant emoji
- End with a natural follow-up question

Make it feel like a friend who really knows games is recommending something perfect for them."""

        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": recommendation_prompt}],
                max_tokens=120,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Recommendation formatting error: {e}")
            # Fallback to simple recommendation
            title = game_data.get('title', 'this game')
            mood = self.session.exit_mood or 'your vibe'
            return f"Perfect! I found **{title}** for you - it totally matches your {mood} mood! 🎮 What do you think?"

    def _get_recent_platforms(self) -> list:
        """Get user's recent platform preferences"""
        if not self.user.platform_prefs:
            return []
        recent_platforms = []
        for platform_list in list(self.user.platform_prefs.values())[-2:]:
            recent_platforms.extend(platform_list)
        return list(set(recent_platforms))

    def _get_recent_genres(self) -> list:
        """Get user's recent genre preferences"""
        if not self.user.genre_prefs:
            return []
        recent_genres = []
        for genre_list in list(self.user.genre_prefs.values())[-2:]:
            recent_genres.extend(genre_list)
        return list(set(recent_genres))

    def _get_interaction_style(self) -> str:
        """Determine user's interaction style based on conversation"""
        interaction_count = len(self.session.interactions)
        
        if interaction_count <= 2:
            return "new_user"
        elif interaction_count <= 5:
            return "getting_comfortable"
        else:
            return "engaged"

async def create_conversation_manager(user, session, db):
    """Factory function to create conversation manager"""
    return ConversationManager(user, session, db)
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
        """Enhanced conversation processing with interactive elements"""
        print(f"🎯 ConversationManager processing: {user_input}")
        
        # Create engines
        engine = await create_natural_conversation_engine(self.user, self.session, self.db)
        tracker = await create_interaction_tracker(self.user, self.session, self.db)
        
        # Add conversation momentum tracking
        momentum = self._assess_conversation_momentum()
        
        # Check for recommendation readiness
        should_recommend = await self._should_recommend_game(user_input, engine)
        
        if should_recommend:
            response = await self._generate_game_recommendation(user_input, engine)
        else:
            response = await engine.process_message(user_input)
            
            # Add engagement boosters for low momentum
            if momentum == "low" and len(self.session.interactions) > 2:
                response += "\n\nI'm really curious about your gaming style! What's a game that completely hooked you recently? 🎯"
        
        # Log interaction
        await tracker.log_interaction(user_input, response)
        
        return response
    
    def _assess_conversation_momentum(self) -> str:
        """Assess conversation momentum for engagement"""
        if len(self.session.interactions) < 2:
            return "starting"
        
        recent_user_msgs = [i.content for i in self.session.interactions[-3:] if i.sender.name == "User"]
        if not recent_user_msgs:
            return "stalled"
        
        avg_length = sum(len(msg) for msg in recent_user_msgs) / len(recent_user_msgs)
        return "high" if avg_length > 20 else "low" if avg_length < 8 else "medium"

    async def _should_recommend_game(self, user_input: str, engine) -> bool:
        """Intelligently determine if user is ready for a game recommendation"""
        user_input_lower = user_input.lower()
        
        # Direct requests
        if any(phrase in user_input_lower for phrase in [
            'recommend', 'suggest', 'give me a game', 'find me', 'what should i play', 'show me'
        ]):
            return True
        
        # Check readiness signals
        readiness_signals = ['yeah', 'yes', 'sure', 'okay', 'sounds good', 'perfect', 'let\'s go', 'do it']
        if any(signal in user_input_lower for signal in readiness_signals):
            return True
        
        # Progressive recommendation logic
        has_mood = bool(self.session.exit_mood or self.user.mood_tags)
        has_preferences = bool(self.user.genre_prefs or self.user.platform_prefs or self.session.platform_preference)
        interaction_count = len(self.session.interactions)
        
        # Recommend after gathering basic info
        if interaction_count >= 3 and has_mood:
            return True
        
        if interaction_count >= 4 and has_preferences:
            return True
        
        # User seems engaged and we have some info
        if interaction_count >= 2 and len(user_input) > 15 and (has_mood or has_preferences):
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
        """Format game recommendation with interactive elements"""
        
        title = game_data.get('title', 'this game')
        mood = self.session.exit_mood or 'your vibe'
        platforms = game_data.get('platforms', [])
        
        # Create engaging recommendation with follow-up options
        base_rec = f"Perfect match! **{title}** totally captures your {mood} mood! 🎯"
        
        # Add platform context if relevant
        user_platforms = self._get_recent_platforms()
        if user_platforms and any(p in platforms for p in user_platforms):
            base_rec += f" Plus it's on {user_platforms[0]}!"
        
        # Interactive follow-ups based on confidence
        if confidence > 0.8:
            follow_ups = [
                "This is going to be perfect for you! Want to know why I'm so confident?",
                "I'm really excited about this match! Should I tell you what makes it special?",
                "This feels like it was made for your current vibe! Interested?"
            ]
        else:
            follow_ups = [
                "What do you think? Want me to explain why this fits?",
                "Sound interesting? I can tell you more about what makes it great!",
                "Does this sound like your kind of game?"
            ]
        
        import random
        return f"{base_rec} {random.choice(follow_ups)}"

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
        """Determine user's interaction style for better responses"""
        interaction_count = len(self.session.interactions)
        user_messages = [i.content for i in self.session.interactions if i.sender.name == "User"]
        
        if not user_messages:
            return "new_user"
        
        avg_length = sum(len(msg) for msg in user_messages) / len(user_messages)
        question_count = sum(msg.count('?') for msg in user_messages)
        
        if avg_length > 30 and question_count > 1:
            return "detailed_curious"
        elif avg_length < 10:
            return "brief_casual"
        elif interaction_count > 5:
            return "engaged"
        else:
            return "getting_comfortable"

    def add_interactive_elements(self, response: str, user_input: str) -> str:
        """Add interactive elements to responses"""
        interaction_count = len(self.session.interactions)
        
        # Add contextual questions for engagement
        if interaction_count == 1 and "mood" not in response.lower():
            response += "\n\nQuick question - what's your current gaming mood? 🎮"
        elif interaction_count == 3 and not self.user.platform_prefs:
            response += "\n\nBtw, what do you usually play on? 📱💻🎮"
        
        return response

async def create_conversation_manager(user, session, db):
    """Factory function to create conversation manager"""
    return ConversationManager(user, session, db)
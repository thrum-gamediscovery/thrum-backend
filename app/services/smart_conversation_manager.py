from app.services.intelligent_ai_engine import create_intelligent_ai
from app.services.learning_engine import UserLearningProfile
import json

class SmartConversationManager:
    """Manages intelligent conversation flow based on user context and AI analysis"""
    
    def __init__(self, user, session, db):
        self.user = user
        self.session = session
        self.db = db
        self.profile = UserLearningProfile(user, session)
    
    async def process_user_message(self, user_input: str) -> str:
        """Process user message intelligently and generate appropriate response"""
        
        # Create intelligent AI instance
        ai = await create_intelligent_ai(self.user, self.session)
        
        # Analyze user intent and extract information
        analysis = await ai.analyze_user_intent(user_input)
        
        # Update user profile based on analysis
        await self._update_profile_from_analysis(analysis)
        
        # Determine conversation flow intelligently
        response_type = self._determine_response_type(analysis, user_input)
        
        # Generate appropriate response
        if response_type == "game_recommendation":
            return await self._generate_game_recommendation(ai, analysis)
        elif response_type == "intelligent_question":
            return await ai.generate_intelligent_response(user_input)
        elif response_type == "conclusion":
            return await self._generate_conclusion(ai, user_input)
        else:
            return await ai.generate_intelligent_response(user_input)
    
    async def _update_profile_from_analysis(self, analysis: dict):
        """Update user profile based on AI analysis"""
        
        if analysis.get('mood'):
            self.profile.update_preferences(mood=analysis['mood'])
        
        if analysis.get('platform'):
            self.profile.update_preferences(platform=analysis['platform'])
        
        if analysis.get('preference_revealed'):
            # Store any revealed preference in session metadata
            self.session.meta_data = self.session.meta_data or {}
            self.session.meta_data['latest_preference'] = analysis['preference_revealed']
        
        self.db.commit()
    
    def _determine_response_type(self, analysis: dict, user_input: str) -> str:
        """Intelligently determine what type of response to generate"""
        
        # Check for conclusion signals
        conclusion_signals = ["thanks", "thank you", "perfect", "sounds good", "got it", "awesome"]
        if any(signal in user_input.lower() for signal in conclusion_signals):
            return "conclusion"
        
        # Check if we have enough info for recommendation
        interaction_count = len(self.session.interactions)
        engagement = analysis.get('engagement_level', 'medium')
        
        # If user is highly engaged and we have some preferences, consider recommending
        if (engagement == 'high' and interaction_count >= 3) or interaction_count >= 6:
            return "game_recommendation"
        
        # If user mentioned a specific game, ask intelligent follow-up
        if analysis.get('game_mentioned'):
            return "intelligent_question"
        
        # Default to intelligent conversation
        return "intelligent_question"
    
    async def _generate_game_recommendation(self, ai, analysis: dict) -> str:
        """Generate intelligent game recommendation"""
        from app.services.game_recommend import game_recommendation
        
        # Get game recommendation
        game, _ = await game_recommendation(db=self.db, user=self.user, session=self.session)
        
        if game:
            self.session.last_recommended_game = game["title"]
            
            game_data = {
                "title": game["title"],
                "description": game.get("description", ""),
                "genre": game.get("genre", []),
                "platforms": game.get("platforms", []),
                "game_vibes": game.get("game_vibes", [])
            }
            
            # Generate intelligent recommendation with reasoning
            return await ai.generate_game_recommendation_with_reasoning(game_data)
        
        return await ai.generate_intelligent_response("Let me find something perfect for you.")
    
    async def _generate_conclusion(self, ai, user_input: str) -> str:
        """Generate natural conversation conclusion"""
        
        conclusion_prompt = f"""Generate a natural, friendly conclusion to the conversation.

USER CONTEXT: {ai.user_context}
USER MESSAGE: "{user_input}"
LAST RECOMMENDED GAME: {self.session.last_recommended_game}

Generate a warm, natural conclusion that:
- Thanks them for the conversation
- Confirms their game choice if they accepted a recommendation
- Offers future help in a casual way
- Sounds like a friend wrapping up a conversation
- Keep it under 30 words
- Use emojis naturally"""
        
        import openai
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "user", "content": conclusion_prompt}],
            temperature=0.8,
            max_tokens=60
        )
        
        return response.choices[0].message.content.strip()

async def create_smart_conversation_manager(user, session, db):
    """Factory function to create smart conversation manager"""
    return SmartConversationManager(user, session, db)
import openai
import os
from typing import Dict, List
import random

openai.api_key = os.getenv("OPENAI_API_KEY")

class InteractiveConversationEngine:
    def __init__(self, user, session):
        self.user = user
        self.session = session
        self.conversation_stage = self._get_conversation_stage()
        self.context_memory = self._build_context_memory()
    
    def _build_context_memory(self) -> Dict:
        """Build conversation context memory for better responses"""
        memory = {
            "mentioned_games": [],
            "expressed_preferences": [],
            "rejected_suggestions": [],
            "enthusiasm_level": "medium",
            "communication_style": "casual"
        }
        
        # Analyze conversation history
        for interaction in self.session.interactions:
            if interaction.sender.name == "User":
                content = interaction.content.lower()
                
                # Track mentioned games
                # This could be enhanced with NLP to detect game names
                
                # Track enthusiasm
                if any(indicator in content for indicator in ['!', 'awesome', 'love', 'amazing']):
                    memory["enthusiasm_level"] = "high"
                elif any(indicator in content for indicator in ['meh', 'okay', 'fine']):
                    memory["enthusiasm_level"] = "low"
        
        return memory
    
    def _get_conversation_stage(self) -> str:
        """Intelligently determine conversation stage with better context awareness"""
        interaction_count = len(self.session.interactions)
        
        # Check for explicit user requests first
        if self.session.interactions:
            last_input = self.session.interactions[-1].content.lower()
            
            if any(phrase in last_input for phrase in ["how does it work", "how do you work", "explain"]):
                return "explanation"
            
            if any(phrase in last_input for phrase in ["recommend", "suggest", "find me", "give me a game"]):
                return "recommendation"
            
            if any(phrase in last_input for phrase in ["bye", "thanks", "that's all", "done"]):
                return "conclusion"
        
        # Progressive conversation flow
        if interaction_count <= 1:
            return "greeting"
        
        # Check if we have enough info for recommendation
        has_mood = bool(self.session.exit_mood or self.session.entry_mood)
        has_genre_info = bool(self.user.genre_prefs and any(self.user.genre_prefs.values()))
        has_platform_info = bool(self.user.platform_prefs or self.session.platform_preference)
        
        # Mood discovery is priority
        if not has_mood:
            return "mood_discovery"
        
        # If we have mood but need more context
        if has_mood and not has_genre_info and interaction_count < 4:
            return "genre_discovery"
        
        # Energy/preference refinement
        if has_mood and (not self.session.meta_data or not self.session.meta_data.get("user_energy")):
            return "energy_discovery"
        
        # Platform discovery if needed
        if not has_platform_info and interaction_count < 6:
            return "platform_discovery"
        
        # Ready for recommendation if we have basic info
        if has_mood and (has_genre_info or has_platform_info or interaction_count >= 3):
            if not self.session.last_recommended_game:
                return "recommendation"
        
        # Name collection for personalization
        if not self.user.name and interaction_count > 3:
            return "name_collection"
        
        # Default to conclusion
        return "conclusion"
    
    async def generate_interactive_response(self, user_input: str) -> str:
        """Generate intelligent response based on conversation stage and context"""
        
        stage = self.conversation_stage
        
        # Add conversation momentum tracking
        momentum = self._assess_conversation_momentum()
        
        if stage == "greeting":
            return await self._generate_greeting(user_input)
        elif stage == "explanation":
            return await self._generate_explanation(user_input)
        elif stage == "mood_discovery":
            response = await self._generate_mood_question(user_input)
            # Add engagement booster if momentum is low
            if momentum == "low" and len(self.session.interactions) > 2:
                response += "\n\nI'm really curious about your gaming style - help me understand what makes a game click for you! 🎯"
            return response
        elif stage == "genre_discovery":
            return await self._generate_genre_question(user_input)
        elif stage == "energy_discovery":
            return await self._generate_energy_question(user_input)
        elif stage == "platform_discovery":
            return await self._generate_platform_question(user_input)
        elif stage == "recommendation":
            return await self._generate_recommendation(user_input)
        elif stage == "name_collection":
            return await self._generate_name_question(user_input)
        else:
            return await self._generate_conclusion(user_input)
    
    def _assess_conversation_momentum(self) -> str:
        """Assess current conversation momentum"""
        if not self.session.interactions:
            return "starting"
        
        recent_interactions = self.session.interactions[-3:]
        user_responses = [i for i in recent_interactions if i.sender.name == "User"]
        
        if len(user_responses) == 0:
            return "stalled"
        
        avg_length = sum(len(r.content) for r in user_responses) / len(user_responses)
        
        if avg_length > 25 and len(user_responses) >= 2:
            return "high"
        elif avg_length > 10:
            return "medium"
        else:
            return "low"
    
    async def _generate_greeting(self, user_input: str) -> str:
        """Generate dynamic, engaging greeting"""
        
        # Analyze user's greeting style
        input_lower = user_input.lower()
        is_casual = any(word in input_lower for word in ['hey', 'sup', 'yo', 'what\'s up'])
        is_formal = any(word in input_lower for word in ['hello', 'good morning', 'good evening'])
        
        if is_casual:
            greetings = [
                f"{user_input} 👋\nYo! I'm Thrum, your game discovery wingman. What's the vibe today - looking for something specific or just seeing what's out there?",
                f"{user_input}! 😎\nWhat's good! I'm Thrum and I'm basically a human game recommendation engine. What kind of energy are you bringing today?",
                f"{user_input} 👋\nAyy! I'm Thrum - I match people with games that actually fit their mood, not just whatever's trending. What's calling to you?"
            ]
        elif is_formal:
            greetings = [
                f"{user_input}! 😊\nI'm Thrum, your personal game curator. I specialize in finding games that match your current mood and preferences. What brings you here today?",
                f"{user_input}! 👋\nWelcome! I'm Thrum, and I help people discover games that truly resonate with how they're feeling. What's your current gaming mood?",
                f"{user_input}! ✨\nI'm Thrum, your game discovery companion. I believe the best recommendations come from understanding your actual vibe. How are you feeling today?"
            ]
        else:
            greetings = [
                f"{user_input} 👋\nHey there! I'm Thrum, and I'm all about finding games that actually match your mood. Are you looking for something specific or just exploring?",
                f"{user_input}! 🎮\nI'm Thrum - think of me as your gaming mood translator. I help find games that fit exactly how you're feeling. What's your vibe?",
                f"{user_input} 😊\nI'm Thrum! I specialize in mood-based game recommendations because the best games are the ones that match your energy. What's going on with you today?"
            ]
        
        return random.choice(greetings)
    
    async def _generate_mood_question(self, user_input: str) -> str:
        """Ask about current mood/vibe with intelligent context"""
        
        # Check if user already hinted at their mood
        input_lower = user_input.lower()
        mood_hints = {
            'tired': 'sounds like you might be in a chill mood',
            'stressed': 'sounds like you might need something relaxing',
            'bored': 'sounds like you need something engaging',
            'excited': 'sounds like you\'ve got some energy to burn'
        }
        
        detected_mood = None
        for mood, hint in mood_hints.items():
            if mood in input_lower:
                detected_mood = hint
                break
        
        if detected_mood:
            mood_questions = [
                f"I hear you! {detected_mood.title()} - am I reading that right? Or is there more to it? 🤔",
                f"Gotcha! {detected_mood.title()} - but tell me more. What would actually hit the spot right now? 🎯",
                f"Interesting! {detected_mood.title()} - but I want to make sure I get this right. What's your ideal vibe? 😊"
            ]
        else:
            # Check user's communication style for appropriate response
            if len(user_input) > 30:  # Detailed user
                mood_questions = [
                    "Love the detail! Now help me understand your current headspace - are you feeling more contemplative, energetic, creative, or something completely different? 🌈",
                    "Perfect! So what's your emotional landscape right now? Chill and reflective, pumped and ready for action, or maybe somewhere in between? 🧠",
                    "Great context! Now for the key question - what kind of energy do you want to either match or shift to? ✨"
                ]
            else:  # Brief user
                mood_questions = [
                    "Nice! 😎 What's the vibe - chill, hyped, creative, or something else?",
                    "Sweet! 🔥 How you feeling - zen mode, action mode, or totally different?",
                    "Perfect! 👌 What's your energy - relaxed, pumped, or somewhere else?"
                ]
        
        return random.choice(mood_questions)
    
    async def _generate_explanation(self, user_input: str) -> str:
        """Explain how Thrum works"""
        
        explanations = [
            "Pretty simple.\nYou drop your mood. Then a genre or game type you're into.\nAnd I dig up something that fits — vibe first, not ads or whatever.\nWanna try it?",
            "Easy process.\nTell me how you're feeling today. Then what kind of games you like.\nI find something that matches your energy, not just trending stuff.\nReady to give it a shot?",
            "Super straightforward.\nShare your current vibe. Then your game preferences.\nI match based on your actual mood, not just popular games.\nWant to test it out?",
            "Nothing complicated.\nYou tell me your mood and game style.\nI find something that actually fits how you're feeling right now.\nDown to try?"
        ]
        
        return random.choice(explanations)
    
    async def _generate_genre_question(self, user_input: str) -> str:
        """Ask about game preferences with intelligent mood connection"""
        
        mood = self.session.exit_mood or "good"
        
        # Create mood-specific genre suggestions
        mood_genre_connections = {
            'chill': 'cozy games, puzzles, or maybe something creative',
            'hyped': 'action games, competitive stuff, or high-energy adventures',
            'creative': 'building games, sandbox experiences, or artistic stuff',
            'story': 'narrative-heavy games, RPGs, or emotional journeys',
            'bored': 'something completely different from your usual',
            'stressed': 'relaxing games, meditative experiences, or comfort games'
        }
        
        suggested_genres = mood_genre_connections.get(mood, 'your favorite types of games')
        
        # Analyze user's previous response for personalization
        if 'creative' in user_input.lower():
            genre_questions = [
                f"{mood.title()} and creative - that's a powerful combo! 🎨\nAre you thinking building/crafting games, or more like artistic expression stuff?",
                f"Love that {mood} creative energy! ✨\nWhat draws you more - making things, solving puzzles, or expressing yourself?"
            ]
        elif 'action' in user_input.lower():
            genre_questions = [
                f"{mood.title()} with some action - I can work with that! 🔥\nFast-paced combat, strategic action, or more like adventure action?",
                f"That {mood} action vibe is solid! 🎯\nWhat gets your blood pumping - competition, exploration, or pure adrenaline?"
            ]
        else:
            genre_questions = [
                f"{mood.title()} vibes are perfect! ✨\nBased on that energy, I'm thinking {suggested_genres} - what resonates?",
                f"Love that {mood} energy! 🙌\nWhat usually captures that mood for you - {suggested_genres}?",
                f"{mood.title()} mood is great to work with! 👍\nI'm picturing {suggested_genres} - sound right?",
                f"That {mood} feeling is so specific! 🎯\nWhat kind of games usually match that vibe for you?"
            ]
        
        return random.choice(genre_questions)
    
    async def _generate_energy_question(self, user_input: str) -> str:
        """Ask about game pace/energy preference"""
        
        genre = "puzzle" if self.user.genre_prefs else "games"
        
        energy_questions = [
            f"{genre.title()} gang! 🧩 Respect.\nFast-paced ones or more of the slow, thinky ones?",
            f"Nice choice with {genre}! 🎮\nYou like the quick ones or more take-your-time style?",
            f"{genre.title()} player, love it! ⭐\nHigh-energy or more of the calm approach?",
            f"Good taste in {genre}! 👌\nQuick and snappy or slow and thoughtful?"
        ]
        
        return random.choice(energy_questions)
    
    async def _generate_platform_question(self, user_input: str) -> str:
        """Ask about gaming platform"""
        
        platform_questions = [
            "Got it. You're a calm puzzle enjoyer.\nWhere do you usually play?",
            "Nice, slow and thoughtful is the way 🧠\nWhat's your usual setup?",
            "Perfect vibe! 😌\nWhere do you game mostly?",
            "Love that approach! 🎯\nWhat do you play on usually?"
        ]
        
        return random.choice(platform_questions)
    
    async def _generate_recommendation(self, user_input: str) -> str:
        """Generate intelligent, personalized game recommendation"""
        
        from app.services.game_recommend import game_recommendation
        from app.db.session import SessionLocal
        from app.services.adaptive_responses import create_adaptive_response_system
        
        db = SessionLocal()
        try:
            game, confidence = await game_recommendation(db=db, user=self.user, session=self.session)
            
            if game:
                self.session.last_recommended_game = game["title"]
                
                # Use adaptive response system for personalized recommendation
                adaptive_system = create_adaptive_response_system(self.user, self.session)
                recommendation = adaptive_system.get_adaptive_recommendation_style(game, confidence)
                
                # Add contextual follow-up based on user's communication style
                if len(user_input) > 30:  # Detailed user
                    follow_ups = [
                        "\nWhat aspects of this sound most interesting to you?",
                        "\nI'd love to hear your thoughts on this match!",
                        "\nDoes this align with what you were envisioning?"
                    ]
                else:  # Brief user
                    follow_ups = [
                        "\nSound good?",
                        "\nWhat do you think?",
                        "\nInterested?"
                    ]
                
                return recommendation + random.choice(follow_ups)
            else:
                # No game found - ask for more info
                clarification_questions = [
                    "Hmm, let me get a bit more specific with you. What's a game you absolutely loved? That'll help me nail your taste! 🎯",
                    "I want to find you something perfect! What's your ideal gaming session like - long and immersive or quick and satisfying? 🤔",
                    "Let me dig deeper! What's the last game that made you lose track of time? ⏰"
                ]
                return random.choice(clarification_questions)
            
        finally:
            db.close()
    
    async def _generate_name_question(self, user_input: str) -> str:
        """Ask for user's name"""
        
        name_questions = [
            "Anytime 🙂\nOh btw — what's your name?",
            "No problem! 😊\nWhat should I call you?",
            "You got it! 👍\nWhat's your name btw?",
            "Happy to help! ✨\nWhat's your name?"
        ]
        
        return random.choice(name_questions)
    
    async def _generate_conclusion(self, user_input: str) -> str:
        """Generate personalized conversation conclusion"""
        
        name = self.user.name or "friend"
        interaction_count = len(self.session.interactions)
        
        # Personalize based on conversation quality
        if interaction_count > 8:  # Long, engaged conversation
            conclusions = [
                f"This was such a great conversation, {name}! 😊 I really enjoyed getting to know your gaming style.\nFeel free to come back anytime you need another recommendation - I'll remember our chat!\nWant to share this with friends who might need game help too?",
                f"I had a blast figuring out your gaming personality, {name}! ✨\nYou've got great taste, and I hope you love what we found.\nIf any of your friends need game recs, send them my way!",
                f"Thanks for such an engaging conversation, {name}! 🎯\nI love when I get to really understand someone's gaming vibe.\nCome back anytime, and feel free to tell other gamers about this!"
            ]
        elif self.session.last_recommended_game:  # Successful recommendation
            conclusions = [
                f"Perfect, {name}! 🎮 I'm excited for you to try **{self.session.last_recommended_game}**.\nLet me know how it goes, and come back when you need your next gaming fix!\nWant to share this with friends?",
                f"Awesome choice, {name}! 🚀 I think **{self.session.last_recommended_game}** is going to be exactly what you needed.\nI'm always here when you're ready for another recommendation!\nFeel free to spread the word!",
                f"Great decision, {name}! 👍 **{self.session.last_recommended_game}** should hit the spot perfectly.\nCome back anytime you need another game buddy!\nWant a message to share with gaming friends?"
            ]
        else:  # General conclusion
            conclusions = [
                f"Thanks for chatting, {name}! 😊 Even if we didn't find the perfect game today, I learned about your style.\nCome back anytime - I'll remember our conversation!\nWant to tell friends about this?",
                f"Good talking with you, {name}! 👋 I'm always here when you need game recommendations.\nFeel free to share this with anyone who needs gaming help!",
                f"See you around, {name}! ✌️ Thanks for letting me get to know your gaming preferences.\nSpread the word if this was helpful!"
            ]
        
        return random.choice(conclusions)

async def create_interactive_engine(user, session):
    """Factory function to create interactive conversation engine"""
    return InteractiveConversationEngine(user, session)
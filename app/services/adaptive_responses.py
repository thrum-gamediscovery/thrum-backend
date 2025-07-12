from typing import Dict, List
import random
from datetime import datetime, timedelta

class AdaptiveResponseSystem:
    def __init__(self, user, session):
        self.user = user
        self.session = session
        self.interaction_count = len(self.session.interactions)
        self.user_style = self._analyze_user_style()
        self.conversation_momentum = self._assess_conversation_momentum()
    
    def _assess_conversation_momentum(self) -> str:
        """Assess the current momentum of the conversation"""
        if not self.session.interactions:
            return "starting"
        
        recent_interactions = self.session.interactions[-3:]
        user_responses = [i for i in recent_interactions if i.sender.name == "User"]
        
        if len(user_responses) == 0:
            return "stalled"
        
        # Check response times and engagement
        avg_response_length = sum(len(r.content) for r in user_responses) / len(user_responses)
        
        if avg_response_length > 30 and len(user_responses) >= 2:
            return "high"
        elif avg_response_length > 15:
            return "medium"
        else:
            return "low"

    def _analyze_user_style(self) -> Dict:
        """Analyze user's communication style for better adaptation"""
        if not self.session.interactions:
            return {"type": "new", "detail_level": "medium", "enthusiasm": "medium"}
        
        user_messages = [i.content for i in self.session.interactions if i.sender.name == "User"]
        if not user_messages:
            return {"type": "new", "detail_level": "medium", "enthusiasm": "medium"}
        
        avg_length = sum(len(msg) for msg in user_messages) / len(user_messages)
        enthusiasm_indicators = sum(msg.count('!') + msg.count('😊') + msg.count('🎮') for msg in user_messages)
        question_count = sum(msg.count('?') for msg in user_messages)
        
        return {
            "type": "returning" if self.interaction_count > 3 else "new",
            "detail_level": "high" if avg_length > 40 else "low" if avg_length < 15 else "medium",
            "enthusiasm": "high" if enthusiasm_indicators > len(user_messages) else "low" if enthusiasm_indicators == 0 else "medium",
            "curiosity": "high" if question_count > len(user_messages) * 0.3 else "medium"
        }

    def get_adaptive_greeting(self) -> str:
        """Get greeting adapted to user's interaction history and style"""
        name = f" {self.user.name}" if self.user.name else ""
        time_context = self._get_time_context()
        
        if self.interaction_count == 0:
            # First time user - more engaging intro
            greetings = [
                f"Hey there! 👋 I'm Thrum, your personal game matchmaker. What's got you in the mood to game today?",
                f"Hi! 😊 I'm Thrum - think of me as your gaming wingman. What kind of vibe are you chasing?",
                f"Hello! 🎮 I'm Thrum, and I live for finding people their perfect game. What's your energy like right now?"
            ]
        elif self.interaction_count < 5:
            # Getting comfortable - reference previous interactions
            last_mood = self.session.exit_mood
            if last_mood:
                greetings = [
                    f"Hey{name}! 👋 Still feeling that {last_mood} vibe, or has your mood shifted?",
                    f"What's up{name}! 😊 Ready for another game hunt? How's your energy today?",
                    f"Hi{name}! 🎮 Back for more discoveries? What's calling to you right now?"
                ]
            else:
                greetings = [
                    f"Hey{name}! 👋 Good to see you again! What's your gaming mood today?",
                    f"Hi{name}! 😊 Ready to find something awesome? What's your vibe?",
                    f"What's up{name}! 🎮 Let's discover your next favorite game!"
                ]
        else:
            # Established relationship - more personalized
            recent_genres = self._get_recent_preferences()
            greetings = [
                f"Hey{name}! 🎯 {time_context} What kind of gaming adventure are we hunting today?",
                f"What's good{name}! 😄 Ready to dive into something new? What's your current mood?",
                f"Hi{name}! 🚀 {time_context} Let's find you something that hits just right!"
            ]
            
            if recent_genres:
                greetings.append(f"Hey{name}! Still into {recent_genres} or feeling something different today? 🎮")
        
        # Add momentum-based greeting modification
        greeting = random.choice(greetings)
        
        if self.conversation_momentum == "high" and self.interaction_count > 2:
            greeting += " I love how engaged you are with finding the perfect game!"
        elif self.conversation_momentum == "stalled":
            greeting = f"Hey{name}! 👋 Let's get back to finding you something amazing to play! What's your current mood?"
        
        return greeting

    def get_adaptive_follow_up(self, user_response_type: str, context: Dict = None) -> str:
        """Get intelligent follow-up questions adapted to user's style and context"""
        context = context or {}
        
        # Dynamic follow-ups based on user style and conversation flow
        if self.user_style["detail_level"] == "high":
            follow_ups = {
                "mood_shared": [
                    "That's such a specific vibe! What kind of gaming experience usually captures that feeling for you?",
                    "I love that energy! When you're in that mood, do you lean toward story-heavy games or more action-focused ones?",
                    "Perfect! That mood makes me think of a few different directions - are you feeling more solo adventure or maybe something social?"
                ],
                "genre_mentioned": [
                    "Excellent taste! What's the last game in that genre that really hooked you? I want to understand your specific style.",
                    "Nice choice! Are you looking for something that pushes the boundaries of that genre, or more of a polished classic experience?",
                    "Great direction! What draws you to that genre - is it the mechanics, the storytelling, or the overall atmosphere?"
                ],
                "platform_mentioned": [
                    "Smart choice for that platform! Are you looking for something you can dive deep into, or more pick-up-and-play?",
                    "Perfect! That platform has some amazing options. What's your typical gaming session like - long immersive sessions or shorter bursts?"
                ]
            }
        else:  # Brief communicator - keep it snappy
            follow_ups = {
                "mood_shared": [
                    "Nice! Quick question - solo adventure or multiplayer fun?",
                    "Cool vibe! Story-focused or action-packed?",
                    "Sweet! What platform gets the most love?"
                ],
                "genre_mentioned": [
                    "Perfect! What's your go-to platform?",
                    "Got it! Any recent favorites in that genre?",
                    "Nice! Looking for something new or a classic?"
                ],
                "platform_mentioned": [
                    "Solid choice! What genre's calling to you?",
                    "Perfect! Quick sessions or deep dives?"
                ]
            }
        
        # Add contextual intelligence
        if context.get("time_sensitive"):
            follow_ups["mood_shared"].append("Got it! Since you're looking for something now, what's your usual go-to platform?")
        
        if context.get("returning_user") and self.session.exit_mood:
            follow_ups["mood_shared"].append(f"Interesting shift from your {self.session.exit_mood} mood last time! What changed?")
        
        return random.choice(follow_ups.get(user_response_type, ["Tell me more! What's got you excited? 😊"]))

    def get_adaptive_recommendation_style(self, game_data: Dict, confidence: float = 0.8) -> str:
        """Generate dynamic, personalized recommendation based on user style and game data"""
        title = game_data.get('title', 'this game')
        genre = game_data.get('genre', ['game'])
        platforms = game_data.get('platforms', [])
        
        # Build personalized reasoning
        reasoning = self._get_intelligent_reasoning(game_data, confidence)
        
        if self.user_style["enthusiasm"] == "high":
            # High-energy recommendation
            intros = [
                f"YES! I found your perfect match! 🎯",
                f"This is it! I'm so excited to show you this! ✨",
                f"Found it! This is going to be PERFECT for you! 🚀"
            ]
            
            recommendation = f"{random.choice(intros)} **{title}** {reasoning}"
            
            if confidence > 0.9:
                recommendation += " This is seriously going to be your new obsession! What do you think? 🎮"
            else:
                recommendation += " I have a really good feeling about this one! Sound interesting? 😊"
                
        elif self.user_style["detail_level"] == "high":
            # Detailed, analytical recommendation
            recommendation = f"I found something really special for you. **{title}** {reasoning}"
            
            # Add platform context if relevant
            if platforms and self.user.platform_prefs:
                user_platforms = list(self.user.platform_prefs.values())[-1] if self.user.platform_prefs else []
                if any(p in platforms for p in user_platforms):
                    recommendation += f" Plus, it's available on your preferred platform. "
            
            recommendation += "What aspects of this sound most appealing to you?"
            
        else:
            # Concise, direct recommendation
            mood = self.session.exit_mood or 'your vibe'
            recommendation = f"Perfect match! **{title}** {reasoning} Exactly what you need for that {mood} mood! Interested? 🎮"
        
        return recommendation

    def _get_intelligent_reasoning(self, game_data: Dict, confidence: float) -> str:
        """Generate intelligent, contextual reasoning for recommendations"""
        reasons = []
        
        # Mood-based reasoning
        if self.session.exit_mood:
            mood_explanations = {
                'chill': 'has this perfectly relaxing flow that lets you just zone out and enjoy',
                'hyped': 'brings that high-energy excitement that matches your current vibe',
                'creative': 'gives you amazing creative freedom to build and express yourself',
                'story': 'tells an incredible story that will completely draw you in',
                'action': 'delivers that intense, fast-paced action you\'re craving',
                'cozy': 'has that warm, comfortable feeling that\'s perfect for unwinding'
            }
            if self.session.exit_mood in mood_explanations:
                reasons.append(mood_explanations[self.session.exit_mood])
        
        # Genre-based reasoning
        if game_data.get('genre'):
            genre = game_data['genre'][0] if isinstance(game_data['genre'], list) else game_data['genre']
            genre_appeals = {
                'puzzle': 'challenges your mind in the most satisfying way',
                'adventure': 'takes you on an incredible journey',
                'rpg': 'lets you dive deep into character progression and storytelling',
                'action': 'keeps your adrenaline pumping with amazing gameplay',
                'simulation': 'gives you that perfect sense of control and progression'
            }
            if genre.lower() in genre_appeals:
                reasons.append(genre_appeals[genre.lower()])
        
        # Confidence-based reasoning
        if confidence > 0.9:
            reasons.append("and honestly, this feels like it was made specifically for you")
        elif confidence > 0.7:
            reasons.append("and I think it\'s going to really click with your style")
        
        # User history-based reasoning
        if self.session.rejected_games and len(self.session.rejected_games) > 0:
            reasons.append("plus it\'s completely different from what didn\'t work before")
        
        return ' - it ' + ', '.join(reasons[:2]) if reasons else 'matches your gaming personality perfectly'

    def get_adaptive_rejection_response(self, rejection_reason: str = None) -> str:
        """Get intelligent response when user rejects a recommendation"""
        rejection_count = len(self.session.rejected_games or [])
        name = f" {self.user.name}" if self.user.name else ""
        
        # Analyze rejection reason for better follow-up
        if rejection_reason:
            reason_lower = rejection_reason.lower()
            if any(word in reason_lower for word in ['played', 'already', 'finished']):
                return f"Ah, you've already experienced that one{name}! Let me find you something fresh. What was your favorite part about it? That'll help me nail the next one! 🎯"
            elif any(word in reason_lower for word in ['not interested', 'boring', 'meh']):
                return f"Got it{name}! That style isn't hitting right. What kind of energy are you actually looking for? Let's pivot! 🔄"
            elif any(word in reason_lower for word in ['platform', 'device', 'console']):
                return f"Ah, platform mismatch{name}! What are you playing on? Let me find something perfect for your setup! 🎮"
        
        if rejection_count == 0:
            responses = [
                f"No problem{name}! That helps me understand your taste better. What specifically didn't grab you? 🎯",
                f"All good{name}! Let me recalibrate - what's missing from that suggestion? 😊",
                f"Got it{name}! Tell me what would make it more appealing and I'll find the perfect alternative! 🎮"
            ]
        elif rejection_count == 1:
            responses = [
                f"I'm getting a clearer picture of your style{name}! One quick question - what's a game you absolutely loved? 🎯",
                f"Thanks for the feedback{name}! I'm learning your preferences. What draws you to a game initially? 😊",
                f"Perfect{name}! This is helping me narrow it down. What's your ideal gaming session like? 🎮"
            ]
        elif rejection_count == 2:
            responses = [
                f"Okay{name}, I'm really dialing in on your taste now! What's the best game you've played recently? Let's use that as our north star! 💡",
                f"I appreciate your patience{name}! Let's try a different angle - what mood are you NOT in the mood for? 🤔",
                f"This is actually super helpful{name}! What's a game that made you lose track of time? That's the vibe I want to capture! ⏰"
            ]
        else:
            # Deep dive mode
            responses = [
                f"You know what{name}? Let's start fresh. Forget games for a sec - what's your ideal way to spend free time? I want to really understand you! 🌟",
                f"I'm determined to crack this{name}! What's something (not even a game) that you find genuinely engaging? Let's think outside the box! 🧩",
                f"Let's take a completely different approach{name}. What's your favorite movie or show? Sometimes that reveals gaming preferences better than anything! 🎬"
            ]
        
        return random.choice(responses)

    def get_adaptive_confirmation_response(self, user_response: str = "") -> str:
        """Get intelligent response when user shows interest in a recommendation"""
        name = f" {self.user.name}" if self.user.name else ""
        enthusiasm_indicators = ['!', '😊', '🎮', 'awesome', 'cool', 'love', 'amazing', 'perfect', 'yes', 'definitely']
        
        # Analyze user's response for enthusiasm level
        response_lower = user_response.lower()
        enthusiasm_count = sum(indicator in response_lower for indicator in enthusiasm_indicators)
        has_questions = '?' in user_response
        
        if enthusiasm_count > 2 or any(word in response_lower for word in ['love it', 'perfect', 'exactly']):
            # High enthusiasm - match their energy
            responses = [
                f"YES{name}! I absolutely KNEW this would be your jam! 🎉 You're going to have such an amazing time!",
                f"This is why I love what I do{name}! That excitement tells me everything - you found your perfect match! 🚀",
                f"I'm literally so excited for you{name}! This is going to be incredible! 🎯 Come back and tell me how it goes!"
            ]
        elif has_questions:
            # User is interested but wants more info
            responses = [
                f"Great questions{name}! I love that you're thinking it through. What specifically would you like to know more about? 🤔",
                f"Smart to ask{name}! The more you know, the better. What details would help you decide? 😊",
                f"I appreciate you being thorough{name}! What aspects are you most curious about? 🎮"
            ]
        elif any(word in response_lower for word in ['maybe', 'might', 'possibly']):
            # Cautious interest
            responses = [
                f"I totally get the cautious optimism{name}! Sometimes the best discoveries come from taking a small leap. What's your gut saying? 🤞",
                f"That's fair{name}! Trust your instincts. What would push it from 'maybe' to 'definitely' for you? 💭",
                f"I hear you{name}! No pressure at all. What would make you feel more confident about it? 😊"
            ]
        else:
            # Standard positive response
            responses = [
                f"Excellent choice{name}! 😊 I have a really good feeling about this match. Enjoy the adventure!",
                f"Perfect{name}! 👍 This should hit exactly what you're looking for. Have an amazing time!",
                f"Great decision{name}! 🎮 I think this is going to be exactly what you needed. Happy gaming!"
            ]
        
        # Add follow-up based on user relationship
        if self.interaction_count > 5:
            follow_ups = [
                " Let me know how it goes - I love hearing success stories!",
                " And hey, come back anytime you need another recommendation!",
                " I'm always here when you're ready for your next gaming adventure!"
            ]
            return random.choice(responses) + random.choice(follow_ups)
        
        return random.choice(responses)

    def _get_time_context(self) -> str:
        """Get contextual time-based greeting additions"""
        hour = datetime.now().hour
        if hour < 6:
            return "Up early gaming? I respect that!"
        elif hour < 12:
            return "Perfect morning for game discovery!"
        elif hour < 17:
            return "Afternoon gaming session incoming?"
        elif hour < 21:
            return "Evening vibes are perfect for this!"
        else:
            return "Late night gaming? My favorite time!"
    
    def _get_recent_preferences(self) -> str:
        """Get user's recent preferences for personalization"""
        if self.user.genre_prefs:
            recent_genres = list(self.user.genre_prefs.values())[-1] if self.user.genre_prefs else []
            if recent_genres:
                return recent_genres[0] if len(recent_genres) == 1 else f"{recent_genres[0]} and {recent_genres[1]}"
        return ""
    
    def get_contextual_question(self, context_type: str) -> str:
        """Generate contextual questions based on conversation state"""
        name = f" {self.user.name}" if self.user.name else ""
        
        questions = {
            "mood_clarification": [
                f"Help me understand that vibe better{name} - is it more active energy or chill energy?",
                f"That's interesting{name}! When you're feeling like that, do you want games that match it or contrast it?",
                f"I can work with that{name}! Are you looking to amplify that mood or maybe shift it?"
            ],
            "preference_deep_dive": [
                f"What's the last game that really grabbed you{name}? That might help me understand your style.",
                f"Quick question{name} - do you prefer games that challenge you or games that let you relax?",
                f"I'm curious{name} - what usually makes you lose track of time in a game?"
            ],
            "platform_optimization": [
                f"What's your main gaming setup{name}? I want to make sure my suggestions actually work for you!",
                f"Are you looking for something you can play in short bursts{name}, or do you have time for longer sessions?",
                f"Quick logistics question{name} - mobile, PC, or console gaming today?"
            ]
        }
        
        return random.choice(questions.get(context_type, [f"Tell me more about that{name}! 😊"]))
    
    def get_engagement_booster(self) -> str:
        """Generate responses to boost engagement when conversation lags"""
        name = f" {self.user.name}" if self.user.name else ""
        
        boosters = [
            f"I'm really enjoying figuring out your gaming personality{name}! What's something most people don't know about your gaming preferences?",
            f"You know what{name}? Let's make this fun - if you could only play one genre for the rest of your life, what would it be?",
            f"I'm curious{name} - what's a game that completely surprised you? Sometimes those reveal the most about what we actually like!",
            f"Here's a fun question{name} - would you rather play something that makes you think or something that makes you feel?"
        ]
        
        return random.choice(boosters)

def create_adaptive_response_system(user, session):
    """Factory function to create adaptive response system"""
    return AdaptiveResponseSystem(user, session)
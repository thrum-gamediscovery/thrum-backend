from typing import Dict, List
import random

class AdaptiveResponseSystem:
    def __init__(self, user, session):
        self.user = user
        self.session = session

    def get_adaptive_greeting(self) -> str:
        """Get greeting adapted to user's interaction history"""
        interaction_count = len(self.session.interactions)
        
        if interaction_count == 0:
            # First time user
            greetings = [
                "Hey there! 👋 I'm Thrum, your game discovery buddy. What's your vibe today?",
                "Hi! 😊 I'm Thrum - I help find games that match your mood. How are you feeling?",
                "Hello! 🎮 I'm Thrum, and I'm here to find your perfect game. What's on your mind?"
            ]
        elif interaction_count < 5:
            # Getting to know each other
            name = f" {self.user.name}" if self.user.name else ""
            greetings = [
                f"Hey{name}! 👋 Back for more game discoveries?",
                f"Hi{name}! 😊 Ready to find something awesome to play?",
                f"What's up{name}! 🎮 Looking for your next gaming adventure?"
            ]
        else:
            # Established relationship
            name = f" {self.user.name}" if self.user.name else ""
            greetings = [
                f"Hey{name}! 🎯 What kind of gaming mood are you in today?",
                f"Hi{name}! 😄 Ready to discover something new?",
                f"What's good{name}! 🚀 Let's find you something perfect to play!"
            ]
        
        return random.choice(greetings)

    def get_adaptive_follow_up(self, user_response_type: str) -> str:
        """Get follow-up questions adapted to user's response style"""
        
        # Analyze user's communication style
        user_messages = [i.content for i in self.session.interactions if i.sender.name == "User"]
        avg_length = sum(len(msg) for msg in user_messages[-3:]) / max(len(user_messages[-3:]), 1)
        
        if avg_length > 50:  # Detailed communicator
            follow_ups = {
                "mood_shared": [
                    "That's a great vibe! Tell me more about what kind of gaming experience would match that feeling.",
                    "I love that energy! What type of games usually capture that mood for you?",
                    "Perfect! When you're feeling like that, do you prefer something immersive or more casual?"
                ],
                "genre_mentioned": [
                    "Excellent choice! What specifically draws you to that genre? The mechanics, story, or atmosphere?",
                    "Nice! I can work with that. What are some examples of games in that genre that really clicked for you?",
                    "Great taste! Are you looking for something classic in that genre or maybe a fresh take on it?"
                ]
            }
        else:  # Brief communicator
            follow_ups = {
                "mood_shared": [
                    "Nice! What platform do you usually play on?",
                    "Cool! Any particular genre you're into?",
                    "Sweet! PC, mobile, or console gaming?"
                ],
                "genre_mentioned": [
                    "Perfect! What platform?",
                    "Got it! PC or mobile?",
                    "Nice choice! Where do you play?"
                ]
            }
        
        return random.choice(follow_ups.get(user_response_type, ["Tell me more! 😊"]))

    def get_adaptive_recommendation_style(self, game_data: Dict) -> str:
        """Adapt recommendation style to user preferences"""
        
        # Analyze user's detail preference
        user_messages = [i.content for i in self.session.interactions if i.sender.name == "User"]
        question_count = sum(msg.count('?') for msg in user_messages)
        detail_seeker = question_count > len(user_messages) * 0.3
        
        title = game_data.get('title', 'this game')
        genre = game_data.get('genre', ['game'])
        
        if detail_seeker:
            # Detailed recommendation
            return f"I found the perfect match! **{title}** is a {'/'.join(genre[:2])} game that really captures your vibe. Here's why it's perfect for you: {self._get_detailed_reasoning(game_data)}. What do you think?"
        else:
            # Concise recommendation
            mood = self.session.exit_mood or 'your vibe'
            return f"Perfect! **{title}** totally matches your {mood} mood! 🎮 It's exactly what you're looking for. Interested?"

    def _get_detailed_reasoning(self, game_data: Dict) -> str:
        """Generate detailed reasoning for recommendations"""
        reasons = []
        
        if self.session.exit_mood:
            mood_match = {
                'chill': 'relaxing gameplay that lets you unwind',
                'hyped': 'exciting action that keeps your energy up',
                'creative': 'creative elements that let you express yourself',
                'story': 'compelling narrative that draws you in'
            }
            if self.session.exit_mood in mood_match:
                reasons.append(mood_match[self.session.exit_mood])
        
        if game_data.get('game_vibes'):
            vibes = game_data['game_vibes'][:2]
            reasons.append(f"it has that {'/'.join(vibes)} feel you're after")
        
        return ', and '.join(reasons) if reasons else "it matches your gaming style perfectly"

    def get_adaptive_rejection_response(self) -> str:
        """Get response when user rejects a recommendation"""
        rejection_count = len(self.session.rejected_games or [])
        
        if rejection_count == 0:
            responses = [
                "No worries! Let me find something else that fits your vibe better. 🎯",
                "Got it! I'll dig deeper and find something more your style. 😊",
                "All good! Tell me what didn't click and I'll find a better match. 🎮"
            ]
        elif rejection_count < 3:
            responses = [
                "I'm getting a better sense of your taste! Let me try a different approach. 🎯",
                "Thanks for the feedback! I'm learning what you like. One more try? 😊",
                "Good to know! I'm narrowing down your perfect game. Bear with me! 🎮"
            ]
        else:
            responses = [
                "I really want to get this right for you! Can you tell me more about what you're looking for? 🤔",
                "Let's take a step back - what's a game you absolutely loved? That might help me understand your taste better! 💡",
                "I'm determined to find your perfect game! Help me out - what makes a game click for you? 🎯"
            ]
        
        return random.choice(responses)

    def get_adaptive_confirmation_response(self) -> str:
        """Get response when user shows interest in a recommendation"""
        enthusiasm_indicators = ['!', '😊', '🎮', 'awesome', 'cool', 'love', 'amazing', 'perfect']
        
        recent_user_messages = [
            i.content for i in self.session.interactions[-3:] 
            if i.sender.name == "User"
        ]
        
        enthusiasm_level = sum(
            sum(indicator in msg.lower() for indicator in enthusiasm_indicators)
            for msg in recent_user_messages
        )
        
        if enthusiasm_level > 2:  # High enthusiasm
            responses = [
                "YES! I knew that would be perfect for you! 🎉 Enjoy the game!",
                "Awesome! That's exactly the vibe I was going for! 🚀 Have fun!",
                "Perfect match! 🎯 You're going to love it!"
            ]
        else:  # Moderate enthusiasm
            responses = [
                "Great choice! 😊 I think you'll really enjoy it.",
                "Nice! 👍 That should be exactly what you're looking for.",
                "Excellent! 🎮 Hope you have a great time playing!"
            ]
        
        return random.choice(responses)

def create_adaptive_response_system(user, session):
    """Factory function to create adaptive response system"""
    return AdaptiveResponseSystem(user, session)
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
    
    def _get_conversation_stage(self) -> str:
        """Determine what stage of conversation we're in"""
        interaction_count = len(self.session.interactions)
        
        if interaction_count <= 1:
            return "greeting"
        elif "how does it work" in self.session.interactions[-1].content.lower() if self.session.interactions else False:
            return "explanation"
        elif not self.session.exit_mood and not self.session.entry_mood:
            return "mood_discovery"
        elif not self.user.genre_prefs or not any(self.user.genre_prefs.values()):
            return "genre_discovery"
        elif not self.session.meta_data or not self.session.meta_data.get("user_energy"):
            return "energy_discovery"
        elif not self.user.platform_prefs and not self.session.platform_preference:
            return "platform_discovery"
        elif not self.session.last_recommended_game:
            return "recommendation"
        elif not self.user.name:
            return "name_collection"
        else:
            return "conclusion"
    
    async def generate_interactive_response(self, user_input: str) -> str:
        """Generate response based on conversation stage"""
        
        stage = self.conversation_stage
        
        if stage == "greeting":
            return await self._generate_greeting(user_input)
        elif stage == "explanation":
            return await self._generate_explanation(user_input)
        elif stage == "mood_discovery":
            return await self._generate_mood_question(user_input)
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
    
    async def _generate_greeting(self, user_input: str) -> str:
        """Generate friendly greeting"""
        
        greetings = [
            f"{user_input} hey 👋\nYou looking for something to play or just vibin'?\nI'm Thrum btw. I help you find games that actually match your mood.",
            f"{user_input}! 👋\nWhat's good? Need a game rec or just chillin'?\nI'm Thrum - I match games to your actual vibe.",
            f"{user_input} 👋\nHere for games or just saying what's up?\nI'm Thrum. I help find games that actually fit your mood.",
            f"{user_input}! 👋\nLooking for something fun or just browsing?\nI'm Thrum - I find games based on how you're feeling, not just popular stuff."
        ]
        
        return random.choice(greetings)
    
    async def _generate_mood_question(self, user_input: str) -> str:
        """Ask about current mood/vibe"""
        
        mood_questions = [
            "Okay sick 😎\nSo what's the vibe today — chill, hyped, bored, emotional?",
            "Nice! Let's do it 😄\nWhat's your energy right now — relaxed, pumped, or something else?",
            "Sweet 🔥\nHow you feeling today — zen mode or ready for some action?",
            "Perfect! 👌\nWhat's the mood — peaceful, excited, or totally different?"
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
        """Ask about game preferences based on mood"""
        
        mood = self.session.exit_mood or "good"
        
        genre_questions = [
            f"{mood.title()} and chill — love that mix 😌\nWhat kinda games do you like? Puzzle, cozy, action, story stuff?",
            f"{mood.title()} vibes, nice! ✨\nWhat type of games usually grab you?",
            f"Love that {mood} energy! 🙌\nWhat's your go-to game style?",
            f"{mood.title()} mood is perfect 👍\nWhat kind of games hit different for you?"
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
        """Generate game recommendation"""
        
        from app.services.game_recommend import game_recommendation
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        try:
            game, _ = await game_recommendation(db=db, user=self.user, session=self.session)
            
            if game:
                self.session.last_recommended_game = game["title"]
                
                recommendations = [
                    f"Chill puzzles on mobile. Say less 🔍\nBased on all that — I've got one for you already. It's called **{game['title']}**. It's super relaxing, has this trippy architecture vibe, and tells a quiet story as you go.\nYou ever played it?",
                    f"Mobile gaming, nice choice! 📱\nAlright, perfect match for you — **{game['title']}**. It's got that calm puzzle vibe with beautiful visuals and a gentle story.\nHeard of it before?",
                    f"Mobile puzzles hit different 🎮\nGot the perfect one — **{game['title']}**. Relaxing, gorgeous, and has this dreamy storytelling thing going on.\nRing any bells?",
                    f"Phone gaming, respect! 👌\nI know exactly what you need — **{game['title']}**. Chill puzzles with stunning art and a quiet narrative thread.\nEver come across it?"
                ]
                
                return random.choice(recommendations)
            
        finally:
            db.close()
        
        return "Let me find something perfect for your vibe..."
    
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
        """Generate conversation conclusion"""
        
        name = self.user.name or "friend"
        
        conclusions = [
            f"Noted. See you next time, {name}.\nAnd hey — if you liked this, feel free to drop it in your group chat or whatever.\nWant me to send you a quick message you can forward?",
            f"Cool, {name}! 👋\nIf this was helpful, you can share it with friends who need game recs too.\nWant a shareable message?",
            f"Got it, {name}! ✌️\nFeel free to tell your gaming friends about this if it worked for you.\nNeed a message to share?",
            f"Perfect, {name}! 🎮\nIf you want to spread the word to other gamers, I can give you something to share.\nInterested?"
        ]
        
        return random.choice(conclusions)

async def create_interactive_engine(user, session):
    """Factory function to create interactive conversation engine"""
    return InteractiveConversationEngine(user, session)
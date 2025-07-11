import openai
import os
from typing import Dict, Any
from app.services.learning_engine import build_personalized_context, UserLearningProfile

openai.api_key = os.getenv("OPENAI_API_KEY")

# Legacy function for backward compatibility
async def generate_dynamic_response_legacy(context: Dict[str, Any]) -> str:
    prompt = build_context_prompt(context)
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        temperature=0.7,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def generate_dynamic_response(user, session, user_input: str = "", phase: str = None) -> str:
    """Generate interactive responses that naturally gather user preferences"""
    from app.services.interactive_conversation_engine import create_interactive_engine
    from app.services.learning_engine import UserLearningProfile
    
    # Create interactive conversation engine
    interactive_engine = await create_interactive_engine(user, session)
    
    # Extract and update preferences from user input
    if user_input:
        await _extract_preferences_from_input(user, session, user_input)
    
    # Generate interactive response that gathers missing info
    response = await interactive_engine.generate_interactive_response(user_input)
    
    # Update learning profile
    profile = UserLearningProfile(user, session)
    profile.log_feedback(mood=session.exit_mood or session.entry_mood)
    
    return response

async def _extract_preferences_from_input(user, session, user_input: str):
    """Extract preferences from user input using AI analysis"""
    from app.services.learning_engine import UserLearningProfile
    from datetime import datetime
    from sqlalchemy.orm.attributes import flag_modified
    
    profile = UserLearningProfile(user, session)
    input_lower = user_input.lower()
    
    # Extract mood/energy
    mood_keywords = {
        'chill': ['chill', 'relax', 'calm', 'peaceful', 'cozy', 'zen'],
        'hyped': ['hyped', 'excited', 'pumped', 'energetic', 'intense'],
        'creative': ['creative', 'build', 'craft', 'design', 'make'],
        'story': ['story', 'narrative', 'emotional', 'deep'],
        'action': ['action', 'fast', 'adrenaline', 'combat']
    }
    
    for mood, keywords in mood_keywords.items():
        if any(keyword in input_lower for keyword in keywords):
            session.exit_mood = mood
            profile.update_preferences(mood=mood)
            break
    
    # Extract platform
    platform_keywords = {
        'PC': ['pc', 'computer', 'steam', 'windows'],
        'Mobile': ['mobile', 'phone', 'android', 'ios'],
        'Switch': ['switch', 'nintendo'],
        'PlayStation': ['ps4', 'ps5', 'playstation'],
        'Xbox': ['xbox']
    }
    
    for platform, keywords in platform_keywords.items():
        if any(keyword in input_lower for keyword in keywords):
            profile.update_preferences(platform=platform)
            if not session.platform_preference:
                session.platform_preference = []
            session.platform_preference.append(platform)
            flag_modified(session, "platform_preference")
            break
    
    # Extract genre preferences
    genre_keywords = {
        'RPG': ['rpg', 'role playing', 'leveling'],
        'Action': ['action', 'fighting', 'combat'],
        'Puzzle': ['puzzle', 'brain', 'logic'],
        'Adventure': ['adventure', 'explore', 'discovery'],
        'Strategy': ['strategy', 'tactical', 'planning'],
        'Horror': ['horror', 'scary', 'spooky'],
        'Indie': ['indie', 'independent', 'unique']
    }
    
    for genre, keywords in genre_keywords.items():
        if any(keyword in input_lower for keyword in keywords):
            today = datetime.utcnow().date().isoformat()
            if not user.genre_prefs:
                user.genre_prefs = {}
            user.genre_prefs.setdefault(today, []).append(genre)
            flag_modified(user, "genre_prefs")
            break
    
    # Extract story preference
    if any(word in input_lower for word in ['story', 'narrative', 'plot', 'characters']):
        user.story_pref = True
    elif any(word in input_lower for word in ['gameplay', 'mechanics', 'action only']):
        user.story_pref = False
    
    # Store energy level in session metadata
    if not session.meta_data:
        session.meta_data = {}
    
    if any(word in input_lower for word in ['high energy', 'pumped', 'intense', 'fast']):
        session.meta_data['user_energy'] = 'high'
    elif any(word in input_lower for word in ['low key', 'chill', 'calm', 'slow']):
        session.meta_data['user_energy'] = 'low'
    
    flag_modified(session, "meta_data")

def build_context_prompt(context: Dict[str, Any]) -> str:
    """Build dynamic prompt based on context and user profile"""
    
    profile = context.get('user_profile', {})
    stage = context.get('conversation_stage', 'greeting')
    next_question = context.get('next_question_type', 'mood')
    personalization = context.get('personalization_level', 'low')
    
    # Build personalized context
    user_context = ""
    if profile.get('name'):
        user_context += f"User's name: {profile['name']}. "
    if profile.get('platform'):
        user_context += f"Plays on: {profile['platform']}. "
    if profile.get('mood_tags'):
        user_context += f"Recent moods: {', '.join(profile['mood_tags'][-2:])}. "
    if profile.get('reject_tags'):
        user_context += f"Dislikes: {', '.join(profile['reject_tags'])}. "
    if profile.get('playtime'):
        user_context += f"Plays: {profile['playtime']}. "
    
    base_prompt = f"""You are Thrum - a friendly game discovery assistant who talks like the examples.

{user_context}

Conversation stage: {stage}
Personalization level: {personalization}
User input: "{context.get('user_input', '')}"

Rules:
- Talk naturally like in the examples - casual, friendly, with emojis
- NEVER repeat the same phrasing twice
- Ask ONE thing at a time organically in conversation
- No formal questionnaires or lists
- Keep responses conversational and varied
- Use the user's name when you know it
- Reference their preferences naturally"""

    if stage == 'greeting':
        prompt = f"{base_prompt}\n\nTask: Greet them warmly and offer a quick game rec. Be welcoming and casual like the examples."
    
    elif stage == 'discovery':
        if next_question == 'platform':
            prompt = f"{base_prompt}\n\nTask: Naturally ask what they play on. Make it conversational, not a survey question."
        elif next_question == 'mood':
            prompt = f"{base_prompt}\n\nTask: Ask about their current gaming mood/energy. Keep it natural and varied."
        elif next_question == 'story_preference':
            prompt = f"{base_prompt}\n\nTask: Casually ask if they prefer story-driven games or gameplay-focused. Make it conversational."
        elif next_question == 'name':
            prompt = f"{base_prompt}\n\nTask: Offer to remember their name for next time. Keep it optional and friendly."
        elif next_question == 'playtime':
            prompt = f"{base_prompt}\n\nTask: Ask when they usually play games. Make it natural conversation."
        else:
            prompt = f"{base_prompt}\n\nTask: Continue the conversation naturally based on their response."
    
    elif stage == 'recommendation':
        game = context.get('recommended_game', 'Unknown')
        prompt = f"{base_prompt}\n\nTask: Recommend **{game}** confidently. Explain why it fits them based on what you know. Include platform info naturally."
    
    elif stage == 'conclusion':
        prompt = f"{base_prompt}\n\nTask: Wrap up warmly. Offer to help again in the future. Keep it friendly and natural."
    
    else:
        prompt = f"{base_prompt}\n\nTask: Respond naturally to their message. Be helpful and engaging like in the examples."
    
    return prompt
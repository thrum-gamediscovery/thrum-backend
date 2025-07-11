import openai
import os
from typing import Dict, Any

openai.api_key = os.getenv("OPENAI_API_KEY")

async def generate_dynamic_response(context: Dict[str, Any]) -> str:
    """Generate all responses dynamically using ChatGPT"""
    
    prompt = build_context_prompt(context)
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        temperature=0.7,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content.strip()

def build_context_prompt(context: Dict[str, Any]) -> str:
    """Build dynamic prompt based on context"""
    
    base_prompt = f"""You are Thrum - a professional game discovery assistant. 

Context:
- Phase: {context.get('phase', 'intro')}
- User input: "{context.get('user_input', '')}"
- Interaction count: {context.get('interaction_count', 0)}
- Rejected games: {len(context.get('rejected_games', []))}
- Last game: {context.get('last_game', 'None')}
- User mood: {context.get('mood', 'unknown')}
- Time: {context.get('time_context', 'anytime')}

Rules:
- Be conversational and professional
- No repetitive questions
- Make confident suggestions
- Vary your language each time
- Keep responses under 25 words
- End conversations with suggestions, not questions"""

    if context.get('phase') == 'intro':
        if context.get('returning_user'):
            prompt = f"{base_prompt}\n\nTask: Welcome back a returning user. Reference their last game if available."
        else:
            prompt = f"{base_prompt}\n\nTask: Introduce yourself as Thrum and explain what you do. Be welcoming."
    
    elif context.get('phase') == 'recommendation':
        if context.get('rejected_games', []):
            prompt = f"{base_prompt}\n\nTask: User rejected {len(context['rejected_games'])} games. Suggest: **{context.get('recommended_game', 'Unknown')}** with confidence."
        else:
            prompt = f"{base_prompt}\n\nTask: Recommend **{context.get('recommended_game', 'Unknown')}** based on their {context.get('mood', 'vibe')}."
    
    elif context.get('phase') == 'conclusion':
        prompt = f"{base_prompt}\n\nTask: End conversation professionally. Confirm **{context.get('last_game', 'the game')}** is perfect for them."
    
    else:
        prompt = f"{base_prompt}\n\nTask: Respond naturally to their message. Be helpful and engaging."
    
    return prompt
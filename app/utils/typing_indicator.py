import asyncio
import os
from openai import AsyncOpenAI
from app.utils.whatsapp import send_whatsapp_message

client = AsyncOpenAI()
model = os.getenv("GPT_MODEL")

async def send_typing_indicator(phone_number: str, session, delay: float = 8.0):
    """Send typing indicator after delay if processing takes too long"""
    await asyncio.sleep(delay)
    
    user_tone = session.meta_data.get("tone", "neutral")
    
    fallback_prompt = f"""
The user is waiting for a reply in a {user_tone} tone.
Generate a short 1-line typing delay message that fits this emotional energy.
Avoid repetition and vary each session.
Example types: chill = 'brb, scanning your vibe 😎', chaotic = 'yo gimme a sec 🌀', caring = 'hang tight, I'm thinking 💭'.
"""
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": fallback_prompt}],
            temperature=0.7,
            max_tokens=20
        )
        message = response.choices[0].message.content.strip()
    except:
        message = "thinking... 🤔"
    
    await send_whatsapp_message(phone_number, message, sent_from_thrum=False)
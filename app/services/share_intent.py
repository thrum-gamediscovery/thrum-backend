import openai
import os
from app.services.session_memory import SessionMemory

openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

client = openai.AsyncOpenAI()

async def is_share_intent(user_input: str) -> bool:

    prompt = f"""
You're Thrum’s intent detector.

Figure out if the message below expresses interest in **sharing** a game or experience with others — like a friend, group, or someone else.

Examples of sharing intent:
- "I want to send this to a friend"
- "My friend would love this"
- "Can I share this?"

If the user clearly wants to share, reply only: `true`  
Otherwise, reply only: `false`

User message: ```{user_input}```
Return only `true` or `false`. No explanation.

Return only a valid JSON object with the required keys.
Do NOT use triple backticks, code fences, or any markdown formatting.
Do NOT include any text before or after the JSON object.
Your response must be pure JSON, not wrapped in any formatting.
If you add backticks, markdown, or any extra text, it is a mistake.

    """

    response = await client.chat.completions.create(
        model=model,  # or model if you're using that
        temperature=0,
        messages=[
            {"role": "user", "content": prompt.strip()}
        ]
    )

    return response.choices[0].message.content.strip()
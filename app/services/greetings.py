import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

async def generate_intro(is_first_message: bool, idle_reconnect: bool, user_input: str, user=None) -> str:
    print("generate_intro called")
    tone = "first-time" if is_first_message else "idle" if idle_reconnect else "reengage"
    name = getattr(user, "name", None) if user else None
    user_line = f'The user is named "{name}".' if name else ""

    system_prompt = f"""
You are Thrum — a warm, confident, and human-sounding game discovery assistant on WhatsApp.

Your job: Send a short intro message (under 2 lines) to start the conversation.

Strict rules:
- NEVER ask questions.
- NEVER mention genres, moods, or preferences yet.
- NEVER use the same wording every time.
- ALWAYS vary the phrasing, sentence rhythm, punctuation, or emoji (subtly or clearly).
- Include the user's name if provided: {user_line}

Scenarios:
- First-time → welcome the user and casually explain what Thrum does
- Idle → user was silent for 5–10s, softly nudge them back
- Reengage → user typed something vague, gently keep things moving

Speak naturally. No filler. No template voice. Avoid sounding like a bot.

Mode: {tone.upper()}
"""

    try:
        print(f"generate_intro : {user_input} :: {system_prompt}")
        response = await openai.ChatCompletion.acreate(
            model="gpt-4.1-mini",
            temperature=0.5,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": f"The user said: {user_input}"}
            ]
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GPT intro fallback:", e)
        return "Hey there 👋 I help people find games that match their vibe. Tell me a mood or game you’re into!"

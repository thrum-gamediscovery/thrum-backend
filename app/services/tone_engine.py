import openai

async def detect_tone_cluster(db, session, user_input: str) -> str:
    """
    Uses GPT to detect the user's tone and maps it to a tone cluster.
    """
    prompt = f"""
You are a tone detector for a conversational assistant.
Classify the user's message below into one of these tone clusters:
[genz, chaotic, sincere, ironic, casual, neutral, warm, open, closed, funny, defiant, excited]

Message: "{user_input}"

Only respond with ONE WORD that best describes the tone. No punctuation.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        tone = response["choices"][0]["message"]["content"].strip().lower()
        tone = tone.split()[0]  # In case GPT adds anything extra
    except Exception as e:
        print(f"⚠️ Tone detection failed: {e}")
        tone = "neutral"

    return tone
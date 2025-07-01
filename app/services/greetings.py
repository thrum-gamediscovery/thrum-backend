import random
import openai

async def generate_intro(is_first_message: bool, idle_reconnect: bool, user_input:str, user=None) -> str:
    user_name = user.name if user and user.name else None

    # Variation tags for GPT
    vibe_tags = [
        "Keep it bold and confident.",
        "Sound a little mysterious.",
        "Be short and snappy.",
        "Use one metaphor if it fits.",
        "Make it feel like a cool friend texting.",
        "Make it feel like the user just bumped into someone who gets them.",
    ]

    if idle_reconnect:
        gpt_prompt = (
            "You are Thrum — a warm, chill friend who knows games inside-out. "
            "The user just came back after being quiet for a bit. "
            "Welcome them back casually, like a friend would. "
            "No questions. Just a quick, real check-in. "
        )
        if user_name:
            gpt_prompt += f"You know their name is {user_name}, so you can say it. "
        gpt_prompt += random.choice(vibe_tags)

        fallback_lines = [
            f"Hey {user_name}, still got something queued up for you." if user_name else None,
            f"{user_name}, ready to dive back in?" if user_name else None,
            "Hey, you're back. Still got something lined up for your vibe.",
            "Took a pause? All good. Let's pick up where we left off.",
            "Back again? I was just thinking of something you'd probably love.",
        ]
        fallback_lines = [line for line in fallback_lines if line]

    elif is_first_message:
        gpt_prompt = (
            f"You are Thrum — a human, clever, game-savvy friend. "
            f"This is your first-ever message to a new user. You don't know their name. "
            f"The user just messaged: \"{user_input}\".\n"
            "Start with a greeting like 'hey', 'hi', or 'hello'. "
            "Introduce yourself naturally — like 'I'm Thrum'. "
            "Then say something short and bold that sets the tone. "
            "No questions, no emojis, no robotic phrases. "
            "Do NOT mention journeys, adventures, or unlocking anything. "
            "Sound confident, casual, and short — max 2 lines, 15–20 words. "
            "Think like a cool gamer friend texting you."
            "and ask to recommend game."
        ) + " " + random.choice(vibe_tags)

        fallback_lines = [
            "Hey, I'm Thrum. Not here to list stuff—let's skip the scroll and find your next game.",
            "Hi — I'm Thrum. I know what slaps. You just vibe.",
            "Hello, I'm Thrum. Skip the endless scroll — I've got something better.",
            "Hey — name's Thrum. I've got something that might actually hit.",
            "Hey. I'm Thrum. I've been saving a good one just in case you showed up.",
            "Hi. I'm Thrum. No noise, no filler — just real picks.",
            "Hey. You made it. I've got something that might just click.",
        ]
    else:
        return None

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": gpt_prompt}],
            temperature=0.95,
            top_p=0.9,
            max_tokens=60,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("❌ GPT intro fallback used:", e)
        return random.choice(fallback_lines)
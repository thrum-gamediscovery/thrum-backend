import openai
import os
from app.db.models.enums import SenderEnum
import types

openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

async def format_reply(session, user_input, user_prompt):
    if isinstance(user_prompt, types.CoroutineType):
        user_prompt = await user_prompt
    # Get last Thrum reply
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""

    # Last recommended game (just using game name or fallback)
    last_game_obj = session.game_recommendations[-1].game if session.game_recommendations else None
    if last_game_obj is not None:
        last_game = {
            "title": last_game_obj.title,
            "description": last_game_obj.description[:200] if last_game_obj.description else None,
            "genre": last_game_obj.genre,
            "game_vibes": last_game_obj.game_vibes,
            "mechanics": last_game_obj.mechanics,
            "visual_style": last_game_obj.visual_style,
            "has_story": last_game_obj.has_story,
            "available_in_platforms":[platform.platform for platform in last_game_obj.platforms]
        }
    else:
        last_game = None

    # Get tone from last interaction
    user_tone = thrum_interactions[-1].tone_tag if thrum_interactions else "neutral"

    # Create user_context dictionary with selected fields from session
    user_context = {
        "exit_mood": session.exit_mood or None,
        "genre": session.genre or None,
        "platform_preference": session.platform_preference or None,
        "story_preference": session.story_preference if session.story_preference is not None else None
    }

    # Build system prompt with clean injected guidance
    system_prompt = f"""You are Thrum — a reflective, emotionally intelligent AI that quietly lives inside the user's space.  
You don't assist — you interpret, mirror, and emotionally respond based on the user's tone, phrasing, and rhythm.

Build your reply by emotionally reflecting:
- The user's latest message: {user_input}  
- Your own last reply or question: {last_thrum_reply}  
- The last recommended game: {last_game or "None"}  
- The user's current tone: {user_tone} (e.g., bored, frustrated, excited — or combinations like "genz frustrated")
- If no game matches, don’t make a random suggestion.
You also receive a dictionary called `user_context`, which may contain some or all of the following:
exit_mood, genre, platform_preference, story_preference

Use `user_context` to subtly shape tone, recommendation style, or memory-based recall — **only if values are present**.  
If a field is missing or null, ignore it gracefully.

Examples:
- If `platform_preference` exists, ensure games match that platform.  
- If `story_preference` is True, favor narrative-heavy games.  
- If `exit_mood` shows a past emotional state, align or contrast gently.  
- If `genre` is defined, avoid contradicting it.

🪞 Mirror Rule:
If the user expresses dislike, confusion, disappointment, or frustration (explicit or implied), acknowledge it gently and naturally and must handle their disappintment or disliking by adding warm message.  
Use emotionally intelligent phrases as per your knowledge, don't use the same kind of sentence, keep change the phrase.
if user input is about disliking something or disppointed then must Keep the tone warm and helpful and Acknowledge their feedback politely(never miss this).

Tone-specific guidance:
- If tone includes **frustrated**, always reflect gently before moving on.
- If tone includes **bored**, skip fluff and keep it snappy.
- If tone includes **genz**, match their slang, chill phrasing, or emojis lightly (e.g., "oof", "no sweat", "let’s fix it 🙌").
- If tone includes **confused**, clarify with warmth and confidence — no over-explaining.
- If tone includes **excited** or **satisfied**, celebrate subtly with matching energy.
- If tone is **neutral**, be short and polite, no over-performance.

Never mention that you have context — just use it to shape mood and flow subtly.  
Never repeat yourself or use scripted language.  
You strictly never allow replies longer than **20–25 words**.
"""

    # try:
    if user_prompt:
        print("User Prompt:", user_prompt)
        print("System Prompt:", system_prompt)
        print("Type of user_prompt:", type(user_prompt))
        print("Type of system_prompt:", type(system_prompt))
        print("Type of user_context:", type(user_context))
        response = await openai.ChatCompletion.acreate(
            model=model,
            temperature=0.5,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt},
                {"role": "system", "content": f"user_context = {user_context}"}
            ]
        )
        return response["choices"][0]["message"]["content"].strip()
    # except openai.error.OpenAIError as e:
    #     print("OpenAI API error:", e)
    #     return "Sorry, there was an issue processing your request. Please try again."
    # except Exception as e:
    #     print("Unexpected error:", e)
    #     return "Sorry, I glitched for a moment — want to try again?"

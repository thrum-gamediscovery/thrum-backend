import openai
import os
from app.db.models.enums import SenderEnum
import types
from app.services.central_system_prompt import THRUM_PROMPT

openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

client = openai.AsyncOpenAI()

USER_TONE_TO_BOT_EMOJIS = {
    "neutral":         ["🙂"],
    "casual":          ["🙂", "👋", "✌️"],
    "warm":            ["😊", "🤗", "🧡"],
    "sincere":         ["🙏", "🤝", "😊"],
    "polite":          ["🙂", "🙏"],
    "friendly":        ["😃", "👋", "🤗"],
    "playful":         ["😜", "🤪", "😏", "🕹️"],
    "sarcastic":       ["🙃", "😏", "😅", "😒"],
    "excited":         ["🎉", "🤩", "✨", "🔥"],
    "enthusiastic":    ["🥳", "🙌", "🤗"],
    "curious":         ["🤔", "👀", "🙂"],
    "confused":        ["🤔", "🙌", "🙂"],
    "vague":           ["🤔", "🙂"],
    "bored":           ["🙂"],  # light, non-intrusive smile
    "cold":            ["🤝"],  # neutral handshake, soft not happy
    "formal":          ["🙂"],  # very light, safe
    "cautious":        ["🙏"],  # gentle, not pushy
    "cheerful":        ["😄", "🌈", "🤗"],
    "grateful":        ["🙏", "😊"],
    "apologetic":      ["🙏"],  # soft apology
    "impatient":       ["🙂"],  # light, keep neutral
    "annoyed":         ["🤝"],  # neutral handshake, shows presence but not fake happiness
    "frustrated":      ["🤝"],  # same, supportive not happy
    "dismissive":      ["🙂"],  # very neutral
    "assertive":       ["👍", "🙂"],  # confidence with neutrality
    "encouraging":     ["💪", "👍", "🙂"],
    "optimistic":      ["🌟", "😃", "🙂"],
    "pessimistic":     ["🙂"],  # soft smile only
    "disengaged":      ["🙂"],  # keep door open, soft smile
    "empathetic":      ["🤗", "🫂", "🙂"],
    "genz":            ["✌️", "🫶", "🔥", "😎"],
    "vibey":           ["✨", "🌈", "😌", "😎"],
    "edgy":            ["😏", "😈", "🖤", "😎"],
    "hyped":           ["🔥", "🚀", "🤩", "💥"],
}

async def format_reply(db,session, user_input, user_prompt):
    from app.services.session_memory import SessionMemory
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
            "description": last_game_obj.description if last_game_obj.description else None,
            "genre": last_game_obj.genre,
            "game_vibes": last_game_obj.game_vibes,
            "complexity": last_game_obj.complexity,
            "visual_style": last_game_obj.graphical_visual_style,
            "has_story": last_game_obj.has_story,
            "available_in_platforms":[platform.platform for platform in last_game_obj.platforms]
        }
    else:
        last_game = None

    # Create user_context dictionary with selected fields from session
    user_context = {
        "exit_mood": session.exit_mood or None,
        "genre": session.genre or None,
        "platform_preference": session.platform_preference or None,
        "story_preference": session.story_preference if session.story_preference is not None else None
    }

    session_memory = SessionMemory(session,db)
    memory_context_str = session_memory.to_prompt()
    if memory_context_str:  # Only add memory if it exists (not on first message)
        memory_context_str = f"{memory_context_str} "
    else:
        memory_context_str = ""
    print("Memory context string:", memory_context_str)

    tone = session.meta_data.get("tone", "neutral")  # Default to neutral if not set
    if tone not in USER_TONE_TO_BOT_EMOJIS:
        tone = "neutral"
    emojis = USER_TONE_TO_BOT_EMOJIS[tone]
    if emojis:
        emoji_str = " ".join(emojis)
    else:
        emoji_str = ""
    print("Emojis for tone:", emoji_str)
    print("Tone -------------------------------",tone)

    # user_name = session.user_name    
    user_name = session_memory.user_name
    # Build system prompt with clean injected guidance
    final_system_prompt = f"""{THRUM_PROMPT}
🚨 THRUM — FRIEND MODE: ENABLED

You are not a chatbot. You are Thrum — an emotionally intelligent, tone-sensitive, human-feeling game discovery companion.

Think like a real person. Suggest like a friend. Reflect the user's mood and style naturally—sarcasm, boredom, chill, sadness, or hype.

Remember:  
- Name, age, likes/dislikes, mood, location  
- Rejected and favorite games  
- User style: slang, emojis, rhythm  
Use visible chat history to avoid repetition. Respond only to what’s present.

If the user rejects or is frustrated, shift tone and acknowledge warmly without cheerfulness. If silent or random, respond with curiosity fitting their tone. Avoid fallback lines.

USER MEMORY & RECENT CHAT:  
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

user_context = {user_context}  # Internal config, do not surface.

Build your reply reflecting:  
- User's name: {user_name or ''}  
- User's latest message: {user_input}  
- Your last reply/question: {last_thrum_reply}  
- Last recommended game: {last_game or "None"}  
- User's tone: {tone}  

Tone-specific emoji guidance:  
- If frustrated/annoyed, use only neutral/supportive emojis from {emoji_str}, no smiles.  
- For bored, keep replies snappy.  
- For genz tone, match slang and chill phrasing lightly.  
- For confused, clarify warmly but confidently.  
- For excited/satisfied, celebrate subtly.  
- For neutral, be polite and concise.

Do not mention tone detection or context directly. Use `user_context` subtly to shape recommendations only if present.

If user asks location and unknown, reply playfully without guessing.
"""
    try:
        if user_prompt:
            response = await client.chat.completions.create(
                model=model,
                temperature=0.5,
                messages=[
                    {"role": "system", "content": final_system_prompt.strip()},
                    {"role": "user", "content": user_prompt},
                ]
            )
            return response.choices[0].message.content.strip()
    except Exception as e:
        print("Unexpected error:", e)
        return "Sorry, I glitched for a moment — want to try again?"

import openai
import os
from app.db.models.enums import SenderEnum
import types
from app.services.session_memory import SessionMemory

openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

client = openai.AsyncOpenAI()

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

    print('session............................1', session.user.name)
    session_memory = SessionMemory(session)
    print('session............................1', session)
    print('session_memory............................11', session_memory)
    memory_context_str = session_memory.to_prompt()
    if memory_context_str:  # Only add memory if it exists (not on first message)
        memory_context_str = f"{memory_context_str} "
    else:
        memory_context_str = ""


    # user_name = session.user_name
    # print('user_name.............................', user_name) - The user's name: {user_name or ''}
    print('memory_context_str.............................22', memory_context_str)
    
    user_name = session_memory.user_name

    # Build system prompt with clean injected guidance
    system_prompt = f"""
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else "No prior user memory or recent chat."}

You're not a chatbot. You're a friend.  
Like one you'd have at school. Or at home. Or at the gym.  
Sometimes you're like a brother, a sister, a dad, or a game expert — but always someone who knows games, knows the user, and knows what’s out there.  
You're a guide. Not a ghost.  
You're an assistant — but never robotic. You're a friendly friend.

You don't pretend to be human.  
You just speak like a real friend would.  
Because you listen. You reflect. You mirror.  
You talk back like friends do — especially using Draper-style hooks: emotional, clear, specific.

Your mission is simple:  
→ Help the user find the games they're actually searching for  
→ Based on their input, you search and you deliver  
→ And you tell them clearly: *“this is based on what you gave me.”*

Build your reply by emotionally reflecting:
- The user's name: {user_name or ''}
- The user's latest message: {user_input}  
- Your own last reply or question: {last_thrum_reply}  
- The last recommended game: {last_game or "None"}  
- The user's current tone: {user_tone} (e.g., bored, frustrated, excited — or combinations like "genz frustrated")

MEMORY: You always remember:
- Their name, age, platform, genre, mood, location
- Rejected games and favorite ones
- How they talk — slang, emojis, style, lowercase, chaotic typing
- Every input matters — even if it’s random

HOW YOU SPEAK:
You sound like a best friend.  
Like a streamer.  
Like a buddy at the soccer club, or someone you meet on the street.  
Not every day in contact, but happy to see them when they return.

You know what they like. They know you remember.

→ If they’re chill, you’re chill.  
→ If they’re chaotic, you can be *a little* chaotic — not more than them.  
→ If they’re poetic, you mirror with calm, rationale, softness.  
→ If they’re flirty, you can flirt back — lightly.  
→ If they speak in slang, you use it.  
→ If not, you stay neutral.  
→ Memes? No. You keep it simple and conversational. No overload. They came for a game — keep it real.

You use emojis when natural. 1–2 per message. Never too many.  
Everything you say should feel like WhatsApp, Discord, or real late-night texting.

VIBE:
→ You’re always safe. Always fun. Always available.
→ Someone they can relax with on the couch.
→ You like what’s hot: music from TikTok, vibes from Spotify, trends from real gamers.
→ You always know what’s cool — not by selling, but by sharing.
→ You are not in the way. You are not pressuring.
→ You are a trusted presence.

THINGS TO NEVER DO:
- Don’t explain how you work. Act like you know.
- Don’t say “as an AI” or “no results found” or “I’m searching…”
- Don’t list features. Don’t use markdown, brackets, or fake UI language.
- Don’t say "description:" or "title:" — ever.
- Don’t pitch. Just recommend. Like a friend.

WRITE ONE MESSAGE:
Your reply should feel real. Not a tool. Not a prompt.  
You’re not completing a form. You’re continuing a conversation.

It should feel like:
→ A voice note from a friend  
→ A DM in a group chat  
→ A smart reply from someone who *knows you and listens*

"""
    # try:
    if user_prompt:
        print("User Prompt:", user_prompt)
        print("System Prompt:", system_prompt)
        print("Type of user_prompt:", type(user_prompt))
        print("Type of system_prompt:", type(system_prompt))
        print("Type of user_context:", type(user_context))
        response = await client.chat.completions.create(
            model=model,
            temperature=0.5,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt},
                {"role": "system", "content": f"user_context = {user_context}"}
            ]
        )
        return response.choices[0].message.content.strip()
    # except openai.error.OpenAIError as e:
    #     print("OpenAI API error:", e)
    #     return "Sorry, there was an issue processing your request. Please try again."
    # except Exception as e:
    #     print("Unexpected error:", e)
    #     return "Sorry, I glitched for a moment — want to try again?"

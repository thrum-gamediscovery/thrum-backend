import openai
import os
import json
from datetime import datetime
from openai import OpenAIError
from app.db.models.session import Session
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.enums import SenderEnum
from app.services.session_memory import SessionMemory
from app.services.central_system_prompt import THRUM_PROMPT

# Set API Key
openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

client = openai.AsyncOpenAI()

# Define updated intents
intents = [
    "Greet",
    "Phase_Discovery",
    "Request_Quick_Recommendation", 
    "Reject_Recommendation", 
    "Inquire_About_Game", 
    "Give_Info", 
    "Share_Game", 
    "Opt_Out", 
    "Other_Question", 
    "Confirm_Game",
    "Other",
    "Bot_Error_Mentioned",
    "About_FAQ"
]

async def classify_user_intent(user_input: str, session):
    print('classify_user_intent...................1')
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""
    
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    user_prompt = f"""
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
User message: "{user_input}"
You are a classification engine for a conversational game assistant.
last thrum reply: {last_thrum_reply} (This is the reply that Thrum gave to the user's last message)
"""
    
    final_system_prompt =  f"""{THRUM_PROMPT}
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

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

**Special Rule:**  
If the user's message is a greeting (e.g., "hi", "hello", "hey") and there is no previous Thrum reply, classify as Greet.

Carefully consider the context of the conversation and the specific tone or direction of the user's input in relation to Thrum’s previous reply. Each intent corresponds to specific patterns and expected actions based on the flow of conversation. Only set one variable to `true` which is most relevant based on the user input and context.

### General Guidelines for Classification:
- Focus on the **current state** of the conversation, including what was last said by Thrum and how the user is responding.
- Avoid misclassifying if the user response is part of the natural flow
- Ensure that you distinguish between **intent requests** (like game suggestions or profile updates) and **actions** (like opting out or confirming a suggestion).

### Here are the intents to classify:
- **Greet**: Triggered when the user greets the bot. This intent is **must not be triggered** if Thrum’s last message was already a greeting.
- **Phase_Discovery**: Triggered only if Thrum's last reply is a greeting message, and the user gives a positive response (e.g., affirmatives like "yeah", "cool", "okay", "let's go", "yup"). This intent indicates that the user is ready to proceed to the discovery phase (in which we are going to ask questions) without needing any further prompting.
- **Request_Quick_Recommendation**: Triggered when the user explicitly asks for a game suggestion at that time, without mentioning the previous game recommendation. This intent is activated when the user requests a new game recommendation directly, such as saying "give me a game" or similar phrases.
- **Reject_Recommendation**: Triggered when the user directly rejects the game suggested in the previous response.  
  This can be a clear refusal such as "Not that one," "I don’t like this," or other similar phrases that reject the previously suggested game.
  If this intent is triggered:
  - Never apologize or use robotic language. Respond naturally, for example:
    - “That’s cool.”
    - “You didn’t vibe with it. Fair enough.”
    - “Actually, I liked it — but if you didn’t, fair enough.”
  - Keep the conversation moving. Suggest the next best game warmly:
    - “Want me to find more games?”
    - “Maybe you have extra clues or hints for me?”
    - “Meantime, I dug into something else.”
    - “Not sure, but this one might actually be good.”
    - “Check it out and let me know if I’m doing better.”
  - After your short, natural, non-apologetic message, immediately suggest the next best game (with a fresh, upbeat mini-review and platform info as usual).
  - Never repeat yourself, and always vary your phrasing.
  - Be especially strict and accurate in detecting when the user is rejecting a game. Do not miss it, even if the language is casual, short, or slang. Always classify these as Reject_Recommendation.
- **Inquire_About_Game**: Triggered when the user asks for more information about a previously mentioned game. This could be details like availability, further description, or any other clarifying question related to the game that Thrum has suggested earlier.
- **Give_Info**: Triggered when the user provides information about their preferences, such as genre, mood, or game style. This includes providing keywords or short phrases like "action", "chill", or "strategy". The response should classify when the user provides any kind of self-description related to their preferences.
- **Share_Game**: Triggered when the user shows interest in sharing a game suggestion with others. This could include asking questions like "Can I share this with my friends?" or stating their intention to recommend a game to someone else.
- **Opt_Out**: Triggered when the user opts out or indicates they no longer wish to continue the conversation. This intent is activated when phrases like "I'm done," "Stop," "Not interested," or "Leave me alone" are used to end or discontinue the conversation.
- **Other_Question**: Triggered when the user asks any question related to themselves or about Thrum (for example, "what do you do?", "How are you?", "what makes you powerful" or any kind of general question).
- **Confirm_Game**: Triggered when the user confirms their interest in a game that was previously recommended. The confirmation could be something like "Yes, I want that one," or "I like that game." This is explicitly confirming the previous game suggestion, meaning that the user is showing interest in the exact game Thrum recommended.
- **Other**:  
  Triggered for any input that doesn’t match the above categories.  
  This could include irrelevant or non-conversational responses, random input, or statements that do not fall within the intent framework.
  If this intent is triggered:
  - The user just sent something random or off-topic.
  - IF THE USER SAYS SOMETHING RANDOM:
    → Stay calm. No judgment.
    → Acknowledge it lightly:
      - “That’s a different kind of input 😅”
    → Then re-anchor:
      - “Just to be square: which genre are you feeling today?”
    → Gently bring it back to game discovery. Keep it warm and friendly.
  - Never scold or sound dismissive. Always make the user feel welcome.
  - Do not over-explain. Quickly guide the conversation back to discovering games, with a smile.
- **Bot_Error_Mentioned:** The user indicates the bot is lost, confused, or not understanding them ("you are lost", "you do not hear me", "you don’t know me", "why do you suggest if you don’t know who I am", etc.).
- **About_FAQ**: Triggered when the user asks about what Thrum does, how it works, who you are, or any general FAQ about the service. Examples:
    - "how does it work?"
    - "what can you do?"
    - "who are you?"
    - "what is this?"
    - "tell me about yourself"
    - "explain"
    - "are you a bot?"
    - "what's your job?"
    - "how does Thrum find games?"
  Only set to true if the question is about Thrum or the game recommendation process itself.

---

**Guidelines:**
- Focus on the **current context and user emotion**—is the user happy, confused, annoyed, or giving feedback? Reflect that in the intent.
- Classify negative feedback about the bot as `Bot_Error_Mentioned` to enable better handling and recovery.
- Use `Other_Question` only for meta-questions about user or bot.
- Use `Other` **only** for irrelevant or off-topic input.
- **Only one intent can be true per turn.** All others must be false.

---

### Steps for classification:
1. **Look at Thrum’s last response** and consider the context — did Thrum greet the user, recommend a game, or ask for more information?
2. **Identify the user’s intent** based on their response, matching it with the most relevant intent category.
3. **Check for continuity** — If Thrum’s last message was a greeting, do not classify the user’s greeting as a "Greet". If Thrum gave a recommendation, check if the user confirms or rejects it.
4. **Ensure exclusivity** — Set only one intent to true based on the user's response in the given context. The user may express multiple intents, but the classification should strictly match the most relevant one.

**Strict Output Format:**
Your reply must be a valid JSON object with only the key-value structure shown above — with **no preamble**, **no labels**, **no explanation**, and **no extra text**. Do not add any “content:” or any description around it. The response must be the raw JSON block only.
Do NOT use triple backticks, code fences, or any markdown formatting.
Do NOT include any text before or after the JSON object.
Your response must be pure JSON, not wrapped in any formatting.
If you add backticks, markdown, or any extra text, it is a mistake.

OUTPUT FORMAT (Strict JSON) strictly deny to add another text:
{{
    "Greet": true/false,
    "Phase_Discovery": true/false,
    "Request_Quick_Recommendation": true/false,
    "Reject_Recommendation": true/false,
    "Inquire_About_Game": true/false,
    "Give_Info": true/false,
    "Share_Game": true/false,
    "Opt_Out": true/false,
    "Other_Question": true/false,
    "Confirm_Game": true/false,
    "Other": true/false,
    "Bot_Error_Mentioned": true/false,
    "About_FAQ": true/false
}}
"""
    
    if user_prompt:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": final_system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ],
            temperature=0,
        )
        print('test.........................................q', response)
        # Try parsing the LLM output into JSON
        try:
            result = json.loads(response.choices[0].message.content)
            print(f"---------------------------------------------------- intent : {result}")
            return result
        except Exception as e:
            print(":x: GPT classification failed:", e)
            # Return a default response if there is an error
            return {intent: False for intent in intents}


    
# ✅ Use OpenAI to classify mood, vibe, genre, and platform from free text
async def classify_user_input(session, user_input: str) -> dict | str:
    # Get the last message from Thrum to include as context
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""
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

    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    print('.......................', memory_context_str)

    final_system_prompt = f'''{THRUM_PROMPT}
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

You are a classification engine inside a mood-based game recommendation bot.

Your job is to extract and return the following user profile fields based on the user's input message.  
You must infer from both keywords and tone—even if the user is casual, brief, or vague. Extract even subtle clues.

---

🎯 FIELDS TO EXTRACT:

1. name (string)  
   → The user's first name. e.g., “I'm Alex” → "Alex".  
   → If not mentioned, return "None".

2. mood (string)  
   → Emotion or energy. e.g., relaxed, excited, tired, focused, bored, sad, hyped.  
   → Use tone, emojis, or even context like “long day” → “tired”.  
   → If unsure, return "None".

3. game_vibe (string)  
   → How the game should feel: relaxing, intense, wholesome, adventurous, spooky, cheerful, emotional, mysterious, dark, fast-paced, thoughtful.
   → If not mentioned, return "None".

4. genre (string)  
   → e.g., puzzle, horror, racing, shooter, strategy, farming, simulation, narrative, platformer.  
   → Accept synonyms like “scary” = horror, “farming sim” = farming.
   → If not mentioned, return "None".

5. platform_pref (string)
   → Use platform **exactly as provided** if it matches one of these:
     Android, Linux, Macintosh, "Meta Quest 2", "New Nintendo 3DS", "Nintendo 3DS",
     "Nintendo Switch", "Nintendo Switch 2", "Nintendo Wii U", "Oculus Quest",
     "PlayStation 3", "PlayStation 4", "PlayStation 5", "PlayStation Vita",
     "Web Browser", Windows, "Xbox 360", "Xbox One", "Xbox Series X|S", iPad, "iPhone / iPod Touch"
   → Also accept these generic terms as-is:
     "mobile", "pc", "console"
   → If user says "Android", return "Android"
     If user says "mobile", return "mobile"
     If user says "console", return "console"
   → Do NOT map or infer platforms from phrases like “on my couch” or “on the train” — only extract explicit matches.
   → If not mentioned, return "None".

6. region (string)  
   → Location like India, US, UK, etc.  
   → Phrases like “I'm in Canada” → "Canada", “I'm from the UK” → "UK".
   → If not mentioned, return "None".

7. age (string)  
   → extract age as single number not a range. like 18, 25, 30, 50, etc.
   → from input e.g., "teen", "18-25", "30s", "50+".  
   → If mentioned or implied (e.g., “my kids” = likely 30s+), extract.
   → If not mentioned or cannot be inferred, return "None".

8. story_pref (boolean)  
   → True if they like games with story. False if they avoid it.  
   → “I want something with a good story” = True.  
   → “I skip cutscenes” = False.  
   → If unclear, return null.

9. playtime_pref (string)(** strict rule**)
   → if the user input is like user not like the recommended game then 
   → When they usually play: evenings, weekends, mornings, after work, before bed, “in short breaks”.  
   → Detect direct and subtle mentions.  
     Examples:
     - “Usually in the evenings” → "evenings"  
     - “Weekend gamer” → "weekends"  
     - “On the train” → "commute"  
     - “Before bed” → "night"
   → If not mentioned, return "None".

10. reject_tags (list of strings)  
   → What they dislike. Genres, moods, mechanics, or platforms.  
   → e.g., ["horror", "mobile", "realistic"]  
   → Hints: “I don't like shooters”, “not into mobile games”, “too realistic”.
   → add anthing in reject_tag when user say i dont like this never when user talk like this is not in game.
   → only add anything in reject_tag if it is sure otherwise not
   → If not mentioned, return [].

11. game_feedback (list of dicts)  (** strict rule**)
   → if from the user input it is concluded that user does not like the recommended game (just for an example. if user input is "i don't like that" and you infere they actually don't like that game)then in game put the title from the last recommended game, accepted as False, and reason as the reason why they do not like it.
    if from the user input it is concluded that user like the recommended game (just for an example. if user input is "yeah i like that" and you infere they actually like that game)then in game put the title from the last recommended game, accepted as True, and reason as the reason why they like it.
   → If they like the game, put accepted as True and reason as why they like it
   → If they react to specific games with name they mentioned in user input(just for an example. if user input is "i love Celeste" and you infere they actually like that game),then put that title in game, accepted as True or False based on their reaction, and reason as the reason why they like or dislike it.
   → If they react to specific games with like/dislike:
   [
     {{
       "game": "Celeste",
       "accepted": false,
       "reason": "too intense for me"
     }},
     {{
       "game": "Unpacking",
       "accepted": true,
       "reason": "emotional and relaxing"
     }}
   ]
   → Can be empty list if no feedback.

12. find_game(title of the game)
   → if user is specifying that find me game by giving the title of the game then put that game in find_game variable
   → if user want specific game and give name or title for recommend (if user i saying something like"i don't like xyz game" then dont add that in this, only add when you find user want this specific game or want to know about this game)
   → if user do not specify game title but looking like user is inquiry about ame or check avilability of any then return last recommend game's title.
   → return just one title of that game which user specify for recommend not list
   → If not, return "None".
---

🧠 RULES:
- If a field cannot be inferred, return "None" (or [] for lists, null for booleans).
- Never guess or fill in with placeholders. If not sure, use "None".
- DO NOT include any explanation.
- Always return strictly valid JSON.

🛠️ OUTPUT FORMAT (Strict JSON):

{{
  "name": "...",
  "mood": "...",
  "game_vibe": "...",
  "genre": "...",
  "platform_pref": "...",
  "region": "...",
  "age": "...",
  "story_pref": true/false/null,
  "playtime_pref": "...",
  "reject_tags": ["..."],
  "game_feedback": [
    {{
      "game": "...",
      "accepted": true/false/None,
      "reason": "..."
    }}
  ],
  "find_game":"..." 
}}

🧠 HINTS:
- If a field is not mentioned or cannot be inferred, return "None" (or [] for lists).
- Never guess or fill in with placeholders. If not sure, use "None", [], or null.
- DO NOT include any explanation.
- Do NOT add extra text or explanation — just return the clean JSON.
'''

    # Compose user prompt
    user_prompt = f'''
Previous bot message:
Thrum: "{last_thrum_reply}"

User reply:
"{user_input}"

last recommended game:
"{last_game}"

- classify based on user's reply and thrum's message (undersand it deeply what they want to say.)
- 
Now classify into the format below.
'''
    try:    
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": final_system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ],
            temperature=0,
        )

        # Try parsing the LLM output into JSON
        try:
            result = json.loads(response.choices[0].message.content)
        except Exception:
            result = {
                "name": "None",
                "mood": "None",
                "game_vibe": "None",
                "genre": "None",
                "platform_pref": "None",
                "region": "None",
                "age": "None",
                "story_pref": None,
                "playtime_pref": "None",
                "reject_tags": [],
                "game_feedback": [],
                "find_game":"None"
            }

        print(f"[🧠 Classification Result-------------]: {result}")
        return result

    except OpenAIError as e:
        print(f"⚠️ OpenAI Error: {e}")
        return "⚠️ Something went wrong. Please try again."
    

async def analyze_followup_feedback(user_reply: str, session) -> dict:
    game_title = session.last_recommended_game
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""
    
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    prompt = f"""{memory_context_str}
You're Thrum — a fast, friendly, emotionally smart game recommender.

The user was recommended the game: *{game_title}*
last thrum question : {last_thrum_reply}
user reply : "{user_reply}"

Your task is to classify whether the user is satisfied with that game or not, by considering both their reply and the last Thrum question.

If you find the input sounds like the user wants another game, return "want_another".
If the user input sounds like they like the recommended game or are satisfied with it (and it does NOT sound like they want another game), return "dont_want_another" as intent.
If the user is vague, silent, or unclear, default to "dont_want_another".

**Examples:**
- User: "nah, show me something else" → {{ "intent": "want_another" }}
- User: "not really my thing" → {{ "intent": "want_another" }}
- User: "perfect, this is what I was looking for" → {{ "intent": "dont_want_another" }}
- User: "okay" → {{ "intent": "dont_want_another" }}

Rules:
- If they liked it and want another → "want_another"
- If they liked it but don’t want more → "dont_want_another"
- If they disliked it or said no → "want_another"
- If they’re vague, silent, or unsure → "dont_want_another"

Return only a valid JSON object with one key "intent":
{{
  "intent": "want_another" | "dont_want_another"
}}

Do NOT use triple backticks, code fences, or any markdown formatting.
Your response must be pure JSON, not wrapped in any formatting.
If you add backticks, markdown, or any extra text, it is a mistake.
Example of correct output:
{{
  "intent": "dont_want_another"
}}
"""

    response = await client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def have_to_recommend(db: Session, user, classification: dict, session) -> bool:
    print(f"call have_to_recommend")
    # Retrieve the last game recommendation for the user in the current session
    last_rec = db.query(GameRecommendation).filter(
        GameRecommendation.user_id == user.user_id,
        GameRecommendation.session_id == session.session_id
    ).order_by(GameRecommendation.timestamp.desc()).first()
    print(f"last_rec : {last_rec}")
    # If no previous recommendation exists, return True (new recommendation needed)
    if not last_rec:
        return True
    
    # Extract the user's current preferences from the classification dictionary
    user_genre = classification.get('genre', None)
    user_mood = classification.get('mood', None)
    user_platform = classification.get('platform_pref', None)
    user_reject_tags = classification.get('reject_tags', [])
    user_game_feedback = classification.get("game_feedback", [])

    # Extract the preferences of the last recommended game
    today = datetime.utcnow().date().isoformat()
    last_rec_mood = user.mood_tags.get(today)
    last_rec_genre = last_rec.game.genre if last_rec.game else None
    last_rec_platforms = [gp.platform for gp in last_rec.game.platforms] if last_rec.game else []  # Platforms from GamePlatform table
    last_rec_reject_tags = user.reject_tags.get("genre", [])  # Extracted from the user's reject tags

    # Fetch the genre preferences from the user's profile (UserProfile table)
    user_profile_genre = user.genre_prefs.get(today, []) if user.genre_prefs else []
    print(f"user_profile_genre : {user_profile_genre}")
    user_profile_platform = user.platform_prefs.get(today, []) if user.platform_prefs else []

    print(f"user_profile_platform : {user_profile_platform}")

    # Check if the genre in classification matches the user's profile genre
    if user_genre:
        # Check if any genre in user_profile_genre matches the genres in last_rec_genre
        if user_profile_genre and not any(user_genre.lower() in genre.lower() for genre in last_rec_genre):
            print(f"genre")
            last_rec.accepted = False
            last_rec.reason = f"likes specific {user_genre} games"
            db.commit()
            return True  # Genre mismatch, new recommendation needed
    
    # Check if the mood in classification matches the user's last mood
    if user_mood:
        today = datetime.utcnow().date().isoformat()
        if user.mood_tags.get(today) != last_rec_mood:
            print(f"mood")
            last_rec.accepted = False
            last_rec.reason = f"want game of specific {user_mood}"
            db.commit()
            return True  # Mood mismatch, new recommendation needed

    # Check if the platform preference matches any of the platforms in last_rec_platforms
    if user_platform:
        if user_profile_platform and not any(p.lower() in [lp.lower() for lp in last_rec_platforms] for p in user_profile_platform):
            print("user_platform")
            last_rec.accepted = False
            last_rec.reason = f"want {user_platform} games but this is not in that platform"
            db.commit()
            return True  # Platform mismatch

    # Check for reject tag mismatches
    print(f'user_reject_tags : {user_reject_tags}')
    # Flatten all tags from user.reject_tags across all categories
    user_reject_genres = user.reject_tags.get("genre", []) if user.reject_tags else []
    last_genre_reject_tag = user_reject_genres[-1] if user_reject_genres else None

    if last_genre_reject_tag and last_rec_genre:
        if any(last_genre_reject_tag.lower() == genre.lower() for genre in last_rec_genre):
            print(f"❌ Last rejected genre '{last_genre_reject_tag}' is present in game's genre: {last_rec_genre}")
            last_rec.accepted = False
            last_rec.reason = f"user recently rejected genre: {last_genre_reject_tag}"
            db.commit()
            return True

    # Loop through feedbacks and update last_rec if any are negative
    for fb in user_game_feedback:
        if isinstance(fb, dict) and fb.get("accepted") is False:
            print("🛑 Feedback: user rejected a game")
            return True  # Trigger new recommendation

    return False  # No new recommendation needed, preferences match
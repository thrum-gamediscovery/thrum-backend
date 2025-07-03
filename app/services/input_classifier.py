import openai
import os
import json
from openai import OpenAIError
from app.db.models.session import Session
from app.db.models.enums import SenderEnum

# Set API Key
openai.api_key = os.getenv("OPENAI_API_KEY")


async def is_intent_override(user_input: str) -> bool:
    """
    Uses GPT to decide if the user is overriding intent and wants a game immediately.

    Returns True if GPT believes the message skips discovery and demands a direct game.
    """
    
    prompt = (
        "You are a classification agent for a game recommendation bot.\n"
        "Your task is to detect if the user's message is a direct request for a game,\n"
        "bypassing all mood/genre/platform questions (called an 'intent override').\n\n"
        f"User message: \"{user_input}\"\n\n"
        "Is this an intent override?\n"
        "Respond with just: true or false."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            temperature=0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        content = response['choices'][0]['message']['content'].strip().lower()
        print(f"content : {content} ::: {'true' in content}")
        return "true" in content

    except Exception as e:
        print("GPT override check failed:", e)
        return False
    
# ✅ Use OpenAI to classify mood, vibe, genre, and platform from free text
async def classify_user_input(session, user_input: str) -> dict | str:
    # Get the last message from Thrum to include as context
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""
    last_game = session.game_recommendations[-1].game if session.game_recommendations else None

    system_prompt = '''
You are a classification engine inside a mood-based game recommendation bot.

Your job is to extract and return the following user profile fields based on the user's input message.  
You must infer from both keywords and tone — even if the user is casual, brief, or vague. Extract even subtle clues.

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

4. genre (string)  
   → e.g., puzzle, horror, racing, shooter, strategy, farming, simulation, narrative, platformer.  
   → Accept synonyms like “scary” = horror, “farming sim” = farming.

5. platform_pref (string)  
   → PC, mobile, Xbox, PlayStation, Switch, etc.  
   → Detect implied platforms too: “on the train” = mobile, “on my couch” = console.

6. region (string)  
   → Location like India, US, UK, etc.  
   → Phrases like “I'm in Canada” → "Canada", “I'm from the UK” → "UK".

7. age (string)  
   → extract age as single number not a range. like 18, 25, 30, 50, etc.
   → from input e.g., "teen", "18-25", "30s", "50+".  
   → If mentioned or implied (e.g., “my kids” = likely 30s+), extract.

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

10. regect_tag (list of strings)  
   → What they dislike. Genres, moods, mechanics, or platforms.  
   → e.g., ["horror", "mobile", "realistic"]  
   → Hints: “I don't like shooters”, “not into mobile games”, “too realistic”.
   → only add anything in regected_tag if it is sure otherwise not

11. game_feedback (list of dicts)  (** strict rule**)
   → if from the user input it is concluded that user does not like the recommended game (just for an example. if user input is "i don't like that" and you infere they actually don't like that game)then in game put the title from the last recommended game, accepted as False, and reason as the reason why they do not like it.
    if from the user input it is concluded that user like the recommended game (just for an example. if user input is "yeah i like that" and you infere they actually like that game)then in game put the title from the last recommended game, accepted as True, and reason as the reason why they like it.
   → If they like the game, put accepted as True and reason as why they like it
   → If they react to specific games with name they mentioned in user input(just for an example. if user input is "i love Celeste" and you infere they actually like that game),then put that title in game, accepted as True or False based on their reaction, and reason as the reason why they like or dislike it.
   → If they react to specific games with like/dislike:
   [
     {
       "game": "Celeste",
       "accepted": false,
       "reason": "too intense for me"
     },
     {
       "game": "Unpacking",
       "accepted": true,
       "reason": "emotional and relaxing"
     }
   ]

---

🧠 RULES:
- If a field cannot be inferred, return "None" (or [] for lists, null for booleans).
- DO NOT include any explanation.
- Always return strictly valid JSON.

🛠️ OUTPUT FORMAT (Strict JSON):

{
  "name": "...",
  "mood": "...",
  "game_vibe": "...",
  "genre": "...",
  "platform_pref": "...",
  "region": "...",
  "age": "...",
  "story_pref": true/false,
  "playtime_pref": "...",
  "regect_tag": ["..."],
  "game_feedback": [
    {
      "game": "...",
      "accepted": true/false/None,
      "reason": "..."
    }
  ]
}

🧠 HINTS:
- If a field is not mentioned or cannot be inferred, return "None" (or [] for lists).
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
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ],
            temperature=0
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
                "regect_tag": [],
                "game_feedback": []
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
    prompt = f"""
You're Thrum — a fast, friendly, emotionally smart game recommender.

The user was recommended the game: *{game_title}*
last thrum question : {last_thrum_reply}
user reply : "{user_reply}"

Your task is to classify whether user is satisfied with that game or not, if you find that input is sounds like user want other game and then return "want_another" 
and if the user input is like they like the recommended game or they are satisfy with that game and it is not sounds like they want other game then return "dont_want_another" as intent.
and the most important thing is that you must infere user input by referencing the last thrum question.
Return only a valid JSON object like this:

{{
  "intent": "want_another" | "dont_want_another"
}}

Rules:
- If they liked it and want another → "want_another"
- If they liked it but don’t want more → "dont_want_another"
- If they disliked it or said no → "want_another"
- If they’re vague, silent, or unsure → "dont_want_another"

Only return valid JSON. No explanation.
"""

    response = await openai.ChatCompletion.acreate(
        model="gpt-4.1-mini",
        temperature=0.3,
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

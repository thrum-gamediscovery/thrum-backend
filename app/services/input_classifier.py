import openai
import os
import json
import re
from datetime import datetime
from openai import OpenAIError
from app.db.models.session import Session
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.enums import SenderEnum

from app.services.central_system_prompt import THRUM_PROMPT

# Set API Key
openai.api_key = os.getenv("OPENAI_API_KEY")
model= os.getenv("GPT_MODEL")

client = openai.AsyncOpenAI()

# Define updated intents
intents = [
    "Greet",
    "Phase_Discovery",
    "Request_Similar_Game",
    "Request_Quick_Recommendation", 
    "Reject_Recommendation", 
    "Inquire_About_Game", 
    "Give_Info", 
    "Share_Game", 
    "Opt_Out", 
    "Other_Question", 
    "Confirm_Game",
    "want_to_share_friend"
    "Other",
    "Bot_Error_Mentioned",
    "About_FAQ"
]

async def classify_user_intent(user_input: str, session):
    from app.services.session_memory import SessionMemory
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
  
    
    final_system_prompt =  f"""
USER MEMORY & RECENT CHAT:
{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

**You are intent classifier**
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
  - Phase_Discovery must be True when Thrum's last reply is a greeting message, and according the thrum's question user does not ask directly game recommendation or not asking for a game suggestion immediately, but rather giving information about their preferences or interests. if it is not clear that user want game immediately in the reply of greeting message then Phase_Discovery must be True.
  - Do not trigger Phase_Discovery if the user input is just random stuff not looking like answer in anyway of the thrum's question.
  - Phase_Discovery must be set to True when Thrum's last reply is a greeting and the user's response is not a direct request for a game suggestion. If the user’s reply does not clearly ask for a game, or simply shares a preference, mood, or gives a neutral/curious reply, always set Phase_Discovery to True.
  - if Thrum's last message is about asking user's favourite game or asking about their preferences and user is giving the information about that then Phase_Discovery must be True, even if user input is containing the game title the Phase_Discovery must be true.(carefully check that when user provide the game name it must be ans of thrum's question of favourite game.)
  
- **Request_Similar_Game**: Triggered when the user asks for a game similar to one they already like or have played. This intent is activated when the user explicitly asks for a game that is similar to their preferences or past games. this intent is specifically for when the user is looking for a game that matches their previous interests or experiences, not just any game recommendation.

- **Request_Quick_Recommendation**: Triggered when the user explicitly asks for a game suggestion at that time, OR asks for a suggestion on a different platform than last recommended, or asking for a game directly like "suggest a game","want a game", etc.
- true ONLY when user clearly asks for a new game suggestion.
- if user just looking for some specific game then do not trigger it(for eg, user say im'm looking for genre, or any scpecification then do not trigger it.). untill they want game immediately, or directly ask for a game suggestion.
- Do not Trigger it as True when user is not asking for a new game recommendation and user just giving information about game or user input is just an statement which is not include the intent for new or other game.
- Do NOT trigger if user is just inquiring about platform availability or requesting a store/platform link for a specific game.
- "for mobile?" or "on Android?" only triggers if it's an explicit request for a new rec, not just checking if a game is available.
  This intent is activated for phrases like:
    - "give me a game"
    - "suggest one for me"

- **Request_Quick_Recommendation**: Triggered when the user explicitly asks for a game suggestion at that time, OR asks for a suggestion on a different platform than last recommended, or asking for a game directly like "suggest a game","want a game", etc.
- true ONLY when user clearly asks for a new game suggestion.
- if user just looking for some specific game then do not trigger it.(for eg, user say im'm looking for genre, or any scpecification then do not trigger it.)
- Do not trigger this intent if the user is just giving information about a game or if the user is just stating something that does not include the intent for new or other game.
- Do not Trigger it as True when user is not asking for a new game recommendation and user just giving information about game or user input is just an statement which is not include the intent for new or other game.
- Do NOT trigger if user is just inquiring about platform availability or requesting a store/platform link for a specific game.
- "for mobile?" or "on Android?" only triggers if it's an explicit request for a new rec, not just checking if a game is available.
  This intent is activated for phrases like:
    - "give me a game"
    - "suggest one for me"

- **Reject_Recommendation**: Triggered when the user directly rejects the game suggested in the previous response.
  This can be a clear refusal such as "Not that one," "I don’t like this," or any other similar phrases with same intent that reject the previously suggested game.
  - Be especially strict and accurate in detecting when the user is rejecting a game. Do not miss it, even if the language is casual, short, or slang. Always classify these as Reject_Recommendation.
  - if user is giving the reason why they are rejecting the game then it, then at that time Request_Quick_Recommendation should be True or triggered, as user alrady provide the reason why they are rejecting the game. but if they do not provide the reason and just mean they did not like without reason then Request_Quick_Recommendation should be False and Reject_Recommendation must be true or triggered.
  - If the user’s rejection is not strongly negative, but instead is neutral or based on context. For example, the user might say “not right now” (meaning they’re interested but just not at the moment) or “too expensive” (meaning the price, not the game itself, is the issue). In these situations, the system should recognize that it’s not a true dislike of the game, but rather a situational or soft rejection, so this should not trigger Reject_Recommendation.
  - If thrum's last message was to ask what they did not like about the game and user is giving the reason why they did not like the game then Request_Quick_Recommendation should be True or triggered.

- **Inquire_About_Game**: must be set to true if:
    1. The user message contains the title of a specific game (matching the game catalog) then Inquire_About_Game should True, must check if user providing the game title when thrum's last message is about asking for their favorite game then "Phase_Discovery" should True. OR
    2. The user asks for a link, platform, or store for any game, even if the main question is about the link.
    3. if the user has been asked that they want more information about game(in different phrase or words with this intention) and if they positively respond about they want the more information(not they like the game but want to know more) or they want to know more(then Inquire_About_Game must be true , Confirm_Game must be false in that case.), indicating they want to know more about it. The user expresses a desire to know more about a game, such as its features, gameplay mechanics, or storyline. must triggered when the user lazyly says positive response but not confirming the game (last thrum messge to recommend a game).

- **Give_Info**: Triggered when the user provides information about their preferences, such as genre, mood, or game style. This includes providing keywords or short phrases like "action", "chill", or "strategy". The response should classify when the user provides any kind of self-description related to their preferences. if last thrum message is to ask about what user likes or dislikes about the game and user is giving the information about that then Give_Info should not be triggered.
  - If the user’s reply relates to Thrum’s previous question about preferences or interests—whether the user provides specific details, indicates uncertainty, or chooses not to answer—map the response to the question and set Give_Info to true, unless a direct game request is made.
  - If the user input contains any information about preferred genre, vibe, mood, or platform, and does not specifically ask for a game, then Give_Info must be set to true.

- **Opt_Out**: Triggered when the user opts out or indicates they no longer wish to continue the conversation. This intent is activated when phrases like "I'm done," "Stop," "Not interested," or "Leave me alone" are used to end or discontinue the conversation.

- **Confirm_Game**: Triggered when the user confirms their interest in a game that was previously recommended(if input is just "yes" then it might be for know more information depends on previous thrum message in that case Inquire_About_Game should be true.). The confirmation could be something like "like that game" or "I like that game." or "like that one" or similar to that, This is explicitly confirming the previous game suggestion, meaning that the user is showing interest in the exact game Thrum recommended they liked that. also triggered when user is giving the reason why they liked the game or what they liked about the game(so check thrum's last message and user's reply).

- **want_to_share_friend**: Triggered when the user expresses a desire to share Thrum with friends. This intent is activated when the user says something like "I want to share this with my friends".
  - If thrum's last message is about asking about soft sentence that suggests they might want to share Thrum with some of their friends, and the user responds positively or expresses interest in sharing Thrum with friends, then this intent(want_to_share_friend) must be set to true.

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

- **Low_Effort_Response** : Triggered only when the user’s reply is clearly minimal, vague, or low-effort (e.g., "ok", "cool", "nice", "thanks", "like"), and does not provide meaningful or relevant information to Thrum’s last question. This includes one-word or very short replies that show disengagement, politeness without substance, or boredom. Be very careful not to trigger this intent when the user’s short reply is a valid, meaningful answer—for example, a one-word genre ("Action"), platform ("PC"), mood ("Chill"), or any direct answer that clearly relates to Thrum’s previous question. Only assign this intent if the input truly lacks helpful content or fails to move the conversation forward. only Trigger when user input is very short, vague, or low-effort, for about two or more times.(from chat history). Use this intent to trigger a warm, friendly nudge that encourages more engagement, without sounding robotic or pushy.

- **Other_Question**: Triggered when the user asks a question that is not directly related to game or recommendation.

- **Other**:
  Must Triggerd when chat is not relted to any game or game recommendation, or when user is giving information about game or user input is just an statement which is not include the intent for new or other game. so must check the user input and thrum's last message.
  Triggered for any input that doesn’t match the above categories, or when user is input is just an statement which shares some information about the game.
  This could include irrelevant or non-conversational responses, random input, or statements that do not fall within the intent framework.
---
**Guidelines:**
- Focus on the **current context and user emotion**—is the user happy, confused, annoyed, or giving feedback? Reflect that in the intent.
- Classify negative feedback about the bot as `Bot_Error_Mentioned` to enable better handling and recovery.
- Use `Other_Question` only for meta-questions about user or bot.
- Use `Other` **only** for irrelevant or off-topic input.
- **Only one intent can be true per turn.** All others must be false.
---
### Steps for classification:
1. **Must Look at Thrum’s last response** and consider the context — did Thrum greet the user, recommend a game, or ask for more information?
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
    "Request_Similar_Game": true/false,
    "Reject_Recommendation": true/false,
    "Inquire_About_Game": true/false,
    "Give_Info": true/false,
    "Share_Game": true/false,
    "Opt_Out": true/false,
    "Other_Question": true/false,
    "Confirm_Game": true/false,
    "want_to_share_friend": true/false,
    "Other": true/false,
    "Bot_Error_Mentioned": true/false,
    "About_FAQ": true/false
}}
"""
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": final_system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ],
            temperature=0,
        )
        res = response.choices[0].message.content
        # Try parsing the LLM output into JSON
        try:
            result = json.loads(res)
            print("user_input: ", user_input)
            print(f"intent : {result}")
            return result
        except Exception as e:
            print(":x: GPT classification failed:", e)
            # Return a default response if there is an error
            return {
                "Greet": False,
                "Phase_Discovery": False,
                "Request_Similar_Game": False,
                "Request_Quick_Recommendation": False,
                "Reject_Recommendation": False,
                "Inquire_About_Game": False,
                "Give_Info": False,
                "Share_Game": False,
                "Opt_Out": False,
                "Other_Question": False,
                "Confirm_Game": False,
                "want_to_share_friend": False,
                "Other": True,
                "Bot_Error_Mentioned": False,
                "About_FAQ": False
            }
    except OpenAIError as e:
        print(f"⚠️ OpenAI Error: {e}")
        return {
                "Greet": False,
                "Phase_Discovery": False,
                "Request_Similar_Game": False,
                "Request_Quick_Recommendation": False,
                "Reject_Recommendation": False,
                "Inquire_About_Game": False,
                "Give_Info": False,
                "Share_Game": False,
                "Opt_Out": False,
                "Other_Question": False,
                "Confirm_Game": False,
                "want_to_share_friend": False,
                "Other": True,
                "Bot_Error_Mentioned": False,
                "About_FAQ": False
            }


    
# ✅ Use OpenAI to classify mood, vibe, genre, and platform from free text
async def classify_user_input(session, user_input: str) -> dict | str:
    from app.services.session_memory import SessionMemory
    # Get the last message from Thrum to include as context
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""
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

    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    final_system_prompt = f'''
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

2. mood (list of strings)  
   → Emotion or energy. e.g., relaxed, excited, tired, focused, bored, sad, hyped.  
   → Use tone, emojis, or even context like “long day” → “tired”.  
   → If unsure, return "None".
   → if user input contains mood from the given list, then directly return from this [happy,sad,angry,anxious,relaxed,excited,bored,focused,restless,playful,cozy,lonely,confident,insecure,curious,frustrated,romantic,tired,energized,melancholic,nostalgic,competitive,peaceful,social,introverted,extroverted,motivated,lazy,grateful,moody,overwhelmed,optimistic,pessimistic,calm,stressed,hopeful,ashamed,proud,guilty,shy,fearful,inspired,jealous,empathetic,creative,apathetic,sarcastic,weird,neutral,excitable]
   
3. game_vibe (list of strings)  
   → How the game should feel: relaxing, intense, wholesome, adventurous, spooky, cheerful, emotional, mysterious, dark, fast-paced, thoughtful.
   → If not mentioned, return "None".
   → if user directly give vibe then directly return from this [adventurous,beautiful,challenging,cheerful,comedic,contemplative,creative,dark,destructive,disconcerting,energetic,epic,exciting,ingenious,laidback,liberating,light-hearted,morbid,mysterious,optimistic,"power fantasy",relaxing,sentimental,serious,surreal,suspenseful,tragic,wholesome]

4. genre (list of strings)  
  → e.g., puzzle, horror, racing, shooter, strategy, farming, simulation, narrative, platformer.  
  → Select exactly one genre from this list only: card game, action, adventure, driving, fighting, mmo, music, other, party, platform, puzzle, racing, "real-world game", role-playing, shooter, simulation, sports, strategy, "virtual life", and **newly identified genres based on user input**.  
  → Accept and map common synonyms **based on detected gameplay structure**. If the user refers to specific activities or gameplay styles, match them dynamically. For example:
    - “scary” → horror
    - “farming sim” → simulation
    - “story-based” → adventure
    - “battle” → fighting
    - “online” → mmo
    - “music” → music
    - “car” or “racing” → racing or driving
    - new genre added dynamically based on user input
  → If not explicitly mentioned or if input cannot be mapped directly, return "None".  
  → This classification system is flexible and adapts to new terms, ensuring that any user-specific genre or activity is categorized appropriately without manual mapping.  

  → The goal is to identify what *feels* like a genre by detecting **player interaction patterns**, such as:
    - **Exploration, Racing, Fighting, Simulation**, etc.
  → Do not rely on hardcoded genre names but instead dynamically map based on user language and gameplay description.

5. favourite_games (list of strings)
→ Only return the exact title of the game they refer to as their favorite or most liked.
→ If the user does not mention a favorite, return "None".
→ If the user mentions more than one, choose the one they describe most positively.
→ Do not infer, guess, or include games that are not explicitly mentioned as a favorite.
→ Your response must only be the game title as a string (no explanation or extra text).
→ If unclear or not mentioned, return "None".
  
6. platform_pref (list of strings)
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

7. region (string)  
   → Location like India, US, UK, etc.  
   → Phrases like “I'm in Canada” → "Canada", “I'm from the UK” → "UK".
   → If not mentioned, return "None".

8. age (string)  
   → extract age as single number not a range. like 18, 25, 30, 50, etc.
   → from input e.g., "teen", "18-25", "30s", "50+".  
   → If mentioned or implied (e.g., “my kids” = likely 30s+), extract.
   → If not mentioned or cannot be inferred, return "None".

9. story_pref (boolean)  
   → True if they like games with story. False if they avoid it.  
   → “I want something with a good story” = True.  
   → “I skip cutscenes” = False.  
   → If unclear, return null.

10. playtime_pref (list of strings)(** strict rule**)
   → if the user input is like user not like the recommended game then 
   → When they usually play: evenings, weekends, mornings, after work, before bed, “in short breaks”.  
   → Detect direct and subtle mentions.  
     Examples:
     - “Usually in the evenings” → "evenings"  
     - “Weekend gamer” → "weekends"  
     - “On the train” → "commute"  
     - “Before bed” → "night"
   → If not mentioned, return "None".

11. reject_tags (list of strings)  
   → What they dislike. Genres, moods, mechanics, or platforms.  
   → e.g., ["horror", "mobile", "realistic"]  
   → Hints: “I don't like shooters”, “not into mobile games”, “too realistic”.
   → add anthing in reject_tag when user say i dont like this never when user talk like this is not in game.
   → only add anything in reject_tag if it is sure otherwise not
   → If not mentioned, return [].

12. game_feedback (list of dicts)  (** strict rule**)
   → if from the user input it is concluded that user does not like the recommended game (just for an example. if user input is "i don't like that" and you infere they actually don't like that game)then in game put the title from the last recommended game, accepted as False, and reason as the reason why they do not like it.
   → if from the user input it is concluded that user like the recommended game (just for an example. if user input is "yeah i like that" and you infere they actually like that game)then in game put the title from the last recommended game, accepted as True, and reason as the reason why they like it.
   → You must set `"accepted": false` only and only if the user **directly says** they do not like that game (using clear language about the game itself).
   → Never set `"accepted": false` if the user rejects only a genre, platform, or mood (for example, saying "not in the mood for strategy games" or "I don't play on Xbox" must not be recorded as game feedback).
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

13. find_game(title of the game)(string)
   → if user is asking for a specific game title or name in last message, then put that game title in find_game variable
   → if user is specifying that find me game by giving the title of the game in last message then put that game in find_game variable
   → if user want specific game and give name or title for recommend (if user i saying something like"i don't like xyz game" then dont add that in this, only add when you find user want this specific game or want to know about this game)
   → if user do not specify game title but looking like user is inquiry about ame or check avilability of any then return last recommend game's title.
   → if user is not specifying any game title but chat is about game then return last recommend game's title.
   → return just one title of that game which user specify for recommend not list
   → If user not specify about game or title then strictly take last game title.
   → If not, return "None".
   
14. gameplay_elements (list of strings)
  → Focus on GAMEPLAY ELEMENT and structural features that the user describes or wants.
  → Include any mention of core actions, progression systems, advancement, linearity, perspective, player control, interaction loops, or feedback style.
  → Extract every word or phrase about how the player interacts with the game, what actions they take, and how gameplay is experienced or structured.
  → Consider any description of what makes the game feel unique, active, hands-on, or what the player actually does in the game.
  → Do NOT include reasons for playing (that goes in preferred_keywords), and do not skip implied ELEMENT.
  → Return every relevant mechanic, structure, or action as an array of strings; if not present, return [].

15. preferred_keywords (list of strings)
  → Focus on PLAYER MOTIVATION, emotional needs, and preferences for game experience.
  → Include all user mentions of desired game vibe, complexity, visual style, theme, emotional fit, social setting, cognitive style, intensity, or any reason for wanting a specific type of game.
  → Extract every word or phrase that describes why the user wants to play — their mood, goals, feelings, or what makes a game appealing to them.
  → Look for anything that explains the user’s ideal experience, even if only suggested through adjectives, tone, or feelings.
  → Do NOT include game ELEMENT (those go in gameplay_elements); capture only motivation and preference concepts.
  → Return all preference and motivation words or phrases as an array; if not present, return [].

16. disliked_keywords (list of strings)
  → Focus on all NEGATIVE experiences, unwanted features, or game elements the user wishes to avoid.
  → Include anything the user describes as frustrating, boring, stressful, unappealing, annoying, or not enjoyable.
  → Extract every word or phrase about bad gameplay patterns, disliked mechanics, monetization issues, emotional triggers, or negative play experiences.
  → Look for any mention of what the user does NOT like in games, even if it’s subtle or implied (such as “no pay-to-win,” “hate grinding,” “too easy,” etc.).
  → Do NOT skip implied dislikes or features the user reacts negatively to, even if not directly stated as “dislike.”
  → Return all such terms as an array of strings; if not present, return [].

  17. played_yet (boolean or "None")
  → Determine whether the user has actually played the game or is only reacting to it, based strictly on their current input.
  → Return true if the user’s message clearly indicates personal gameplay experience through their words, tone, or described actions.
  → Return false if the user is only commenting based on impressions, appearance, or what they have heard about the game, without indicating they have played it.
  → If the input does not refer to a specific game, or if it cannot be determined from the input, return "None".

---

🧠 RULES:
- If a field cannot be inferred, return "None" (or [] for lists, null for booleans).
- Never guess or fill in with placeholders. If not sure, use "None".
- DO NOT include any explanation.
- Always return strictly valid JSON.

🛠️ OUTPUT FORMAT (Strict JSON):

{{
  "name": "...",
  "mood": ["..."],
  "game_vibe": ["..."],
  "genre": ["..."],
  "favourite_games": ["..."],
  "platform_pref": ["..."],
  "region": "...",
  "age": "...",
  "story_pref": true/false/null,
  "playtime_pref": ["..."],
  "reject_tags": ["..."],
  "game_feedback": [
    {{
      "game": "...",
      "accepted": true/false/None,
      "reason": "..."
    }}
  ],
  "find_game":"...",
  "gameplay_elements": ["..."],
  "preferred_keywords": ["..."],
  "disliked_keywords": ["..."],
  "played_yet": true/false/None
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

User current reply:
"{user_input}"

last recommended game:
"{last_game}"

- Strictly extract the fields above from the user current reply not from USER MEMORY & RECENT CHAT (USER MEMORY & RECENT CHAT is just for reference).
- classify based on user's reply and thrum's message (undersand it deeply what they want to say.)
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
            res = response.choices[0].message.content
            result = json.loads(res)
        except Exception:
            result = {
                "name": "None",
                "mood": [],
                "game_vibe": [],
                "genre": [],
                "favourite_games": [],
                "platform_pref": [],
                "region": "None",
                "age": "None",
                "story_pref": "None",
                "playtime_pref": "None",
                "reject_tags": [],
                "game_feedback": [],
                "find_game":"None",
                "gameplay_elements": [],
                "preferred_keywords": [],
                "disliked_keywords": [],
                "played_yet": False
            }

        print(f"Classification Result: {result}")
        return result

    except OpenAIError as e:
        print(f"⚠️ OpenAI Error: {e}")
        result = {
                "name": "None",
                "mood": [],
                "game_vibe": [],
                "genre": [],
                "favourite_games": [],
                "platform_pref": [],
                "region": "None",
                "age": "None",
                "story_pref": "None",
                "playtime_pref": "None",
                "reject_tags": [],
                "game_feedback": [],
                "find_game":"None",
                "gameplay_elements": [],
                "preferred_keywords": [],
                "disliked_keywords": [],
                "played_yet": False
            }

    print(f"Classification Result: {result}")
    return result

    

async def analyze_followup_feedback(user_reply: str, session) -> dict:
    from app.services.session_memory import SessionMemory
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
If the user input sounds like they like the recommended game or are satisfied with it (and it does NOT sound like they want another game), return "game_accepted" as intent.
If the user is vague, silent, or unclear, default to "dont_want_another".

**Examples:**
- User: "nah, show me something else" → {{ "intent": "want_another" }}
- User: "not really my thing" → {{ "intent": "want_another" }}
- User: "perfect, this is what I was looking for" → {{ "intent": "game_accepted" }}
- User: "I'll check it out" → {{ "intent": "game_accepted" }}
- User: "okay" → {{ "intent": "dont_want_another" }}
- User: "better. I'll check it out" → {{ "intent": "game_accepted" }}
- User: "thx" → {{ "intent": "game_accepted" }}

Rules:
- If they liked it and want another → "want_another"
- If they liked it and will try it → "game_accepted"
- If they liked it but don’t want more → "dont_want_another"
- If they disliked it or said no → "want_another"
- If they’re vague, silent, or unsure → "dont_want_another"

Return only a valid JSON object with one key "intent":
{{
  "intent": "want_another" | "dont_want_another" | "game_accepted"
}}

Do NOT use triple backticks, code fences, or any markdown formatting.
Your response must be pure JSON, not wrapped in any formatting.
If you add backticks, markdown, or any extra text, it is a mistake.
Example of correct output:
{{
  "intent": "game_accepted"
}}
"""

    response = await client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def have_to_recommend(db: Session, user, classification: dict, session) -> bool:
    # Retrieve the last game recommendation for the user in the current session
    last_rec = db.query(GameRecommendation).filter(
        GameRecommendation.user_id == user.user_id,
        GameRecommendation.session_id == session.session_id
    ).order_by(GameRecommendation.timestamp.desc()).first()
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
    user_profile_platform = user.platform_prefs.get(today, []) if user.platform_prefs else []


    # Check if the genre in classification matches the user's profile genre
    if user_genre:
        # Check if any genre in user_profile_genre matches the genres in last_rec_genre
        if user_profile_genre and not any(user_genre.lower() in genre.lower() for genre in last_rec_genre):
            last_rec.accepted = False
            last_rec.reason = f"likes specific {user_genre} games"
            db.commit()
            return True  # Genre mismatch, new recommendation needed
    
    # # Check if the mood in classification matches the user's last mood
    # if user_mood:
    #     today = datetime.utcnow().date().isoformat()
    #     if user.mood_tags.get(today) != last_rec_mood:
    #         last_rec.accepted = False
    #         last_rec.reason = f"want game of specific {user_mood}"
    #         db.commit()
    #         return True  # Mood mismatch, new recommendation needed

    # Check if the platform preference matches any of the platforms in last_rec_platforms
    if user_platform:
        if user_profile_platform and not any(p.lower() in [lp.lower() for lp in last_rec_platforms] for p in user_profile_platform):
            last_rec.accepted = False
            last_rec.reason = f"want {user_platform} games but this is not in that platform"
            db.commit()
            return True  # Platform mismatch

    # Check for reject tag mismatches
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

    return False  # No new recommendation needed, preferences matchs
from app.services.session_memory import confirm_input_summary
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.session import SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import Boolean
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply
import json
from sqlalchemy.orm.attributes import flag_modified
from app.services.session_memory import SessionMemory
from app.services.general_prompts import GLOBAL_USER_PROMPT
from app.services.central_system_prompt import THRUM_PROMPT

async def handle_confirmation(session):
    return await confirm_input_summary(session)

async def handle_confirmed_game(db, user, session):
    """
    Handle when user accepts a game recommendation.
    
    Following client specs:
    - 1-2 lines max
    - Match user's emotional tone
    - Ask them to share back later (creates emotional stickiness)
    - Never say "hope you enjoy" or "thanks"
    - Keep it playful, curious, or chill based on their tone
    """
    game_title = session.last_recommended_game
    tone = session.meta_data.get("tone", "friendly")
    
    # Get memory context for personalization
    memory_context = ""
    if session.meta_data:
        name = session.meta_data.get("name", "")
        platform = session.meta_data.get("platform", "")
        genre_likes = session.meta_data.get("genre_likes", [])
        genre_dislikes = session.meta_data.get("genre_dislikes", [])
        
        memory_context = f"""
Memory context:
- Name: {name}
- Platform: {platform}
- Likes: {genre_likes}
- Dislikes: {genre_dislikes}
- User tone: {tone}
"""
    
    if not session.meta_data.get("played_yet", False):
        # First time accepting this game
        user_prompt = f"""
{THRUM_PROMPT}

SITUATION: User just accepted **{game_title}**.
{memory_context}

BEHAVIOR RULES:
→ 1–2 lines max. Keep it playful, curious, or chill — whatever matches their tone ({tone}).
→ Never say "I'll check in" or "I'll follow up later" — that's fake-friend energy.
→ Always invite *them* to share back later — keep it light, not needy, like how friends would ask.
→ You can mention there might be more like this — "If that one clicks, there's more where that came from" — but never pitch.

WHAT NEVER TO DO:
❌ Don't say "Hope you enjoy" or "Thanks for accepting" — too robotic.
❌ Don't ask "Want another?" — that's system logic.
❌ Don't suggest another game immediately.
❌ Don't recycle emoji, phrasing, or sentence rhythm from earlier replies.

VIBE: Like a friend who just got a nod and smiles — warm, curious, emotionally vivid.
You're not closing the chat — you're leaving the door open by asking the kind of question that makes someone want to answer later.

Examples of the invite-back style (don't copy exactly):
- "Let me know how it hits when you've played it."
- "Curious what you think after a few minutes in."
- "Lmk if it actually slaps or just looks good 😅"

Match their {tone} tone and create a moment that feels like a real friend celebrating with them.
""".strip()
        
        # Mark that we've handled first acceptance
        if session.meta_data is None:
            session.meta_data = {}
        session.meta_data["played_yet"] = True
        
    else:
        # They've played and are giving feedback
        if session.meta_data.get("ask_confirmation", True):
            user_prompt = f"""
{THRUM_PROMPT}

SITUATION: User confirmed they liked **{game_title}**.
{memory_context}

Ask in a warm, conversational way what they enjoyed most about it.
→ Keep question short—just 1-2 lines
→ Match their {tone} tone
→ Vary phrasing each time; never repeat previous wording
→ Be genuinely curious like a friend who wants to hear the story
→ Don't suggest a game on your own if there is no game found

Return only the new user-facing message.
""".strip()
            
            session.meta_data["ask_confirmation"] = False
            
        else:
            user_prompt = f"""
{THRUM_PROMPT}

SITUATION: User confirmed they liked **{game_title}**.
{memory_context}

Reply in a warm, humble manner expressing happiness that they liked your recommendation.
→ Keep message open and engaging
→ Avoid language that closes or ends conversation
→ No more than 2 sentences or 25 words
→ Match their {tone} tone
→ Make it feel like a friend who's genuinely happy their suggestion worked out

Return only the new user-facing message.
""".strip()
    
    # Initialize metadata if needed
    if session.meta_data is None:
        session.meta_data = {}
    
    # Set default values
    if "dont_give_name" not in session.meta_data:
        session.meta_data["dont_give_name"] = False
    if 'ask_for_rec_friend' not in session.meta_data:
        session.meta_data['ask_for_rec_friend'] = True
    
    db.commit()
    return user_prompt

async def ask_for_name_if_needed():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).join(Session.user).filter(
        Session.last_thrum_timestamp.isnot(None),
        Session.meta_data["dont_give_name"].astext.cast(Boolean) == False
    ).all()

    for s in sessions:
        s = db.query(Session).filter(Session.session_id == s.session_id).one()
        user = s.user
         # ✅ EARLY SKIP if flag is already True (safety net)
        if s.meta_data.get("dont_give_name", True):
            continue
        if user.name is None:
            delay = timedelta(seconds=15)
            # Check if the delay time has passed since the last interaction
            print(f"Checking if we need to ask for name for user {user.phone_number} in session {s.session_id} ::  dont_give_name  {s.meta_data['dont_give_name']}")
            if now - s.last_thrum_timestamp > delay:
                # Ensure the session meta_data flag is set to avoid re-asking the name
                s.meta_data["dont_give_name"] = True
                s.meta_data["ask_for_rec_friend"] = True
                flag_modified(s, "meta_data")
                db.commit()
                db.refresh(s) 
                print(f"Session {s.session_id} :: Asking for name for user {user.phone_number} :: dont_give_name  {s.meta_data['dont_give_name']}")
                user_interactions = [i for i in s.interactions if i.sender == SenderEnum.User]
                last_user_reply = user_interactions[-1].content if user_interactions else ""
                
                # Ask for the user's name
                response_prompt = (
                    "Generate a polite, natural message (max 10–12 words) asking the user for their name.\n"
                    "The tone should be friendly and casual, without being too formal or overly casual.\n"
                    "Ensure it doesn’t feel forced, just a simple request to know their name.\n"
                    "Output only the question, no extra explanations or examples."
                    "Do not use emoji. Ask like Thrum wants to remember for next time."
                )
                
                reply = await format_reply(session=s, user_input=last_user_reply, user_prompt=response_prompt)
                if reply is None:
                    reply = "what's your name? so I can remember for next time."
                await send_whatsapp_message(user.phone_number, reply)

    db.close()  # Close the DB session
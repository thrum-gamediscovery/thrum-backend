from app.services.session_memory import confirm_input_summary
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.session import SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import Boolean
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply
from sqlalchemy.orm.attributes import flag_modified
from app.db.models.game import Game
from app.db.models.game_platforms import GamePlatform
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
    game_id = db.query(Game).filter_by(title=game_title).first().game_id if game_title else None
    tone = session.meta_data.get("tone", "friendly")
    user_input = session.interactions[-1].content if session.interactions else ""
    platform_rows = db.query(GamePlatform.platform).filter_by(game_id=game_id).all()
    platform_list = [p[0] for p in platform_rows] if platform_rows else []
    # Get user's preferred platform (last non-empty entry in the array)
    platform_preference = None
    if session.platform_preference:
        non_empty = [p for p in session.platform_preference if p]
        if non_empty:
            platform_preference = non_empty[-1]
    else:
        gameplatform_row = db.query(GamePlatform).filter_by(game_id=game_id).first()
        platform_preference = gameplatform_row.platform
    # Fetch the platform link for that game and platform
    platform_link = None
    if platform_preference:
        gp_row = db.query(GamePlatform).filter_by(game_id=game_id, platform=platform_preference).first()
        if gp_row:
            platform_link = gp_row.link  # This is the URL/link for the user's preferred platform
    else:
        print(f"`No preferred platform found for user #############`")
        gp_row = (
            db.query(GamePlatform)
            .filter(GamePlatform.game_id == game_id, GamePlatform.link.isnot(None))
            .first()
        )
        platform_link = gp_row.link if gp_row else None
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
            {GLOBAL_USER_PROMPT}\n
            ---
            THRUM — GAME LIKED FEEDBACK
            User said: "{user_input}"
            Tone: {tone}
            → The user liked the game you recommended.
            → Respond like a close friend — curious, warm, and totally in the moment.
            → First: ask what made it click — gameplay, tone, mechanics, art, pace — whatever fits. Make it sound emotionally real, not scripted.
            → Mirror their tone: dry? Teasing? Hyped? Chill? Match it naturally.
            → Do NOT reuse lines, phrasing, or emojis from earlier. Every reply must be new in rhythm and structure.
            → No structured list — just talk like someone who *gets* them.
            → Once they reply, reflect back in Draper style — warm, sharp, and emotionally tuned to what they shared — and slide the follow-up into the same message, keeping the rhythm natural and human:
            • If platform is known: casually offer a direct link ("Wanna play it on {platform_preference}? Here’s where to grab it.")  
            - Platform link: {platform_link if platform_link else "No link available"}
            • If platform is unknown: offer 1–2 likely platform options based on availability. Ask like a friend who’s just excited to help.
                Examples:
                - “Think it’d slap harder on mobile or Game Pass?”
                - “Wanna try it on Steam or Switch?”
            :star2: Goal: Make them feel seen. Use this moment to bond deeper — and casually invite them to play if the vibe feels open.
        """.strip()
        
        # Mark that we've handled first acceptance
        if session.meta_data is None:
            session.meta_data = {}
        session.meta_data["played_yet"] = True
        
    else:
        # They've played and are giving feedback
        if session.meta_data.get("ask_confirmation", True):
            user_prompt = (f"""
                {GLOBAL_USER_PROMPT}\n
                ---
                THRUM — GAME ALREADY PLAYED
                User said: "{user_input}"
                Tone: {tone}
                → The user already played the game you recommended.
                → Ask casually how they felt about it — gameplay, vibe, story, pace — whatever fits. Don’t assume they liked or disliked it.
                → Mirror their tone: dry? nostalgic? hype? Reflect it naturally.
                → NEVER reuse lines, sentence rhythm, or emoji from earlier.
                → Use Draper style — curious, sharp, tuned in emotionally.
                → Once they answer, follow up lightly: ask if they’re open to something similar — a follow-up rec, same vibe, or something adjacent.
                → Don’t ask “do you want another?”
                → Ask like a close friend would:
                - “Want me to find something with that same vibe?”
                - “Wanna see what else kinda hits like that?”
                - “Feel like playing something in that zone again?”
                :star2: Goal: Use their memory as the hook — reflect back emotionally, then glide into a similar recommendation request like a friend who gets their taste.
            """)
            
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
        print("Setting default metadata for session")
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
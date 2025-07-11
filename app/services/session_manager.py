from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session
from app.db.models.user_profile import UserProfile
from app.db.models.enums import SessionTypeEnum, ResponseTypeEnum
from app.services.nudge_checker import detect_user_is_cold  # ✅ import smart tone checker
from app.db.models.enums import SenderEnum

def update_returning_user_flag(session):
    if session.meta_data.get("returning_user") is None:
        if session.meta_data.get("last_interaction"):
            session.meta_data["returning_user"] = True
        else:
            session.meta_data["returning_user"] = False

def is_session_idle(session, idle_minutes=10):
    if not session.interactions:
        return False
    last_time = session.interactions[-1].timestamp
    return (datetime.utcnow() - last_time) > timedelta(minutes=idle_minutes)

# 🧠 Decide session state based on last activity timestamp
def get_session_state(last_active: datetime) -> SessionTypeEnum:
    now = datetime.utcnow()
    if not last_active:
        return SessionTypeEnum.ONBOARDING
    elapsed = now - last_active
    if elapsed > timedelta(hours=48):
        return SessionTypeEnum.COLD
    elif elapsed > timedelta(minutes=30): #elif elapsed > timedelta(hours=11):
        return SessionTypeEnum.PASSIVE
    else:
        return SessionTypeEnum.ACTIVE

# SECTION 5 - SESSION & MEMORY UPDATES
def update_user_mood(user, session, mood_result: str):
    from sqlalchemy.orm.attributes import flag_modified
    today = datetime.utcnow().date().isoformat()
    user.mood_tags[today] = mood_result
    user.last_updated["mood_tags"] = str(datetime.utcnow())
    
    if not session.entry_mood:
        session.entry_mood = mood_result
    session.exit_mood = mood_result

    flag_modified(user, "mood_tags")
    flag_modified(user, "last_updated")
    db.commit()

def add_rejected_game(user, session, game_id: str):
    if str(game_id) not in session.rejected_games:
        session.rejected_games.append(str(game_id))

def add_genre_preference(user, session, genre: str):
    from sqlalchemy.orm.attributes import flag_modified
    today = datetime.utcnow().date().isoformat()
    user.genre_prefs.setdefault(today, [])
    if genre not in user.genre_prefs[today]:
        user.genre_prefs[today].append(genre)
        flag_modified(user, "genre_prefs")

    session.genre = session.genre or []
    if genre not in session.genre:
        session.genre.append(genre)

def reject_genre(user, session, genre: str):
    from sqlalchemy.orm.attributes import flag_modified
    user.reject_tags.setdefault("genre", [])
    if genre not in user.reject_tags["genre"]:
        user.reject_tags["genre"].append(genre)
        flag_modified(user, "reject_tags")

    session.meta_data = session.meta_data or {}
    session.meta_data.setdefault("reject_tags", {"genre": [], "platform": [], "other": []})
    if genre not in session.meta_data["reject_tags"]["genre"]:
        session.meta_data["reject_tags"]["genre"].append(genre)
        flag_modified(session, "meta_data")

# 🔁 Create or update session based on user activity
async def update_or_create_session(db: DBSession, user):
    now = datetime.utcnow()
    last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .order_by(Session.start_time.desc())
        .first()
    )

    if not last_session:
        new_session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            state=SessionTypeEnum.ONBOARDING,
            meta_data={
                "is_user_cold": False,
                "last_interaction": datetime.utcnow().isoformat(),
                "returning_user": False
            }
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    # ✅ Detect if user is cold based on interaction pattern
    is_cold = await detect_user_is_cold(last_session, db)
    last_session.meta_data = last_session.meta_data or {}
    last_session.meta_data["is_user_cold"] = is_cold

    last_active_time = last_session.end_time or last_session.start_time
    elapsed = now - last_active_time

    # 📝 Update session state
    if elapsed > timedelta(hours=48):
        last_session.state = SessionTypeEnum.COLD
    elif elapsed > timedelta(minutes=30):
        last_session.state = SessionTypeEnum.PASSIVE
    else:
        last_session.state = SessionTypeEnum.ACTIVE
        last_session.end_time = now

    db.commit()

    # 🚀 Start new session if cold/passive
    if last_session.state in [SessionTypeEnum.PASSIVE, SessionTypeEnum.COLD]:
        new_session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            state=SessionTypeEnum.ONBOARDING,
            meta_data={
                "is_user_cold": is_cold,
                "last_interaction": datetime.utcnow().isoformat(),
                "returning_user": False
            }
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    # 💡 NEW: Time-based returning_user check (30+ min idle = reengagement)
    last_interaction_time_str = last_session.meta_data.get("last_interaction")
    if last_interaction_time_str:
        try:
            last_interaction_time = datetime.fromisoformat(last_interaction_time_str)
            idle_seconds = (now - last_interaction_time).total_seconds()
            if idle_seconds > 1800:  # 30 minutes
                last_session.meta_data["returning_user"] = True
        except Exception:
            pass  # Fallback in case of invalid format

    last_session.meta_data["last_interaction"] = datetime.utcnow().isoformat()
    update_returning_user_flag(last_session)

    return last_session

# 🎭 Mood shift session handler
def update_or_create_session_mood(db: DBSession, user, new_mood: str) -> Session:
    now = datetime.utcnow()
    last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .order_by(Session.start_time.desc())
        .first()
    )

    if not last_session:
        session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            entry_mood=new_mood,
            exit_mood=new_mood,
            meta_data={"is_user_cold": False}
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    if not last_session.entry_mood:
        last_session.entry_mood = new_mood
        last_session.exit_mood = new_mood
        db.commit()
        return last_session

    if last_session.exit_mood == new_mood:
        last_session.exit_mood = new_mood
        db.commit()
        return last_session

    last_session.exit_mood = new_mood
    db.commit()

    new_session = Session(
        user_id=user.user_id,
        start_time=now,
        entry_mood=new_mood,
        exit_mood=new_mood,
        meta_data={"is_user_cold": False}
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

def is_session_idle_or_fading(session) -> bool:
    now = datetime.utcnow()
    last_time = session.end_time or session.start_time
    minutes_idle = (now - last_time).total_seconds() / 60

    # Smart idle threshold — adapt based on how many user replies exist
    reply_count = len([i for i in session.interactions if i.sender.name == "User"])
    idle_threshold = 3 if reply_count <= 2 else 8

    if minutes_idle > idle_threshold:
        return True

    # Extra check: if is_user_cold is already flagged
    if session.meta_data.get("is_user_cold"):
        return True

    return False

def detect_tone_shift(session) -> bool:
    tones = [
        i.tone_tag for i in session.interactions[-5:]
        if i.tone_tag and i.sender == SenderEnum.User
    ]
    return len(set(tones)) > 1 if len(tones) >= 3 else False

# SECTION 0 - BOOT + ENTRY PHASE
def is_new_user(db, user_id):
    from uuid import UUID
    if isinstance(user_id, str):
        try:
            user_id = UUID(user_id)
        except ValueError:
            return True
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first() is None

def get_time_context():
    hour = datetime.now().hour
    if hour < 6:
        return "early_morning"
    elif hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    elif hour < 21:
        return "evening"
    else:
        return "late_night"

def create_new_session(db: DBSession, user_id: str, platform: str = "WhatsApp") -> Session:
    session = Session(
        user_id=user_id,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        state=SessionTypeEnum.ONBOARDING,
        meta_data={"platform": platform}
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

async def generate_greeting(user: UserProfile, time_context: str) -> str:
    from app.services.dynamic_response_engine import generate_dynamic_response_legacy
    
    context = {
        'phase': 'greeting',
        'time_context': time_context,
        'user_name': user.name,
        'returning_user': bool(user.last_updated)
    }
    
    return await generate_dynamic_response_legacy(context)

async def boot_entry(user_id: str, platform: str = "WhatsApp") -> dict:
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        time_context = get_time_context()

        if is_new_user(db, user_id):
            print(f"👋 New user detected: {user_id}")
            user = UserProfile(phone_number=f"boot_{user_id}", name=None, mood_tags={}, genre_prefs={}, platform_prefs={})
            db.add(user)
            db.commit()
        else:
            from uuid import UUID
            if isinstance(user_id, str):
                try:
                    user_id = UUID(user_id)
                except ValueError:
                    user_id = None
            user = db.query(UserProfile).filter(UserProfile.user_id == user_id).first() if user_id else None

        session = create_new_session(db=db, user_id=user_id, platform=platform)
        greeting = await generate_greeting(user=user, time_context=time_context)

        return {
            "reply": greeting,
            "session_id": session.session_id,
            "user_id": user.user_id,
            "time_context": time_context
        }

    except Exception as e:
        print(f"❌ Boot phase failed: {e}")
        return {
            "reply": "Hey! I'm here if you want to find a good game — just drop a word or how you're feeling.",
            "session_id": None,
            "user_id": user_id,
            "time_context": "unknown"
        }
    finally:
        db.close()

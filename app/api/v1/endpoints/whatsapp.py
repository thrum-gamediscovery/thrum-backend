from fastapi import APIRouter, Form, Depends,Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session as DBSession
from app.db.models.user import User
from app.db.models.session import Session
from app.db.models.interaction import Interaction
from app.db.models.enums import SenderEnum, ResponseTypeEnum
from app.db.deps import get_db
from datetime import datetime
from app.db.models.enums import PlatformEnum
from app.api.v1.endpoints.chat import chat_with_thrum
from app.services.session_manager import update_or_create_session
from app.services.send_feedback_message import send_whatsapp_feedback_message
from app.api.v1.endpoints.chat import ChatRequest

router = APIRouter()

def handle_session_and_chat(request, db, user, Body, reply):
    session = update_or_create_session(db, user)
    request.scope["headers"] = list(request.scope["headers"]) + [
        (b"x-user-id", user.user_id.encode())
    ]
    payload = ChatRequest(user_input=Body)
    chat_with_thrum(request=request, payload=payload, bot_reply=reply, db=db)

@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(request: Request, From: str = Form(...), Body: str = Form(...), db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.phone_number == From).first()
    # Step 1: New user — create profile
    if not user:
        user = User(
            phone_number=From,
            platform=PlatformEnum.WhatsApp,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            genre_interest={},
            mood_history={},
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        reply=":wave: Hi there! Welcome to Thrum (GameDive). What's your name?"
        handle_session_and_chat(request=request, db=db, user=user, Body=Body, reply=reply)
        return PlainTextResponse(reply)
    
    # 2. Ask for name
    print('_____________name_____________',user.name)
    if not user.name:
        user.name = Body.strip()
        db.commit()
        reply = f"Nice to meet you, {user.name}! What kind of games do you enjoy? (e.g., puzzle, racing, RPG)"
        handle_session_and_chat(request=request, db=db, user=user, Body=Body, reply=reply)
        return PlainTextResponse(reply)
    
    # 3. Ask for genre interest
    print('_____________genre_interest___________',user.genre_interest)
    if not user.genre_interest or user.genre_interest == {}:
        genres = [g.strip().lower() for g in Body.split(",")]
        user.genre_interest = {"likes": genres}
        db.commit()
        reply = "Awesome! What’s your current mood? (e.g., bored, relaxed, excited)"
        handle_session_and_chat(request=request, db=db, user=user, Body=Body, reply=reply)
        return PlainTextResponse(reply)
    
    # 4. Ask for mood
    print('_____________mood_history___________',user.mood_history)
    if not user.mood_history or user.mood_history == {}:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        user.mood_history = {today: Body.strip().lower()}
        db.commit()
        reply = ":white_check_mark: Got it! I’ll now start finding a game that matches your vibe. Just type 'suggest game'."
        handle_session_and_chat(request=request, db=db, user=user, Body=Body, reply=reply)
        return PlainTextResponse(reply)
    
    if "suggest game" in Body.lower():
        latest_interaction = (
            db.query(Interaction)
            .filter(Interaction.session.has(user_id=user.user_id))
            .order_by(Interaction.timestamp.desc())
            .first()
        )
        print('latest_interaction >>>>>', latest_interaction)
        if latest_interaction and latest_interaction.response_type == ResponseTypeEnum.GameRec:
            game_name = latest_interaction.game_name or "this game"
        game_name = None
        send_whatsapp_feedback_message(
            user_phone=user.phone_number.replace("whatsapp:", ""),
            game_name=game_name
        )
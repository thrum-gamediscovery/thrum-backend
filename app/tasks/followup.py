# app/tasks/followup.py
from celery import shared_task
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models import Interaction, Session
from app.db.models.enums import ResponseTypeEnum
from app.services.send_feedback_message import send_feedback_followup_message

@shared_task
def send_feedback_followups():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=30)

        interactions = db.query(Interaction).join(Session).filter(
            Interaction.response_type == ResponseTypeEnum.GameRec,
            Interaction.timestamp < cutoff,
            Session.user_feedback == None
        ).all()

        for interaction in interactions:
            user = interaction.session.user  # Access user through session
            game = interaction.game

            if user and user.phone_number:
                send_feedback_followup_message(
                    user_phone=user.phone_number.replace("whatsapp:", ""),
                    message=f"👋 Hey! Did you get a chance to try *{game.name if game else 'the game'}*? Let me know 👍 or 👎!"
                )

    finally:
        db.close()


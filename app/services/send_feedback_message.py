from twilio.rest import Client
from app.core.config import settings

def send_whatsapp_feedback_message(user_phone: str, game_name: str = None) -> str:
    """
    Sends a feedback template to the user via WhatsApp using Twilio Content API.
    Optionally includes the game name in content variables.
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    message = client.messages.create(
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=f"whatsapp:{user_phone}",
        content_sid=settings.TWILIO_FEEDBACK_CONTENT_SID,
    )

    return message.sid
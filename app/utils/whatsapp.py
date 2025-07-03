import requests
import os
from requests.auth import HTTPBasicAuth
from starlette.requests import Request 
from app.db.session import SessionLocal
from app.db.models.user_profile import UserProfile

async def create_request(user_id):
    scope = {
        "type": "http",
        "headers": [(b"x-user-id", str(user_id).encode())],
    }
    return Request(scope)

async def send_whatsapp_message(phone_number: str, message: str):
    from app.api.v1.endpoints.whatsapp import bot_reply 
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

    payload = {
        "From": from_whatsapp_number,
        "To": phone_number,
        "Body": message
    }

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    try:
        response = requests.post(url, data=payload, auth=HTTPBasicAuth(account_sid, auth_token))
        response.raise_for_status()
        print(f"✅ Sent WhatsApp message to {phone_number}")

        try:
            db = SessionLocal()
            user = db.query(UserProfile).filter(UserProfile.phone_number == phone_number).first()
            if user:
                request = await create_request(user.user_id)
                await bot_reply(request=request, db=db, user=user, reply=message)
        except Exception as e:
            print(f"⚠️ Failed to log bot reply: {e}")
    except requests.RequestException as e:
        print(f"⚠️ Failed to send message to {phone_number}: {e}")

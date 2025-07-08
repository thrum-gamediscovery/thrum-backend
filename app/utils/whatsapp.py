import os
import requests
from requests.auth import HTTPBasicAuth
from starlette.requests import Request 
from app.db.session import SessionLocal
from app.db.models.user_profile import UserProfile
import httpx  # If you want to use async HTTP requests

async def create_request(user_id):
    scope = {
        "type": "http",
        "headers": [(b"x-user-id", str(user_id).encode())],
    }
    return Request(scope)

async def send_whatsapp_message(phone_number: str, message: str, sent_from_thrum=True):
    from app.api.v1.endpoints.whatsapp import bot_reply

    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

    # ✅ Ensure proper formatting for WhatsApp numbers
    if not phone_number.startswith("whatsapp:"):
        phone_number = f"whatsapp:{phone_number.strip()}"

    print(f"📞 Sending WhatsApp message FROM {from_whatsapp_number} TO {phone_number}")
    print(f"💬 Message: {message}")

    payload = {
        "From": from_whatsapp_number,  # should be like 'whatsapp:+14155238886'
        "To": phone_number,            # should be like 'whatsapp:+91xxxxxxx'
        "Body": message.strip()
    }

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    try:
        async with httpx.AsyncClient() as client:  # Async request
            response = await client.post(url, data=payload, auth=(account_sid, auth_token))
            print(f"🔄 Raw response: {response.status_code}")
            print(f"🔍 Twilio response text: {response.text}")

            response.raise_for_status()  # will throw error for 400, 401, etc.
            print(f"✅ Sent WhatsApp message to {phone_number}")

            # Log bot reply if sent from Thrum
            try:
                # Use synchronous session handling here
                db = SessionLocal()  # Use synchronous session (no async with here)
                user = db.query(UserProfile).filter(UserProfile.phone_number == phone_number).first()
                if user and sent_from_thrum:
                    request = await create_request(user.user_id)
                    await bot_reply(request=request, db=db, user=user, reply=message)
            except Exception as e:
                print(f"⚠️ Failed to log bot reply: {e}")

    except requests.RequestException as e:
        print(f"❌ Failed to send message to {phone_number}: {e}")
        if 'response' in locals():
            print(f"🔍 Twilio response: {response.status_code} → {response.text}")

import os
import httpx
from starlette.requests import Request

async def create_request(user_id):
    scope = {
        "type": "http",
        "headers": [(b"x-user-id", str(user_id).encode())],
    }
    return Request(scope)

async def send_whatsapp_message(phone_number: str, message: str, sent_from_thrum=True):

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
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload, auth=(account_sid, auth_token))
            
            if response.status_code == 201:
                print(f"✅ Sent WhatsApp message to {phone_number}")
            elif response.status_code == 429:
                print(f"⚠️ Rate limit exceeded - Twilio daily message limit reached")
            else:
                print(f"❌ Failed to send message: {response.status_code}")
                
    except Exception as e:
        print(f"❌ WhatsApp send error: {e}")

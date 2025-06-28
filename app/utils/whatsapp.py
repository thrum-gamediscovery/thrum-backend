import requests
import os
from requests.auth import HTTPBasicAuth

def send_whatsapp_message(phone_number: str, message: str):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_whatsapp_number = "whatsapp:+14155238886"  # This is Twilio's sandbox number

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
    except requests.RequestException as e:
        print(f"⚠️ Failed to send message to {phone_number}: {e}")
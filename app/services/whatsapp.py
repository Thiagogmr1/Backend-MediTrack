import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
template_sid = os.getenv("TWILIO_TEMPLATE_SID")

def send_reminder(phone: str, medication_name: str, dosage: str):
    try:
        formatted_phone = f"whatsapp:+55{phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}"
        print(f"[WhatsApp] Enviando para: {formatted_phone}")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

        data = {
            "From": twilio_number,
            "To": formatted_phone,
            "ContentSid": template_sid,
            "ContentVariables": json.dumps({"1": medication_name, "2": dosage})
        }

        response = requests.post(url, data=data, auth=(account_sid, auth_token))
        result = response.json()

        if response.status_code == 201:
            print(f"Mensagem enviada para {phone}: {result['sid']}")
            return True
        else:
            print(f"Erro ao enviar para {phone}: {result}")
            return False

    except Exception as e:
        print(f"Erro ao enviar mensagem para {phone}: {e}")
        return False
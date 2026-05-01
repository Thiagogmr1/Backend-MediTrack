from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")

client = Client(account_sid, auth_token)

def send_reminder(phone: str, medication_name: str, dosage: str):
    try:
        formatted_phone = f"whatsapp:+55{phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}"
        print(f"[WhatsApp] Enviando para: {formatted_phone}")
        
        message = client.messages.create(
            from_=twilio_number,
            to=formatted_phone,
            body=f"⏰ *Lembrete de Medicamento*\n\nEstá quase na hora de tomar:\n*{medication_name} {dosage}*\n\nResponda com uma das opções:\n✅ *Tomei*\n❌ *Não tomei*"
        )
        print(f"Mensagem enviada para {phone}: {message.sid}")
        return True
    except Exception as e:
        print(f"Erro ao enviar mensagem para {phone}: {e}")
        return False
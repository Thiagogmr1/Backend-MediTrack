import logging
import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
template_sid = os.getenv("TWILIO_TEMPLATE_SID")
template_group_sid = os.getenv("TWILIO_TEMPLATE_GROUP_SID")

if not all([account_sid, auth_token, twilio_number, template_sid, template_group_sid]):
    raise RuntimeError("Variáveis de ambiente do Twilio não configuradas corretamente")


def _send_template(phone: str, content_sid: str, content_variables: dict):
    logger.info(f"[WhatsApp] Template: {content_sid} | Variáveis: {content_variables}")
    try:
        formatted_phone = f"whatsapp:+55{phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}"
        logger.info(f"[WhatsApp] Enviando para: {formatted_phone}")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

        data = {
            "From": twilio_number,
            "To": formatted_phone,
            "ContentSid": content_sid,
            "ContentVariables": json.dumps(content_variables)
        }

        response = requests.post(url, data=data, auth=(account_sid, auth_token))
        result = response.json()

        if response.status_code == 201:
            logger.info(f"[WhatsApp] Mensagem enviada para {phone}: {result['sid']}")
            return True
        else:
            logger.error(f"[WhatsApp] Erro ao enviar para {phone}: {result}")
            return False

    except Exception as e:
        logger.error(f"[WhatsApp] Erro ao enviar mensagem para {phone}: {e}")
        return False


def send_reminder(phone: str, medication_name: str, dosage: str):
    """Envia lembrete de um único medicamento (template original)."""
    return _send_template(phone, template_sid, {"1": medication_name, "2": dosage})


def send_grouped_reminder(phone: str, medications: list[dict]):
    """Envia lembrete agrupado de vários medicamentos no mesmo horário (template novo)."""
    medication_list = "\n".join(f"• {m['name']} {m['dosage']}" for m in medications)
    return _send_template(phone, template_group_sid, {"1": medication_list})
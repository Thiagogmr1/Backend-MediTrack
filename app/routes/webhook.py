import logging
import os
from fastapi import APIRouter, Request, HTTPException
from twilio.request_validator import RequestValidator
from app.database import get_connection

logger = logging.getLogger(__name__)
router = APIRouter()

def validate_twilio_request(request: Request, form_data: dict) -> bool:
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    validator = RequestValidator(auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    return validator.validate(url, dict(form_data), signature)

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()

    if not validate_twilio_request(request, dict(form_data)):
        logger.warning("[Webhook] Requisição inválida — não veio da Twilio")
        raise HTTPException(status_code=403, detail="Requisição inválida")

    phone = str(form_data.get("From", "")).replace("whatsapp:+55", "").replace("whatsapp:+", "")
    message = str(form_data.get("Body", "")).strip().lower()
    button_payload = str(form_data.get("ButtonPayload", "")).strip().lower()

    if len(phone) == 10:
        phone = phone[:2] + '9' + phone[2:]

    response_text = button_payload if button_payload else message

    logger.info(f"[Webhook] Telefone: {phone} | Mensagem: '{message}' | Payload: '{button_payload}'")

    if "tomei" not in response_text:
        logger.info(f"[Webhook] Resposta ignorada: {response_text}")
        return {"status": "ignored"}

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Acha a dose pendente mais próxima para esse telefone
        cursor.execute("""
            SELECT d.id, m.prescription_id, ms.scheduled_time
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN medication_schedules ms ON ms.id = d.schedule_id
            JOIN prescriptions p ON p.id = m.prescription_id
            JOIN users u ON u.id = p.patient_id
            LEFT JOIN dose_logs dl ON dl.dose_id = d.id AND dl.patient_id = u.id
            WHERE d.scheduled_date = CURRENT_DATE
            AND dl.id IS NULL
            AND REGEXP_REPLACE(u.phone, '[^0-9]', '', 'g') = REGEXP_REPLACE(%s, '[^0-9]', '', 'g')
            ORDER BY ms.scheduled_time ASC
            LIMIT 1
        """, (phone,))

        row = cursor.fetchone()

        if not row:
            logger.info(f"[Webhook] Nenhuma dose pendente para {phone}")
            return {"status": "no_pending_dose"}

        reference_dose_id, prescription_id, scheduled_time = row

        # 2. Busca o patient_id
        cursor.execute("""
            SELECT p.patient_id
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN prescriptions p ON p.id = m.prescription_id
            WHERE d.id = %s
        """, (reference_dose_id,))
        patient_id = cursor.fetchone()[0]

        # 3. Busca TODAS as doses pendentes da mesma prescrição + mesmo horário
        cursor.execute("""
            SELECT d.id
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN medication_schedules ms ON ms.id = d.schedule_id
            LEFT JOIN dose_logs dl ON dl.dose_id = d.id AND dl.patient_id = %s
            WHERE m.prescription_id = %s
            AND ms.scheduled_time = %s
            AND d.scheduled_date = CURRENT_DATE
            AND dl.id IS NULL
        """, (patient_id, prescription_id, scheduled_time))

        dose_ids = [r[0] for r in cursor.fetchall()]

        # 4. Registra todas as doses do grupo de uma vez
        for dose_id in dose_ids:
            cursor.execute(
                "INSERT INTO dose_logs (dose_id, patient_id) VALUES (%s, %s)",
                (dose_id, patient_id)
            )
        conn.commit()

        logger.info(f"[Webhook] {len(dose_ids)} dose(s) registrada(s) para paciente {patient_id} — prescrição {prescription_id} às {scheduled_time}")
        return {"status": "success", "doses_registered": len(dose_ids)}

    except Exception as e:
        conn.rollback()
        logger.error(f"[Webhook] Erro: {e}")
        return {"status": "error"}
    finally:
        cursor.close()
        conn.close()
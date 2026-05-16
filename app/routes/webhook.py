import logging
from fastapi import APIRouter, Request
from app.database import get_connection

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()

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
        cursor.execute("""
            SELECT d.id
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN prescriptions p ON p.id = m.prescription_id
            JOIN users u ON u.id = p.patient_id
            LEFT JOIN dose_logs dl ON dl.dose_id = d.id AND dl.patient_id = u.id
            WHERE d.scheduled_date = CURRENT_DATE
            AND dl.id IS NULL
            AND REGEXP_REPLACE(u.phone, '[^0-9]', '', 'g') = REGEXP_REPLACE(%s, '[^0-9]', '', 'g')
            ORDER BY (
                SELECT ms.scheduled_time
                FROM medication_schedules ms
                WHERE ms.id = d.schedule_id
            ) ASC
            LIMIT 1
        """, (phone,))

        row = cursor.fetchone()

        if not row:
            logger.info(f"[Webhook] Nenhuma dose pendente para {phone}")
            return {"status": "no_pending_dose"}

        dose_id = row[0]

        cursor.execute("""
            SELECT p.patient_id
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN prescriptions p ON p.id = m.prescription_id
            WHERE d.id = %s
        """, (dose_id,))

        patient_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO dose_logs (dose_id, patient_id) VALUES (%s, %s)",
            (dose_id, patient_id)
        )
        conn.commit()

        logger.info(f"[Webhook] Dose {dose_id} registrada para paciente {patient_id}")
        return {"status": "success"}

    except Exception as e:
        conn.rollback()
        logger.error(f"[Webhook] Erro: {e}")
        return {"status": "error"}
    finally:
        cursor.close()
        conn.close()
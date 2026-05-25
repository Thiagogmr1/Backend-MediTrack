import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import get_connection
from app.services.whatsapp import send_reminder
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def check_and_send_reminders():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        logger.info(f"[Scheduler] Horário: {now} — Buscando doses até {current_time}")

        cursor.execute("""
            SELECT
                d.id AS dose_id,
                u.phone,
                m.name AS medication_name,
                m.dosage,
                ms.scheduled_time
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN medication_schedules ms ON ms.id = d.schedule_id
            JOIN prescriptions p ON p.id = m.prescription_id
            JOIN users u ON u.id = p.patient_id
            WHERE d.scheduled_date = %s
            AND d.reminder_sent = FALSE
            AND TO_CHAR(ms.scheduled_time, 'HH24:MI') <= %s
            AND u.phone IS NOT NULL
        """, (today, current_time))

        rows = cursor.fetchall()
        logger.info(f"[Scheduler] Doses encontradas: {len(rows)}")

        for row in rows:
            dose_id, phone, medication_name, dosage, _ = row
            logger.info(f"[Scheduler] Enviando para {phone} — {medication_name}")
            success = send_reminder(phone, medication_name, dosage)

            if success:
                cursor.execute(
                    "UPDATE doses SET reminder_sent = TRUE WHERE id = %s",
                    (dose_id,)
                )
                conn.commit()
                logger.info(f"[Scheduler] Lembrete enviado — {phone} | {medication_name}")

    except Exception as e:
        logger.error(f"[Scheduler] Erro: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def start_scheduler():
    scheduler.add_job(check_and_send_reminders, "interval", minutes=1)
    scheduler.start()
    logger.info("[Scheduler] Agendador iniciado!")
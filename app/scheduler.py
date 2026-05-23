import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import get_connection
from app.services.whatsapp import send_reminder
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=ZoneInfo("America/Sao_Paulo"))

def check_and_send_reminders():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        today = now.strftime("%Y-%m-%d")
        window_start = (now - timedelta(minutes=2)).strftime("%H:%M")
        window_end = now.strftime("%H:%M")

        logger.info(f"[Scheduler] Horário: {now} — Janela: {window_start} a {window_end}")

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
            AND TO_CHAR(ms.scheduled_time, 'HH24:MI') BETWEEN %s AND %s
            AND u.phone IS NOT NULL
        """, (today, window_start, window_end))

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


def mark_missed_doses():
    """Roda à meia-noite e marca como missed todas as doses pending do dia anterior."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        logger.info(f"[Scheduler] Marcando doses perdidas do dia {yesterday}")

        cursor.execute("""
            UPDATE doses
            SET status = 'missed'
            WHERE scheduled_date = %s
            AND status = 'pending'
        """, (yesterday,))

        missed_count = cursor.rowcount
        conn.commit()

        logger.info(f"[Scheduler] {missed_count} doses marcadas como missed")

    except Exception as e:
        logger.error(f"[Scheduler] Erro ao marcar doses perdidas: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def start_scheduler():
    # Job de lembretes — roda a cada minuto
    scheduler.add_job(check_and_send_reminders, "interval", minutes=1)

    # Job de meia-noite — marca doses perdidas do dia anterior
    scheduler.add_job(
        mark_missed_doses,
        CronTrigger(hour=0, minute=1, timezone=ZoneInfo("America/Sao_Paulo"))
    )

    scheduler.start()
    logger.info("[Scheduler] Agendador iniciado!")
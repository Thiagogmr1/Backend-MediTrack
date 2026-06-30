import logging
from datetime import datetime, timedelta
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import get_connection
from app.services.whatsapp import send_reminder, send_grouped_reminder

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def check_and_send_reminders():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        now = datetime.now()
        window_start = now.strftime("%H:%M")
        window_end = (now + timedelta(minutes=1)).strftime("%H:%M")
        logger.info(f"[Scheduler] Horário: {now} — Janela: {window_start} a {window_end}")

        cursor.execute("""
            SELECT
                d.id AS dose_id,
                u.phone,
                m.name AS medication_name,
                m.dosage,
                p.id AS prescription_id,
                ms.scheduled_time
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN medication_schedules ms ON ms.id = d.schedule_id
            JOIN prescriptions p ON p.id = m.prescription_id
            JOIN users u ON u.id = p.patient_id
            WHERE d.scheduled_date = CURRENT_DATE
            AND d.reminder_sent = FALSE
            AND d.status = 'pending'
            AND m.status = 'active'
            AND p.status = 'active'
            AND TO_CHAR(ms.scheduled_time, 'HH24:MI') BETWEEN %s AND %s
            AND u.phone IS NOT NULL
        """, (window_start, window_end))

        rows = cursor.fetchall()
        logger.info(f"[Scheduler] Doses encontradas: {len(rows)}")

        # Agrupa por (telefone, prescrição, horário)
        groups = defaultdict(list)
        for row in rows:
            dose_id, phone, medication_name, dosage, prescription_id, scheduled_time = row
            key = (phone, prescription_id, scheduled_time)
            groups[key].append({
                "dose_id": dose_id,
                "name": medication_name,
                "dosage": dosage
            })

        for (phone, prescription_id, scheduled_time), meds in groups.items():
            if len(meds) == 1:
                logger.info(f"[Scheduler] Enviando individual para {phone} — {meds[0]['name']}")
                success = send_reminder(phone, meds[0]["name"], meds[0]["dosage"])
            else:
                names = ", ".join(m["name"] for m in meds)
                logger.info(f"[Scheduler] Enviando agrupado para {phone} — {names}")
                success = send_grouped_reminder(phone, meds)

            if success:
                dose_ids = [m["dose_id"] for m in meds]
                cursor.execute(
                    "UPDATE doses SET reminder_sent = TRUE WHERE id = ANY(%s)",
                    (dose_ids,)
                )
                conn.commit()
                logger.info(f"[Scheduler] Lembrete enviado para {phone} — {len(meds)} medicamento(s)")

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
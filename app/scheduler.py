from apscheduler.schedulers.background import BackgroundScheduler
from app.database import get_connection
from app.services.whatsapp import send_reminder
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()

def check_and_send_reminders():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        now = datetime.now()
        # Janela de 1 minuto para frente
        window_start = (now + timedelta(minutes=1)).strftime("%H:%M")
        window_end = (now + timedelta(minutes=2)).strftime("%H:%M")
        print(f"[Scheduler] Horário do Python: {now} — Janela: {window_start} a {window_end}")

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
            WHERE d.scheduled_date = CURRENT_DATE
            AND d.reminder_sent = FALSE
            AND TO_CHAR(ms.scheduled_time, 'HH24:MI') BETWEEN %s AND %s
            AND u.phone IS NOT NULL
        """, (window_start, window_end))

        rows = cursor.fetchall()
        print(f"[Scheduler] Doses encontradas: {len(rows)}")

        for row in rows:
            dose_id, phone, medication_name, dosage, _ = row

            print(f"[Scheduler] Enviando para {phone} — {medication_name}")
            success = send_reminder(phone, medication_name, dosage)

            if success:
                cursor.execute(
                    "UPDATE doses SET reminder_sent = TRUE WHERE id = %s",
                    (dose_id,)
                )
                conn.commit()
                print(f"[Scheduler] Lembrete enviado para {phone} — {medication_name}")

    except Exception as e:
        print(f"[Scheduler] Erro: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def start_scheduler():
    scheduler.add_job(check_and_send_reminders, "interval", minutes=1)
    scheduler.start()
    print("[Scheduler] Agendador iniciado!")
from fastapi import APIRouter, HTTPException
from app.database import get_connection
from datetime import date

router = APIRouter()

@router.get("/today/{patient_id}")
def get_today_doses(patient_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                d.id AS dose_id,
                m.name AS medication_name,
                m.dosage,
                m.indication,
                ms.scheduled_time,
                CASE WHEN dl.id IS NOT NULL THEN 'taken' ELSE 'pending' END AS status
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN medication_schedules ms ON ms.id = d.schedule_id
            LEFT JOIN dose_logs dl ON dl.dose_id = d.id AND dl.patient_id = %s
            WHERE d.scheduled_date = %s
            AND m.prescription_id IN (
                SELECT id FROM prescriptions WHERE patient_id = %s
            )
            ORDER BY ms.scheduled_time
        """, (patient_id, date.today(), patient_id))

        rows = cursor.fetchall()

        doses = []
        for row in rows:
            doses.append({
                "dose_id": row[0],
                "medication_name": row[1],
                "dosage": row[2],
                "indication": row[3],
                "scheduled_time": str(row[4]),
                "status": row[5]
            })

        return doses

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/{dose_id}/take")
def take_dose(dose_id: int, patient_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Verifica se a dose já foi tomada
        cursor.execute(
            "SELECT id FROM dose_logs WHERE dose_id = %s AND patient_id = %s",
            (dose_id, patient_id)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Dose já registrada!")

        # Registra a dose
        cursor.execute(
            "INSERT INTO dose_logs (dose_id, patient_id) VALUES (%s, %s) RETURNING id",
            (dose_id, patient_id)
        )
        conn.commit()

        return {"message": "Dose registrada com sucesso!"}

    except HTTPException as e:
        raise e
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
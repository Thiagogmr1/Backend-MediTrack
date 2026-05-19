from fastapi import APIRouter, HTTPException, Depends
from app.database import get_connection
from app.auth import require_role, get_current_user
from datetime import date

router = APIRouter()

@router.get("/today/{patient_id}")
def get_today_doses(patient_id: int, current_user: dict = Depends(require_role("patient"))):
    if int(current_user.get("sub")) != patient_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

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
        return [
            {
                "dose_id": row[0],
                "medication_name": row[1],
                "dosage": row[2],
                "indication": row[3],
                "scheduled_time": str(row[4]),
                "status": row[5]
            }
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()


@router.post("/{dose_id}/take")
def take_dose(dose_id: int, patient_id: int, current_user: dict = Depends(require_role("patient"))):
    if int(current_user.get("sub")) != patient_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM dose_logs WHERE dose_id = %s AND patient_id = %s",
            (dose_id, patient_id)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Dose já registrada!")

        cursor.execute(
            "INSERT INTO dose_logs (dose_id, patient_id) VALUES (%s, %s) RETURNING id",
            (dose_id, patient_id)
        )
        conn.commit()
        return {"message": "Dose registrada com sucesso!"}

    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()
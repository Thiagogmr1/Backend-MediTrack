from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_connection
from app.auth import require_role, get_current_user

router = APIRouter()

# -------------------------
# MODELS
# -------------------------

class MedicationSchedule(BaseModel):
    scheduled_time: str

class MedicationCreate(BaseModel):
    name: str
    dosage: str
    indication: Optional[str] = None
    notes: Optional[str] = None
    start_date: str
    end_date: str
    schedules: List[MedicationSchedule]

class PrescriptionCreate(BaseModel):
    doctor_id: int
    patient_id: int
    notes: Optional[str] = None
    medications: List[MedicationCreate]

# -------------------------
# CREATE PRESCRIPTION
# -------------------------

@router.post("/")
def create_prescription(prescription: PrescriptionCreate, current_user: dict = Depends(require_role("doctor"))):
    if int(current_user.get("sub")) != prescription.doctor_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO prescriptions (doctor_id, patient_id, notes) VALUES (%s, %s, %s) RETURNING id",
            (prescription.doctor_id, prescription.patient_id, prescription.notes)
        )
        prescription_id = cursor.fetchone()[0]

        for med in prescription.medications:
            cursor.execute(
                """INSERT INTO medications 
                (prescription_id, name, dosage, indication, notes, start_date, end_date) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (prescription_id, med.name, med.dosage, med.indication, med.notes, med.start_date, med.end_date)
            )
            medication_id = cursor.fetchone()[0]

            for schedule in med.schedules:
                cursor.execute(
                    "INSERT INTO medication_schedules (medication_id, scheduled_time) VALUES (%s, %s) RETURNING id",
                    (medication_id, schedule.scheduled_time)
                )
                schedule_id = cursor.fetchone()[0]

                cursor.execute(
                    """INSERT INTO doses (medication_id, schedule_id, scheduled_date)
                    SELECT %s, %s, generate_series(%s::date, %s::date, '1 day'::interval)::date""",
                    (medication_id, schedule_id, med.start_date, med.end_date)
                )

        conn.commit()
        return {"message": "Prescrição criada com sucesso", "prescription_id": prescription_id}

    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()

# -------------------------
# GET PATIENT MEDICATIONS
# -------------------------

@router.get("/patient/{patient_id}")
def get_patient_medications(patient_id: int, current_user: dict = Depends(get_current_user)):
    if int(current_user.get("sub")) != patient_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                m.id AS medication_id,
                m.name,
                m.dosage,
                m.indication,
                m.notes,
                m.start_date,
                m.end_date,
                ARRAY_AGG(ms.scheduled_time::text ORDER BY ms.scheduled_time) AS schedules
            FROM medications m
            JOIN prescriptions p ON p.id = m.prescription_id
            JOIN medication_schedules ms ON ms.medication_id = m.id
            WHERE p.patient_id = %s
            AND m.end_date >= CURRENT_DATE
            GROUP BY m.id, m.name, m.dosage, m.indication, m.notes, m.start_date, m.end_date
            ORDER BY m.name
        """, (patient_id,))

        rows = cursor.fetchall()
        return [
            {
                "medication_id": row[0],
                "name": row[1],
                "dosage": row[2],
                "indication": row[3],
                "notes": row[4],
                "start_date": str(row[5]),
                "end_date": str(row[6]),
                "schedules": row[7]
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
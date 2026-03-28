from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_connection
from app.auth import require_role

router = APIRouter()

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

@router.post("/", dependencies=[Depends(require_role("doctor"))])
def create_prescription(prescription: PrescriptionCreate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Cria a prescrição
        cursor.execute(
            "INSERT INTO prescriptions (doctor_id, patient_id, notes) VALUES (%s, %s, %s) RETURNING id",
            (prescription.doctor_id, prescription.patient_id, prescription.notes)
        )
        prescription_id = cursor.fetchone()[0]

        for med in prescription.medications:
            # Cria cada medicamento
            cursor.execute(
                """INSERT INTO medications 
                (prescription_id, name, dosage, indication, notes, start_date, end_date) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (prescription_id, med.name, med.dosage, med.indication, med.notes, med.start_date, med.end_date)
            )
            medication_id = cursor.fetchone()[0]

            for schedule in med.schedules:
                # Cria cada horário
                cursor.execute(
                    "INSERT INTO medication_schedules (medication_id, scheduled_time) VALUES (%s, %s) RETURNING id",
                    (medication_id, schedule.scheduled_time)
                )
                schedule_id = cursor.fetchone()[0]

                # Gera as doses automaticamente
                cursor.execute(
                    """INSERT INTO doses (medication_id, schedule_id, scheduled_date)
                    SELECT %s, %s, generate_series(%s::date, %s::date, '1 day'::interval)::date""",
                    (medication_id, schedule_id, med.start_date, med.end_date)
                )

        conn.commit()
        return {"message": "Prescrição criada com sucesso!", "prescription_id": prescription_id}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
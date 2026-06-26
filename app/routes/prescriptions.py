from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime
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
    end_date: Optional[str] = None
    continuous_use: bool = False
    frequency: Optional[str] = None
    schedules: List[MedicationSchedule]

    @validator("end_date", always=True)
    def validate_end_date(cls, v, values):
        if not values.get("continuous_use") and not v:
            raise ValueError("end_date é obrigatório quando continuous_use é False")
        if values.get("continuous_use"):
            return None
        return v

class PrescriptionCreate(BaseModel):
    doctor_id: int
    patient_id: int
    notes: Optional[str] = None
    medications: List[MedicationCreate]

class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    indication: Optional[str] = None
    notes: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    continuous_use: Optional[bool] = None
    frequency: Optional[str] = None
    schedules: Optional[List[MedicationSchedule]] = None

class PrescriptionUpdate(BaseModel):
    notes: Optional[str] = None
    medications: Optional[List[MedicationUpdate]] = None

# -------------------------
# HELPERS
# -------------------------

CONTINUOUS_USE_DAYS = 90

def _generate_doses(cursor, medication_id: int, schedule_id: int, start_date: str, end_date: Optional[str], continuous_use: bool):
    """Gera doses para um schedule. Uso contínuo gera janela de 90 dias."""
    if continuous_use or end_date is None:
        cursor.execute(
            """INSERT INTO doses (medication_id, schedule_id, scheduled_date)
            SELECT %s, %s, generate_series(%s::date, %s::date + INTERVAL '%s days', '1 day'::interval)::date""",
            (medication_id, schedule_id, start_date, start_date, CONTINUOUS_USE_DAYS)
        )
    else:
        cursor.execute(
            """INSERT INTO doses (medication_id, schedule_id, scheduled_date)
            SELECT %s, %s, generate_series(%s::date, %s::date, '1 day'::interval)::date""",
            (medication_id, schedule_id, start_date, end_date)
        )

def _assert_doctor_owns_prescription(cursor, prescription_id: int, doctor_id: int):
    """Lança 403 se a prescrição não pertence ao médico."""
    cursor.execute(
        "SELECT id FROM prescriptions WHERE id = %s AND doctor_id = %s AND status != 'ended'",
        (prescription_id, doctor_id)
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=403, detail="Acesso negado ou prescrição não encontrada")

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
                (prescription_id, name, dosage, indication, notes, start_date, end_date, continuous_use, frequency)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    prescription_id, med.name, med.dosage, med.indication,
                    med.notes, med.start_date, med.end_date,
                    med.continuous_use, med.frequency
                )
            )
            medication_id = cursor.fetchone()[0]

            for schedule in med.schedules:
                cursor.execute(
                    "INSERT INTO medication_schedules (medication_id, scheduled_time) VALUES (%s, %s) RETURNING id",
                    (medication_id, schedule.scheduled_time)
                )
                schedule_id = cursor.fetchone()[0]
                _generate_doses(cursor, medication_id, schedule_id, med.start_date, med.end_date, med.continuous_use)

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
# LIST PRESCRIPTIONS (médico vê todas de um paciente)
# -------------------------

@router.get("/doctor/{doctor_id}/patient/{patient_id}")
def list_prescriptions(doctor_id: int, patient_id: int, current_user: dict = Depends(require_role("doctor"))):
    if int(current_user.get("sub")) != doctor_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                p.id,
                p.notes,
                p.status,
                p.created_at,
                COUNT(m.id) AS total_medications,
                BOOL_OR(m.continuous_use) AS has_continuous,
                MAX(m.end_date) AS latest_end_date,
                MAX(ms.scheduled_time) AS latest_scheduled_time,
                ARRAY_AGG(DISTINCT m.name ORDER BY m.name) AS medication_names
            FROM prescriptions p
            LEFT JOIN medications m ON m.prescription_id = p.id
            LEFT JOIN medication_schedules ms ON ms.medication_id = m.id
            WHERE p.doctor_id = %s AND p.patient_id = %s
            GROUP BY p.id, p.notes, p.status, p.created_at
            ORDER BY p.created_at DESC
        """, (doctor_id, patient_id))

        rows = cursor.fetchall()
        return [
            {
                "prescription_id": row[0],
                "notes": row[1],
                "status": row[2],
                "created_at": str(row[3]),
                "total_medications": row[4],
                "has_continuous": row[5],
                "latest_end_date": str(row[6]) if row[6] else None,
                "latest_scheduled_time": str(row[7]) if row[7] else None,
                "medication_names": row[8] if row[8] else []
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

# -------------------------
# GET PRESCRIPTION DETAIL
# -------------------------

@router.get("/{prescription_id}")
def get_prescription(prescription_id: int, current_user: dict = Depends(require_role("doctor"))):
    doctor_id = int(current_user.get("sub"))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Valida ownership
        cursor.execute(
            "SELECT id, notes, status, created_at, patient_id FROM prescriptions WHERE id = %s AND doctor_id = %s",
            (prescription_id, doctor_id)
        )
        prescription = cursor.fetchone()
        if not prescription:
            raise HTTPException(status_code=403, detail="Acesso negado ou prescrição não encontrada")

        # Busca medicamentos com horários
        cursor.execute("""
            SELECT
                m.id,
                m.name,
                m.dosage,
                m.indication,
                m.notes,
                m.start_date,
                m.end_date,
                m.continuous_use,
                m.frequency,
                m.status,
                ARRAY_AGG(ms.scheduled_time::text ORDER BY ms.scheduled_time) AS schedules
            FROM medications m
            JOIN medication_schedules ms ON ms.medication_id = m.id
            WHERE m.prescription_id = %s
            GROUP BY m.id, m.name, m.dosage, m.indication, m.notes,
                     m.start_date, m.end_date, m.continuous_use, m.frequency, m.status
            ORDER BY m.name
        """, (prescription_id,))

        medications = cursor.fetchall()
        return {
            "prescription_id": prescription[0],
            "notes": prescription[1],
            "status": prescription[2],
            "created_at": str(prescription[3]),
            "patient_id": prescription[4],
            "medications": [
                {
                    "medication_id": m[0],
                    "name": m[1],
                    "dosage": m[2],
                    "indication": m[3],
                    "notes": m[4],
                    "start_date": str(m[5]),
                    "end_date": str(m[6]) if m[6] else None,
                    "continuous_use": m[7],
                    "frequency": m[8],
                    "status": m[9],
                    "schedules": m[10]
                }
                for m in medications
            ]
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()

# -------------------------
# EDIT PRESCRIPTION
# -------------------------

@router.patch("/{prescription_id}")
def update_prescription(prescription_id: int, data: PrescriptionUpdate, current_user: dict = Depends(require_role("doctor"))):
    doctor_id = int(current_user.get("sub"))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        _assert_doctor_owns_prescription(cursor, prescription_id, doctor_id)

        # Atualiza notes da prescrição se enviado
        if data.notes is not None:
            cursor.execute(
                "UPDATE prescriptions SET notes = %s WHERE id = %s",
                (data.notes, prescription_id)
            )

        # Atualiza medicamentos se enviados
        if data.medications:
            for idx, med in enumerate(data.medications):
                # Busca o medication_id pelo índice (ordem de criação)
                cursor.execute(
                    "SELECT id FROM medications WHERE prescription_id = %s ORDER BY id LIMIT 1 OFFSET %s",
                    (prescription_id, idx)
                )
                row = cursor.fetchone()
                if not row:
                    continue
                medication_id = row[0]

                # Monta update dinâmico apenas com campos enviados
                fields = []
                values = []
                for field in ["name", "dosage", "indication", "notes", "start_date", "end_date", "continuous_use", "frequency"]:
                    val = getattr(med, field)
                    if val is not None:
                        fields.append(f"{field} = %s")
                        values.append(val)

                if fields:
                    values.append(medication_id)
                    cursor.execute(
                        f"UPDATE medications SET {', '.join(fields)} WHERE id = %s",
                        values
                    )

                # Atualiza horários se enviados
                if med.schedules is not None:
                    # Deleta todas as doses não confirmadas (sem dose_log)
                    cursor.execute("""
                        DELETE FROM doses
                        WHERE medication_id = %s
                        AND id NOT IN (SELECT dose_id FROM dose_logs)
                    """, (medication_id,))

                    # Agora pode deletar os schedules com segurança
                    cursor.execute("DELETE FROM medication_schedules WHERE medication_id = %s", (medication_id,))

                    # Busca start_date e end_date atualizados do medicamento
                    cursor.execute(
                        "SELECT start_date, end_date, continuous_use FROM medications WHERE id = %s",
                        (medication_id,)
                    )
                    med_row = cursor.fetchone()
                    start_date = str(med_row[0])
                    end_date = str(med_row[1]) if med_row[1] else None
                    continuous_use = med_row[2]

                    for schedule in med.schedules:
                        cursor.execute(
                            "INSERT INTO medication_schedules (medication_id, scheduled_time) VALUES (%s, %s) RETURNING id",
                            (medication_id, schedule.scheduled_time)
                        )
                        schedule_id = cursor.fetchone()[0]
                        _generate_doses(cursor, medication_id, schedule_id, start_date, end_date, continuous_use)

        conn.commit()
        return {"message": "Prescrição atualizada com sucesso"}

    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()

# -------------------------
# SUSPEND PRESCRIPTION
# -------------------------

@router.patch("/{prescription_id}/suspend")
def suspend_prescription(prescription_id: int, current_user: dict = Depends(require_role("doctor"))):
    doctor_id = int(current_user.get("sub"))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        _assert_doctor_owns_prescription(cursor, prescription_id, doctor_id)

        # Suspende prescrição e todos os medicamentos ativos
        cursor.execute(
            "UPDATE prescriptions SET status = 'suspended' WHERE id = %s",
            (prescription_id,)
        )
        cursor.execute(
            "UPDATE medications SET status = 'suspended' WHERE prescription_id = %s AND status = 'active'",
            (prescription_id,)
        )

        # Cancela doses futuras não confirmadas (mantém histórico passado)
        cursor.execute("""
            UPDATE doses SET status = 'cancelled'
            WHERE medication_id IN (
                SELECT id FROM medications WHERE prescription_id = %s
            )
            AND scheduled_date > CURRENT_DATE
            AND id NOT IN (SELECT dose_id FROM dose_logs)
        """, (prescription_id,))

        conn.commit()
        return {"message": "Prescrição suspensa com sucesso"}

    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()

# -------------------------
# REACTIVATE PRESCRIPTION
# -------------------------

@router.patch("/{prescription_id}/reactivate")
def reactivate_prescription(prescription_id: int, current_user: dict = Depends(require_role("doctor"))):
    doctor_id = int(current_user.get("sub"))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Valida ownership e que está suspensa
        cursor.execute(
            "SELECT id FROM prescriptions WHERE id = %s AND doctor_id = %s AND status = 'suspended'",
            (prescription_id, doctor_id)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Prescrição não encontrada ou não está suspensa")

        # Reativa prescrição e medicamentos
        cursor.execute(
            "UPDATE prescriptions SET status = 'active' WHERE id = %s",
            (prescription_id,)
        )
        cursor.execute(
            "UPDATE medications SET status = 'active' WHERE prescription_id = %s AND status = 'suspended'",
            (prescription_id,)
        )

        # Busca medicamentos para gerar novas doses a partir de hoje
        cursor.execute("""
            SELECT id, end_date, continuous_use
            FROM medications
            WHERE prescription_id = %s AND status = 'active'
        """, (prescription_id,))
        medications = cursor.fetchall()

        today = datetime.now().date()

        for med_row in medications:
            medication_id = med_row[0]
            end_date = med_row[1]
            continuous_use = med_row[2]

            # Ignora medicamentos com end_date já vencido
            if not continuous_use and end_date and end_date < today:
                continue

            cursor.execute(
                "SELECT id FROM medication_schedules WHERE medication_id = %s",
                (medication_id,)
            )
            schedules = cursor.fetchall()

            for schedule_row in schedules:
                schedule_id = schedule_row[0]

                # Remove todas as doses não confirmadas a partir de hoje (cancelled e pending)
                cursor.execute("""
                    DELETE FROM doses
                    WHERE medication_id = %s
                    AND schedule_id = %s
                    AND scheduled_date >= %s
                    AND id NOT IN (SELECT dose_id FROM dose_logs)
                """, (medication_id, schedule_id, today))

                _generate_doses(
                    cursor,
                    medication_id,
                    schedule_id,
                    str(today),
                    str(end_date) if end_date else None,
                    continuous_use
                )

                # Cancela doses de hoje cujo horário já passou
                cursor.execute("""
                    UPDATE doses SET status = 'cancelled'
                    WHERE medication_id = %s
                    AND schedule_id = %s
                    AND scheduled_date = %s
                    AND status = 'pending'
                    AND reminder_sent = FALSE
                    AND (
                        SELECT ms2.scheduled_time
                        FROM medication_schedules ms2
                        WHERE ms2.id = %s
                    ) < CURRENT_TIME
                """, (medication_id, schedule_id, today, schedule_id))

        conn.commit()
        return {"message": "Prescrição reativada com sucesso"}

    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()

# -------------------------
# DELETE PRESCRIPTION (soft delete)
# -------------------------

@router.delete("/{prescription_id}")
def delete_prescription(prescription_id: int, current_user: dict = Depends(require_role("doctor"))):
    doctor_id = int(current_user.get("sub"))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        _assert_doctor_owns_prescription(cursor, prescription_id, doctor_id)

        # Soft delete: marca como encerrada sem remover dados
        cursor.execute(
            "UPDATE prescriptions SET status = 'ended' WHERE id = %s",
            (prescription_id,)
        )
        cursor.execute(
            "UPDATE medications SET status = 'ended' WHERE prescription_id = %s",
            (prescription_id,)
        )

        # Cancela todas as doses futuras não confirmadas
        cursor.execute("""
            UPDATE doses SET status = 'cancelled'
            WHERE medication_id IN (
                SELECT id FROM medications WHERE prescription_id = %s
            )
            AND scheduled_date > CURRENT_DATE
            AND id NOT IN (SELECT dose_id FROM dose_logs)
        """, (prescription_id,))

        conn.commit()
        return {"message": "Prescrição encerrada com sucesso"}

    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()

# -------------------------
# GET PATIENT MEDICATIONS (rota original — mantida)
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
            AND m.status = 'active'
            AND (m.end_date IS NULL OR m.end_date >= CURRENT_DATE)
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
                "end_date": str(row[6]) if row[6] else None,
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
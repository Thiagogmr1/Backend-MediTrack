from fastapi import APIRouter, HTTPException, Depends
from app.database import get_connection
from app.auth import require_role

router = APIRouter()

@router.get("/doctor/{doctor_id}")
def get_patients_by_doctor(doctor_id: int, current_user: dict = Depends(require_role("doctor"))):
    if int(current_user.get("sub")) != doctor_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT u.id, u.name, u.cpf, u.birth_date, u.phone
            FROM users u
            JOIN doctor_patients dp ON dp.patient_id = u.id
            WHERE dp.doctor_id = %s AND u.role = 'patient'
            ORDER BY u.name
        """, (doctor_id,))
        rows = cursor.fetchall()
        return [
            {"id": r[0], "name": r[1], "cpf": r[2],
             "birth_date": str(r[3]), "phone": r[4]}
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()
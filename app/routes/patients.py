from fastapi import APIRouter, HTTPException, Depends
from app.database import get_connection
from app.auth import require_role

router = APIRouter()

@router.get("/doctor/{doctor_id}", dependencies=[Depends(require_role("doctor"))])
def get_patients_by_doctor(doctor_id: int):
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
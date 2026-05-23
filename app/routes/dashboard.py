from fastapi import APIRouter, HTTPException, Depends
from app.auth import get_current_user, require_role
from app.database import get_connection
from datetime import date

router = APIRouter()

@router.get("/overview/{doctor_id}")
def get_dashboard_overview(doctor_id: int, current_user: dict = Depends(require_role("doctor"))):
    if int(current_user.get("sub")) != doctor_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(DISTINCT patient_id) 
            FROM prescriptions 
            WHERE doctor_id = %s
        """, (doctor_id,))
        total_patients = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                u.id,
                u.name,
                DATE_PART('year', AGE(u.birth_date)) AS age,
                COUNT(DISTINCT m.id) AS active_medications,
                COUNT(d.id) FILTER (WHERE d.status IN ('taken', 'missed')) AS total_doses,
                COUNT(d.id) FILTER (WHERE d.status = 'taken') AS taken_doses,
                ROUND(
                    COUNT(d.id) FILTER (WHERE d.status = 'taken') * 100.0 /
                    NULLIF(COUNT(d.id) FILTER (WHERE d.status IN ('taken', 'missed')), 0)
                , 2) AS adherence
            FROM prescriptions p
            JOIN users u ON u.id = p.patient_id
            JOIN medications m ON m.prescription_id = p.id
            JOIN doses d ON d.medication_id = m.id
            WHERE p.doctor_id = %s
            GROUP BY u.id, u.name, u.birth_date
        """, (doctor_id,))

        rows = cursor.fetchall()
        patients = []
        high_adherence = 0
        low_adherence = 0
        total_adherence = 0

        for row in rows:
            adherence = float(row[6]) if row[6] is not None else 100.0
            total_adherence += adherence
            if adherence >= 80:
                high_adherence += 1
            else:
                low_adherence += 1
            patients.append({
                "patient_id": row[0],
                "name": row[1],
                "age": int(row[2]) if row[2] else None,
                "active_medications": row[3],
                "total_doses": row[4],
                "taken_doses": row[5],
                "adherence": adherence
            })

        general_adherence = round(total_adherence / len(patients), 2) if patients else 0
        high_adherence_pct = round(high_adherence * 100 / total_patients, 2) if total_patients else 0
        low_adherence_pct = round(low_adherence * 100 / total_patients, 2) if total_patients else 0

        return {
            "total_patients": total_patients,
            "general_adherence": general_adherence,
            "high_adherence_percentage": high_adherence_pct,
            "low_adherence_percentage": low_adherence_pct,
            "patients": patients
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()


@router.get("/patient/{patient_id}")
def get_patient_dashboard(patient_id: int, current_user: dict = Depends(get_current_user)):
    role = current_user.get("role")
    user_id = int(current_user.get("sub"))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if role == "patient" and user_id != patient_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        if role == "doctor":
            cursor.execute("""
                SELECT 1 FROM doctor_patients
                WHERE doctor_id = %s AND patient_id = %s
            """, (user_id, patient_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="Acesso negado")

        # Adesão geral — apenas doses taken ou missed (excluindo pending)
        cursor.execute("""
            SELECT
                COUNT(d.id) FILTER (WHERE d.status IN ('taken', 'missed')) AS total_doses,
                COUNT(d.id) FILTER (WHERE d.status = 'taken') AS taken_doses,
                ROUND(
                    COUNT(d.id) FILTER (WHERE d.status = 'taken') * 100.0 /
                    NULLIF(COUNT(d.id) FILTER (WHERE d.status IN ('taken', 'missed')), 0)
                , 2) AS adherence,
                u.name,
                u.phone,
                DATE_PART('year', AGE(u.birth_date)) AS age
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN prescriptions p ON p.id = m.prescription_id
            JOIN users u ON u.id = p.patient_id
            WHERE p.patient_id = %s
            GROUP BY u.name, u.phone, u.birth_date
        """, (patient_id,))
        general = cursor.fetchone()

        if not general or general[0] == 0:
            cursor.execute("""
                SELECT u.name, u.phone, DATE_PART('year', AGE(u.birth_date))
                FROM users u WHERE u.id = %s
            """, (patient_id,))
            user_row = cursor.fetchone()
            return {
                "patient_name": user_row[0] if user_row else "",
                "patient_phone": user_row[1] if user_row else None,
                "patient_age": int(user_row[2]) if user_row and user_row[2] else None,
                "total_doses": 0,
                "taken_doses": 0,
                "general_adherence": 0.0,
                "missed_doses": 0,
                "consecutive_days": 0,
                "daily_adherence": [],
                "weekly_adherence": []
            }

        missed_doses = general[0] - general[1]

        # Adesão diária — usa status para determinar cor do calendário
        cursor.execute("""
            SELECT
                d.scheduled_date,
                COUNT(d.id) AS total_doses,
                COUNT(d.id) FILTER (WHERE d.status = 'taken') AS taken_doses,
                COUNT(d.id) FILTER (WHERE d.status = 'missed') AS missed_doses,
                ROUND(
                    COUNT(d.id) FILTER (WHERE d.status = 'taken') * 100.0 /
                    NULLIF(COUNT(d.id) FILTER (WHERE d.status IN ('taken', 'missed')), 0)
                , 2) AS adherence
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN prescriptions p ON p.id = m.prescription_id
            WHERE p.patient_id = %s
            AND d.scheduled_date >= CURRENT_DATE - INTERVAL '30 days'
            AND d.scheduled_date <= CURRENT_DATE
            GROUP BY d.scheduled_date
            ORDER BY d.scheduled_date
        """, (patient_id,))
        daily_rows = cursor.fetchall()

        daily_adherence = []
        consecutive_days = 0
        for row in daily_rows:
            scheduled_date = row[0]
            total = int(row[1])
            taken = int(row[2])
            missed = int(row[3])
            is_today = scheduled_date == date.today()

            if is_today:
                # Hoje: verde se tomou alguma, neutro se ainda pending
                if taken == total:
                    adherence_val = 100.0
                elif taken > 0:
                    adherence_val = round(taken * 100.0 / total, 2)
                else:
                    adherence_val = -1  # neutro — ainda no prazo
            else:
                # Dias anteriores — usa status real
                if missed == 0 and taken == 0:
                    adherence_val = -1  # sem dados
                elif missed == 0:
                    adherence_val = 100.0
                else:
                    adherence_val = float(row[4]) if row[4] else 0.0

            if adherence_val == 100:
                consecutive_days += 1
            elif adherence_val != -1:
                consecutive_days = 0

            daily_adherence.append({
                "date": str(scheduled_date),
                "total_doses": total,
                "taken_doses": taken,
                "adherence": adherence_val
            })

        # Adesão semanal — usa status
        cursor.execute("""
            SELECT
                DATE_TRUNC('week', d.scheduled_date) AS week,
                COUNT(d.id) FILTER (WHERE d.status IN ('taken', 'missed')) AS total_doses,
                COUNT(d.id) FILTER (WHERE d.status = 'taken') AS taken_doses,
                ROUND(
                    COUNT(d.id) FILTER (WHERE d.status = 'taken') * 100.0 /
                    NULLIF(COUNT(d.id) FILTER (WHERE d.status IN ('taken', 'missed')), 0)
                , 2) AS adherence
            FROM doses d
            JOIN medications m ON m.id = d.medication_id
            JOIN prescriptions p ON p.id = m.prescription_id
            WHERE p.patient_id = %s
            AND d.scheduled_date >= CURRENT_DATE - INTERVAL '30 days'
            AND d.scheduled_date <= CURRENT_DATE
            GROUP BY week
            ORDER BY week
        """, (patient_id,))
        weekly_rows = cursor.fetchall()

        weekly_adherence = [
            {
                "week": str(row[0])[:10],
                "total_doses": row[1],
                "taken_doses": row[2],
                "adherence": float(row[3]) if row[3] else 0
            }
            for row in weekly_rows
        ]

        return {
            "patient_name": general[3],
            "patient_phone": general[4],
            "patient_age": int(general[5]) if general[5] else None,
            "total_doses": general[0],
            "taken_doses": general[1],
            "general_adherence": float(general[2]) if general[2] else 0,
            "missed_doses": missed_doses,
            "consecutive_days": consecutive_days,
            "daily_adherence": daily_adherence,
            "weekly_adherence": weekly_adherence
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno do servidor")
    finally:
        cursor.close()
        conn.close()
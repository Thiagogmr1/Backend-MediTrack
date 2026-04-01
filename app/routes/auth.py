from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import get_connection
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter()

class DoctorRegister(BaseModel):
    name: str
    email: str
    password: str
    birth_date: Optional[str] = None

class PatientRegister(BaseModel):
    name: str
    cpf: str
    birth_date: str

class DoctorLogin(BaseModel):
    email: str
    password: str

class PatientLogin(BaseModel):
    cpf: str
    birth_date: str

@router.post("/register/doctor")
def register_doctor(user: DoctorRegister):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email já cadastrado")

        hashed = hash_password(user.password)

        cursor.execute(
            "INSERT INTO users (name, email, password, role, birth_date) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user.name, user.email, hashed, "doctor", user.birth_date)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()

        return {"message": "Médico cadastrado com sucesso!", "user_id": user_id}

    except HTTPException as e:
        raise e
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.post("/register/patient")
def register_patient(user: PatientRegister):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE cpf = %s", (user.cpf,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="CPF já cadastrado")

        cursor.execute(
            "INSERT INTO users (name, cpf, birth_date, role) VALUES (%s, %s, %s, %s) RETURNING id",
            (user.name, user.cpf, user.birth_date, "patient")
        )
        user_id = cursor.fetchone()[0]
        conn.commit()

        return {"message": "Paciente cadastrado com sucesso!", "user_id": user_id}

    except HTTPException as e:
        raise e
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.post("/login/doctor")
def login_doctor(user: DoctorLogin):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, name, password, role FROM users WHERE email = %s AND role = 'doctor'", (user.email,))
        db_user = cursor.fetchone()

        if not db_user:
            raise HTTPException(status_code=401, detail="Email ou senha incorretos")

        if not verify_password(user.password, db_user[2]):
            raise HTTPException(status_code=401, detail="Email ou senha incorretos")

        token = create_access_token({"sub": str(db_user[0]), "role": db_user[3]})

        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": db_user[0],
            "name": db_user[1],
            "role": db_user[3]
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.post("/login/patient")
def login_patient(user: PatientLogin):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id, name, role FROM users WHERE cpf = %s AND birth_date = %s AND role = 'patient'",
            (user.cpf, user.birth_date)
        )
        db_user = cursor.fetchone()

        if not db_user:
            raise HTTPException(status_code=401, detail="CPF ou data de nascimento incorretos")

        token = create_access_token({"sub": str(db_user[0]), "role": db_user[2]})

        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": db_user[0],
            "name": db_user[1],
            "role": db_user[2]
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
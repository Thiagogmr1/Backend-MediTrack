from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_connection
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter()

class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    role: str

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(user: UserRegister):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email já cadastrado")

        hashed = hash_password(user.password)

        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s) RETURNING id",
            (user.name, user.email, hashed, user.role)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()

        return {"message": "Usuário cadastrado com sucesso!", "user_id": user_id}

    except HTTPException as e:
        raise e
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.post("/login")
def login(user: UserLogin):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, name, password, role FROM users WHERE email = %s", (user.email,))
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
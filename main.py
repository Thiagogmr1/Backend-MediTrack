from fastapi import FastAPI
from app.database import get_connection
from app.routes import auth, prescriptions, doses

app = FastAPI()

app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
app.include_router(prescriptions.router, prefix="/prescriptions", tags=["Prescrições"])
app.include_router(doses.router, prefix="/doses", tags=["Doses"])

@app.get("/")
def root():
    return {"message": "API funcionando!"}

@app.get("/test-db")
def test_db():
    try:
        conn = get_connection()
        conn.close()
        return {"message": "Conexão com o banco de dados funcionando!"}
    except Exception as e:
        return {"error": str(e)}
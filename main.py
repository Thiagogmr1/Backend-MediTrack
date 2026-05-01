from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_connection
from app.routes import auth, prescriptions, doses, dashboard, patients, webhook
from app.scheduler import start_scheduler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
app.include_router(prescriptions.router, prefix="/prescriptions", tags=["Prescrições"])
app.include_router(doses.router, prefix="/doses", tags=["Doses"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(patients.router, prefix="/patients", tags=["Pacientes"])
app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])

@app.on_event("startup")
def startup_event():
    start_scheduler()

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
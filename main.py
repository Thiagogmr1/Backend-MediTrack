import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.database import get_connection
from app.routes import auth, prescriptions, doses, dashboard, patients, webhook
from app.scheduler import start_scheduler
from contextlib import asynccontextmanager

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield

app = FastAPI(lifespan=lifespan)

origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
app.include_router(prescriptions.router, prefix="/prescriptions", tags=["Prescrições"])
app.include_router(doses.router, prefix="/doses", tags=["Doses"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(patients.router, prefix="/patients", tags=["Pacientes"])
app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])
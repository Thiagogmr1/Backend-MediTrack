from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
    
def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return payload

def require_role(role: str):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado"
            )
        return current_user
    return role_checker


# ## 🧠 Entendendo o código:

# | Parte | O que faz |
# |-------|-----------|
# | `SECRET_KEY` | Chave secreta para assinar os tokens JWT |
# | `hash_password` | Criptografa a senha antes de salvar no banco |
# | `verify_password` | Compara a senha digitada com a senha criptografada |
# | `create_access_token` | Gera o token JWT após o login |
# | `decode_access_token` | Valida e lê o token JWT |
# | `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expira em 24 horas |



# ⚠️ Precisamos adicionar a `SECRET_KEY` no arquivo `.env`. Abre o `.env` e adiciona essa linha:

# SECRET_KEY=uma_chave_secreta_bem_longa_e_aleatoria_aqui
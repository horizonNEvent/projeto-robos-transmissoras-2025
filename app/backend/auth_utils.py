import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

# Configurações de Segurança
# EM PRODUÇÃO, USAR UMA VARIÁVEL DE AMBIENTE FORTE!
SECRET_KEY = "bruno-secret-key-tust-robo-system-very-safe"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 Horas

def verify_password(plain_password, hashed_password):
    """
    Verifica se a senha em texto plano bate com o hash bcrypt.
    """
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
        
    return bcrypt.checkpw(plain_password, hashed_password)

def get_password_hash(password):
    """
    Gera o hash bcrypt da senha.
    """
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

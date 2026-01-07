from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..auth_utils import verify_password, get_password_hash, create_access_token, SECRET_KEY, ALGORITHM
from jose import jwt, JWTError

from ..email_utils import send_confirmation_email
EMAIL_ENABLED = True

router = APIRouter(tags=["auth"])

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/auth/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
    
    if not verify_password(user_data.password, user.hashed_password):
         raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
    
    # Opcional: Impedir login se não verificado? 
    # if not user.is_verified and user.email:
    #     raise HTTPException(status_code=400, detail="Email não verificado.")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/auth/register")
async def register(user_in: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Verifica se já existe
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username já cadastrado")
    
    new_user = models.User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        email=user_in.email,
        is_verified=False # Novo usuario nasce não verificado se tiver email
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Dispara email de confirmação
    if user_in.email and EMAIL_ENABLED:
        background_tasks.add_task(send_confirmation_email, user_in.email, user_in.username, user_in.password)
        return {"message": f"Usuário criado! Email de confirmação enviado para {user_in.email}", "username": new_user.username}

    return {"message": "Usuário criado com sucesso", "username": new_user.username}

@router.get("/confirmar-email", response_class=HTMLResponse)
def confirmar_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        scope = payload.get("scope")
        
        if not username or scope != "email_confirmation":
            raise HTTPException(status_code=400, detail="Token inválido")
            
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
             raise HTTPException(status_code=404, detail="Usuário não encontrado")
             
        user.is_verified = True
        db.commit()
        
        return """
        <html>
            <body style="font-family: Arial; text-align: center; padding-top: 50px; background-color: #f0f9ff;">
                <h1 style="color: #10b981;">✅ Email Confirmado com Sucesso!</h1>
                <p>Obrigado, seu cadastro foi validado.</p>
                <p>Você já pode fechar esta janela.</p>
            </body>
        </html>
        """
        
    except JWTError:
        return """
        <html>
            <body style="font-family: Arial; text-align: center; padding-top: 50px; background-color: #fee2e2;">
                <h1 style="color: #ef4444;">❌ Link Expirado ou Inválido</h1>
                <p>Por favor, solicite um novo link de confirmação.</p>
            </body>
        </html>
        """

class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    is_active: bool = True

@router.get("/auth/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    # Retorna lista segura (sem hash)
    return [
        {"id": u.id, "username": u.username, "email": u.email, "is_active": u.is_active, "is_verified": u.is_verified}
        for u in users
    ]

@router.put("/auth/users/{user_id}")
def update_user(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    user.email = user_in.email
    user.is_active = user_in.is_active
    
    if user_in.password and len(user_in.password.strip()) > 0:
        user.hashed_password = get_password_hash(user_in.password)
        
    db.commit()
    return {"message": "Usuário atualizado"}

@router.delete("/auth/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    db.delete(user)
    db.commit()
    return {"message": "Usuário removido"}

@router.post("/auth/resend-confirmation/{user_id}")
async def resend_confirmation(user_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if not user.email:
        raise HTTPException(status_code=400, detail="Usuário não possui email cadastrado.")
        
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Usuário já está verificado.")

    if EMAIL_ENABLED:
        background_tasks.add_task(send_confirmation_email, user.email, user.username)
        return {"message": f"Email de confirmação reenviado para {user.email}"}
    else:
        raise HTTPException(status_code=500, detail="Serviço de email não configurado.")

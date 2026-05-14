from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from pydantic import BaseModel
from typing import List

router = APIRouter(
    prefix="/ie-public",
    tags=["ie-public"],
)


class IeTargetCreate(BaseModel):
    codigo_ons: str
    nome: str
    ativo: bool = True


class IeTargetResponse(BaseModel):
    id: int
    codigo_ons: str
    nome: str
    ativo: bool

    class Config:
        orm_mode = True


@router.get("/targets", response_model=List[IeTargetResponse])
def list_targets(db: Session = Depends(get_db)):
    return db.query(models.IePublicTarget).all()


@router.post("/targets", response_model=IeTargetResponse)
def create_target(target: IeTargetCreate, db: Session = Depends(get_db)):
    exists = db.query(models.IePublicTarget).filter(
        models.IePublicTarget.codigo_ons == target.codigo_ons
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Código ONS já existe na lista WebIE Public.")

    db_target = models.IePublicTarget(
        codigo_ons=target.codigo_ons,
        nome=target.nome,
        ativo=target.ativo,
    )
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    return db_target


@router.delete("/targets/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db)):
    db_target = db.query(models.IePublicTarget).filter(models.IePublicTarget.id == target_id).first()
    if not db_target:
        raise HTTPException(status_code=404, detail="Target not found")

    db.delete(db_target)
    db.commit()
    return {"message": "Deletado com sucesso"}


@router.put("/targets/{target_id}/toggle")
def toggle_target(target_id: int, db: Session = Depends(get_db)):
    db_target = db.query(models.IePublicTarget).filter(models.IePublicTarget.id == target_id).first()
    if not db_target:
        raise HTTPException(status_code=404, detail="Target not found")

    db_target.ativo = not db_target.ativo
    db.commit()
    return {"message": f"Status alterado para {db_target.ativo}"}

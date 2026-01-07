from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os

from ..database import get_db
from .. import models
from pydantic import BaseModel

router = APIRouter(tags=["documents"])

class DocumentSchema(BaseModel):
    id: int
    execution_id: int | None
    robot_config_id: int | None
    filename: str
    file_path: str
    cnpj_extracted: str | None
    competence_extracted: str | None
    invoice_value: str | None
    base: str | None
    ons_code: str | None
    agent_name: str | None
    created_at: str

    class Config:
        from_attributes = True

@router.get("/documents", response_model=List[DocumentSchema])
def list_documents(db: Session = Depends(get_db)):
    """Lista todos os documentos validados e registrados no banco."""
    return db.query(models.DocumentRegistry).order_by(models.DocumentRegistry.id.desc()).all()

@router.get("/documents/download/{doc_id}")
def download_document(doc_id: int, db: Session = Depends(get_db)):
    """Permite o download de um documento específico pelo seu ID."""
    doc = db.query(models.DocumentRegistry).filter(models.DocumentRegistry.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado no servidor")
    
    return FileResponse(
        doc.file_path,
        filename=doc.filename,
        media_type='application/xml'
    )

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Remove um documento específico do banco e tenta apagar o arquivo físico."""
    doc = db.query(models.DocumentRegistry).filter(models.DocumentRegistry.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    
    # Tenta remover o arquivo físico
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except:
            pass
            
    db.delete(doc)
    db.commit()
    return {"message": "Documento removido"}

@router.delete("/documents/clear/all")
def clear_all_documents(db: Session = Depends(get_db)):
    """Limpa todos os registros de documentos validados (Não apaga arquivos físicos por segurança)."""
    db.query(models.DocumentRegistry).delete()
    db.commit()
    return {"message": "Repositório de documentos limpo"}

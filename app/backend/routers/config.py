from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from .. import models, database
from typing import List
from pydantic import BaseModel
import json

router = APIRouter(prefix="/config/robots", tags=["config"])

class RobotConfigSchema(BaseModel):
    id: int | None = None
    robot_type: str
    base: str
    label: str
    username: str
    password: str
    agents_json: str
    active: bool = True

    class Config:
        from_attributes = True

@router.get("", response_model=List[RobotConfigSchema])
def get_configs(db: Session = Depends(database.get_db)):
    return db.query(models.RobotConfig).all()

@router.post("")
def save_config(config: RobotConfigSchema, db: Session = Depends(database.get_db)):
    if config.id:
        db_config = db.query(models.RobotConfig).filter(models.RobotConfig.id == config.id).first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")
        db_config.robot_type = config.robot_type
        db_config.base = config.base
        db_config.label = config.label
        db_config.username = config.username
        db_config.password = config.password
        db_config.agents_json = config.agents_json
        db_config.active = config.active
    else:
        db_config = models.RobotConfig(**config.dict(exclude={'id'}))
        db.add(db_config)
    
    db.commit()
    return {"status": "saved", "id": db_config.id}

@router.delete("/{config_id}")
def delete_config(config_id: int, db: Session = Depends(database.get_db)):
    db_config = db.query(models.RobotConfig).filter(models.RobotConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(db_config)
    db.commit()
    return {"status": "deleted"}

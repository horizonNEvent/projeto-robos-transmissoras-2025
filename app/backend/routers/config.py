from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from .. import models, database
from typing import List
from pydantic import BaseModel
import json
from ..scheduler import reload_schedules

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

class RobotScheduleSchema(BaseModel):
    id: int | None = None
    robot_config_id: int
    schedule_time: str
    days_of_week: str
    target_competence: str
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

# --- Scheduling Endpoints ---

@router.get("/schedules/{robot_config_id}", response_model=List[RobotScheduleSchema])
def get_schedules(robot_config_id: int, db: Session = Depends(database.get_db)):
    return db.query(models.RobotSchedule).filter_by(robot_config_id=robot_config_id).all()

@router.post("/schedules")
def save_schedule(schedule: RobotScheduleSchema, db: Session = Depends(database.get_db)):
    if schedule.id:
        db_s = db.query(models.RobotSchedule).filter(models.RobotSchedule.id == schedule.id).first()
        if not db_s: raise HTTPException(status_code=404)
        db_s.schedule_time = schedule.schedule_time
        db_s.days_of_week = schedule.days_of_week
        db_s.target_competence = schedule.target_competence
        db_s.active = schedule.active
    else:
        db_s = models.RobotSchedule(**schedule.dict(exclude={'id'}))
        db.add(db_s)
    
    db.commit()
    reload_schedules() # Sync with APScheduler
    return {"status": "saved"}

@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(database.get_db)):
    db_s = db.query(models.RobotSchedule).filter(models.RobotSchedule.id == schedule_id).first()
    if db_s:
        db.delete(db_s)
        db.commit()
        reload_schedules()
    return {"status": "deleted"}

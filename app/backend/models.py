from sqlalchemy import  Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Empresa(Base):
    __tablename__ = 'empresas'
    
    id = Column(Integer, primary_key=True, index=True)
    codigo_ons = Column(String, unique=True, index=True)
    nome_empresa = Column(String)
    base = Column(String, default="AETE")
    ativo = Column(Boolean, default=True)

class Transmissora(Base):
    __tablename__ = 'transmissora'
    
    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String, unique=True, index=True) # Chave Única Principal
    codigo_ons = Column(String, index=True)
    sigla = Column(String)
    nome = Column(String)
    grupo = Column(String)
    # Campo para armazenar todas as outras colunas da planilha de forma dinâmica
    dados_json = Column(String) 
    ultima_atualizacao = Column(String)
class RobotConfig(Base):
    __tablename__ = 'robot_configs'
    
    id = Column(Integer, primary_key=True, index=True)
    robot_type = Column(String) # 'SIGET', 'WEBIE', etc.
    base = Column(String) # 'AETE', 'RE', 'AE', 'DE'
    label = Column(String) # Friendly name (e.g. 'Anemus 1')
    username = Column(String)
    password = Column(String)
    agents_json = Column(String) # List of ONS codes assigned to this credential
    active = Column(Boolean, default=True)
    
    # Scheduling fields
    schedule_time = Column(String, nullable=True) # e.g. "08:00"
    target_competence = Column(String, nullable=True) # e.g. "2026-01"
    last_success_competence = Column(String, nullable=True) # e.g. "2025-12"

class RobotSchedule(Base):
    __tablename__ = 'robot_schedules'
    
    id = Column(Integer, primary_key=True, index=True)
    robot_config_id = Column(Integer, index=True)
    schedule_time = Column(String)  # HH:MM
    days_of_week = Column(String)  # "MON,TUE,WED,THU,FRI,SAT,SUN"
    target_competence = Column(String)  # "CURRENT", "NEXT", "YYYY-MM"
    active = Column(Boolean, default=True)

class RobotExecution(Base):
    __tablename__ = 'robot_executions'
    
    id = Column(Integer, primary_key=True, index=True)
    robot_config_id = Column(Integer, index=True)
    start_time = Column(String)
    end_time = Column(String, nullable=True)
    status = Column(String)  # "RUNNING", "SUCCESS", "FAILED"
    logs = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    trigger_type = Column(String)  # "MANUAL", "SCHEDULED"

class DocumentRegistry(Base):
    __tablename__ = 'document_registry'
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, index=True)
    filename = Column(String)
    file_path = Column(String)
    file_hash = Column(String, index=True)  # To avoid physical duplicates
    cnpj_extracted = Column(String, index=True)
    competence_extracted = Column(String, index=True)
    invoice_value = Column(String, nullable=True)
    is_valid = Column(Boolean, default=True)
    validation_notes = Column(String, nullable=True)
    created_at = Column(String)

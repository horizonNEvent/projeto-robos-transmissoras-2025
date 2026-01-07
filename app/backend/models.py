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

class SigetPublicTarget(Base):
    __tablename__ = 'siget_public_targets'
    
    id = Column(Integer, primary_key=True, index=True)
    codigo_ons = Column(String, unique=True, index=True)
    nome = Column(String)
    ativo = Column(Boolean, default=True)

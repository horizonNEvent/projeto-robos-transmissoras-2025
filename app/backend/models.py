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

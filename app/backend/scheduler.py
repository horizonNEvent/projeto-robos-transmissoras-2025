import os
import time
import shutil
import json # Importação adicionada # Importação adicionada
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .database import SessionLocal
from .models import RobotSchedule, RobotConfig, RobotExecution, DocumentRegistry
from .xml_utils import extract_xml_data

# Instância Global do Scheduler
scheduler = BackgroundScheduler()

def process_downloaded_files(execution_id, robot_type, robot_config_id=None):
    """
    Varre a pasta de downloads, organiza por competência/CNPJ e registra no banco.
    """
    # Carrega empresas.json para lookup
    try:
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Data', 'empresas.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            EMPRESAS_DATA = json.load(f)
    except Exception as e:
        print(f"⚠️ Erro ao carregar empresas.json: {e}")
        EMPRESAS_DATA = {}

    db = SessionLocal()
    try:
        # Pasta temporária onde o robô jogou os arquivos
        # Ex: /app/downloads/TUST/CNT
        root_raw_dir = os.path.join(os.getcwd(), "downloads", "TUST", robot_type.upper())
        if not os.path.exists(root_raw_dir):
            print(f"⚠️ Pasta temporária {root_raw_dir} não encontrada em {root_raw_dir}")
            return

        # Varre recursivamente todas as subpastas em busca de XMLs
        found_files = 0
        for root, dirs, files in os.walk(root_raw_dir):
            for filename in files:
                data = {}
                if filename.endswith(".xml"):
                    found_files += 1
                    filepath = os.path.join(root, filename)
                    data = extract_xml_data(filepath)
                
                if data.get("valid"):
                    comp = data["competencia"]
                    cnpj = data["cnpj"]
                    
                    # Tenta inferir Base e ONS Code pela estrutura de pastas (Padrão: .../BASE/ONS_CODE/...)
                    # root exemplo: /app/downloads/TUST/CNT/DE/3748
                    path_parts = root.replace("\\", "/").split("/")
                    # Partes de trás para frente: [..., ROBOT_TYPE, BASE, ONS_CODE]
                    inferred_ons = path_parts[-1] if len(path_parts) > 0 else None
                    inferred_base = path_parts[-2] if len(path_parts) > 1 else None
                    
                    # Nome do Agente: Busca no JSON, fallback para DB, ultimo caso string vazia
                    agent_name = "Desconhecido"
                    
                    # 1. Tenta pegar do JSON (Mais rápido e confiável conforme parametrização)
                    if inferred_base and inferred_ons:
                        # Varre o JSON pra achar o match
                        # Estrutura: { "DE": { "3748": "Diamante" } }
                        base_data = EMPRESAS_DATA.get(inferred_base.upper()) or EMPRESAS_DATA.get(inferred_base)
                        if base_data:
                            agent_name = base_data.get(str(inferred_ons)) or agent_name

                    # 2. Se falhou e ainda é Desconhecido, tenta DB
                    if agent_name == "Desconhecido" and inferred_ons:
                        from .models import Empresa
                        emp = db.query(Empresa).filter_by(codigo_ons=str(inferred_ons)).first()
                        if emp:
                            agent_name = emp.nome_empresa

                    final_dir = os.path.join(os.getcwd(), "downloads", "FINAL", comp, cnpj)
                    os.makedirs(final_dir, exist_ok=True)
                    
                    final_path = os.path.join(final_dir, filename)
                    # Alterado de rename para copy2 para manter o arquivo na pasta temporária (Download zip)
                    shutil.copy2(filepath, final_path)
                    # os.rename(filepath, final_path)
                    
                    doc = DocumentRegistry(
                        execution_id=execution_id,
                        robot_config_id=robot_config_id,
                        filename=filename,
                        file_path=final_path,
                        file_hash=data["hash"],
                        cnpj_extracted=cnpj,
                        competence_extracted=comp,
                        invoice_value=data["valor"],
                        base=inferred_base,
                        ons_code=inferred_ons,
                        agent_name=agent_name,
                        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    exists = db.query(DocumentRegistry).filter_by(file_hash=data["hash"]).first()
                    if not exists:
                        db.add(doc)
                        print(f"📦 [VALIDADOR] Arquivo organizado e registrado: {agent_name} ({comp})")
                    else:
                        print(f"⏭️ [VALIDADOR] Arquivo já registrado: {filename}")
                elif filename.endswith(".xml"):
                    print(f"⚠️ [VALIDADOR] Arquivo XML inválido ou sem CNPJ: {filename}")
        
        if found_files == 0:
            print(f"📭 [VALIDADOR] Nenhum XML encontrado em {root_raw_dir}")
        else:
            print(f"🏁 [VALIDADOR] Processamento concluído. {found_files} arquivos encontrados.")
        
        db.commit()
    except Exception as e:
        print(f"❌ Erro na organização de arquivos: {e}")
    finally:
        db.close()

def scheduled_robot_task(schedule_id, robot_config_id):
    """
    Tarefa disparada pelo agendador (Mimetiza o botão manual).
    """
    db = SessionLocal()
    try:
        # 1. Busca a configuração
        config = db.query(RobotConfig).filter_by(id=robot_config_id).first()
        if not config:
            print(f"❌ [AGENDA] Configuração {robot_config_id} não encontrada.")
            return

        print(f"⏰ [AGENDA] Disparando Robô agendado: {config.label}")

        # 2. Registro de Execução
        execution = RobotExecution(
            robot_config_id=robot_config_id,
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="RUNNING",
            trigger_type="SCHEDULED"
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        # 3. Chama o robô (Lógica Manual IGUAL - Sem passar competência)
        from .routers.robots import run_robot_logic
        run_robot_logic(config.robot_type, config.id, None) 
        
        # 4. Organização de arquivos (Só pelo Scheduler)
        process_downloaded_files(execution.id, config.robot_type, config.id)
        
        execution.status = "SUCCESS"
        execution.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        print(f"❌ [AGENDA] Erro: {e}")
        if 'execution' in locals():
            execution.status = "FAILED"
            execution.error_message = str(e)
            execution.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    finally:
        db.commit()
        db.close()

def init_scheduler():
    """
    Inicia o scheduler e carrega os agendamentos do banco.
    """
    if not scheduler.running:
        scheduler.start()
        reload_schedules()
        print("🚀 Scheduler iniciado e agendas carregadas.")

def reload_schedules():
    """
    Limpa todos os jobs e recarrega do banco de dados.
    """
    scheduler.remove_all_jobs()
    db = SessionLocal()
    try:
        active_schedules = db.query(RobotSchedule).filter_by(active=True).all()
        for s in active_schedules:
            # Converte HH:MM para hora e minuto
            h, m = s.schedule_time.split(":")
            
            # Adiciona o job
            scheduler.add_job(
                scheduled_robot_task,
                trigger=CronTrigger(hour=h, minute=m),
                args=[s.id, s.robot_config_id],
                id=f"job_{s.id}",
                replace_existing=True
            )
            print(f"📌 Agendado: Robô {s.robot_config_id} às {s.schedule_time}")
    finally:
        db.close()

import os
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .database import SessionLocal
from .models import RobotSchedule, RobotConfig, RobotExecution, DocumentRegistry
from .xml_utils import extract_xml_data

# Instância Global do Scheduler
scheduler = BackgroundScheduler()

def process_downloaded_files(execution_id, robot_id):
    """
    Varre a pasta de downloads, organiza por competência/CNPJ e registra no banco.
    """
    db = SessionLocal()
    try:
        # Pasta temporária onde o robô jogou os arquivos
        # Ex: /app/downloads/TUST/CNT
        root_raw_dir = os.path.join(os.getcwd(), "downloads", "TUST", robot_id.upper())
        if not os.path.exists(root_raw_dir):
            print(f"⚠️ Pasta temporária {root_raw_dir} não encontrada.")
            return

        # Varre recursivamente todas as subpastas em busca de XMLs
        for root, dirs, files in os.walk(root_raw_dir):
            for filename in files:
                if filename.endswith(".xml"):
                    filepath = os.path.join(root, filename)
                    data = extract_xml_data(filepath)
                
                if data.get("valid"):
                    comp = data["competencia"]  # YYYY-MM
                    cnpj = data["cnpj"]
                    
                    # Define e cria a pasta final organizada
                    final_dir = os.path.join(os.getcwd(), "downloads", "FINAL", comp, cnpj)
                    os.makedirs(final_dir, exist_ok=True)
                    
                    final_path = os.path.join(final_dir, filename)
                    
                    # Move o arquivo para a pasta definitiva
                    os.rename(filepath, final_path)
                    
                    # Registra o documento no banco
                    doc = DocumentRegistry(
                        execution_id=execution_id,
                        filename=filename,
                        file_path=final_path,
                        file_hash=data["hash"],
                        cnpj_extracted=cnpj,
                        competence_extracted=comp,
                        invoice_value=data["valor"],
                        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    # Evita duplicidade no banco
                    exists = db.query(DocumentRegistry).filter_by(file_hash=data["hash"]).first()
                    if not exists:
                        db.add(doc)
                        print(f"📦 Arquivo organizado: {comp}/{cnpj}/{filename}")
        
        db.commit()
    except Exception as e:
        print(f"❌ Erro na organização de arquivos: {e}")
    finally:
        db.close()

def scheduled_robot_task(schedule_id, robot_config_id):
    """
    Tarefa inteligente disparada pelo agendador.
    """
    db = SessionLocal()
    try:
        # 1. Busca a configuração
        config = db.query(RobotConfig).filter_by(id=robot_config_id).first()
        if not config:
            print(f"❌ [AGENDA] Configuração {robot_config_id} não encontrada.")
            return

        print(f"⏰ [AGENDA] Robô: {config.label} | Alvo: {config.target_competence}")

        # 2. Idempotência: Se já temos esse documento válido, não roda o robô.
        if config.target_competence:
            exists = db.query(DocumentRegistry).filter(
                DocumentRegistry.robot_config_id == robot_config_id,
                DocumentRegistry.competence_extracted == config.target_competence
            ).first()
            if exists:
                print(f"✅ [AGENDA] Documento já validado para {config.target_competence}. Pulando...")
                return

        # 3. Registro de Execução
        execution = RobotExecution(
            robot_config_id=robot_config_id,
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="RUNNING",
            trigger_type="SCHEDULED"
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        # 4. Chama o robô (Lógica Manual IGUAL)
        from .routers.robots import run_robot_logic
        run_robot_logic(config.robot_type, config.id, config.target_competence) 
        
        # 5. Organização de arquivos (Só pelo Scheduler)
        process_downloaded_files(execution.id, config.robot_type)
        
        execution.status = "SUCCESS"
        execution.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Atualiza metadata de sucesso
        if config.target_competence:
            config.last_success_competence = config.target_competence

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

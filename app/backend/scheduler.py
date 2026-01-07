import os
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .database import SessionLocal
from .models import RobotSchedule, RobotConfig, RobotExecution, DocumentRegistry
from .routers.robots import run_robot_logic  # Função que vamos precisar refatorar ou usar
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
        raw_dir = os.path.join(os.getcwd(), "downloads", robot_id)
        if not os.path.exists(raw_dir):
            return

        for filename in os.listdir(raw_dir):
            if filename.endswith(".xml"):
                filepath = os.path.join(raw_dir, filename)
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
    Tarefa disparada pelo agendador.
    """
    print(f"⏰ [AGENDA] Iniciando execução agendada {schedule_id} para o robô {robot_config_id}")
    db = SessionLocal()
    
    # 1. Cria o registro de execução
    execution = RobotExecution(
        robot_config_id=robot_config_id,
        start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="RUNNING",
        trigger_type="SCHEDULED"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    try:
        # 2. Busca a configuração do robô
        config = db.query(RobotConfig).filter_by(id=robot_config_id).first()
        if not config:
            raise Exception("Configuração não encontrada")

        # 3. CHAMA A LÓGICA DO ROBÔ (Aqui integraríamos com seu script de robô)
        # Por enquanto, simulamos ou chamamos a função principal de execução
        # result = run_robot_logic(config) 
        
        # Simulação de espera do robô
        time.sleep(5) 
        
        # 4. Processa os arquivos baixados
        process_downloaded_files(execution.id, config.robot_type)
        
        execution.status = "SUCCESS"
        execution.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
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

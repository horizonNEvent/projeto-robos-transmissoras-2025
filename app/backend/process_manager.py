
import subprocess
import threading
import uuid
import time
import os
from datetime import datetime
from typing import Dict, List, Optional
import shlex

class RobotProcess:
    def __init__(self, id: str, name: str, command: List[str], log_dir: str, output_dir: Optional[str] = None, base_name: Optional[str] = None, agents: Optional[List[str]] = None):
        self.id = id
        self.name = name
        self.command = command
        self.output_dir = output_dir
        self.base_name = base_name
        self.agents = agents
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.status = "running"
        self.return_code: Optional[int] = None
        self.log_file = os.path.join(log_dir, f"{name}_{base_name or 'unknown'}_{id}.log")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        self.process = None # subprocess.Popen object
        self._stop_event = threading.Event()
        
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "base_name": self.base_name,
            "agents": self.agents,
            "command": " ".join(self.command),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "return_code": self.return_code,
            "output_dir": self.output_dir
        }

class ProcessManager:
    def __init__(self, log_dir: str = "logs"):
        self.processes: Dict[str, RobotProcess] = {}
        self.lock = threading.Lock()
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def start_process(self, name: str, command: List[str], output_dir: Optional[str] = None, base_name: Optional[str] = None, agents: Optional[List[str]] = None) -> str:
        proc_id = str(uuid.uuid4())
        
        # Criação do objeto de processo
        rp = RobotProcess(proc_id, name, command, self.log_dir, output_dir, base_name, agents)
        
        with self.lock:
            self.processes[proc_id] = rp

        # Inicia thread para rodar o processo sem bloquear
        thread = threading.Thread(target=self._run_process, args=(rp,))
        thread.daemon = True
        thread.start()
        
        return proc_id

    def _run_process(self, rp: RobotProcess):
        try:
            # Cria output_dir se não existir
            if rp.output_dir and not os.path.exists(rp.output_dir):
                os.makedirs(rp.output_dir, exist_ok=True)
                
            # Prepara arquivo de log
            with open(rp.log_file, "w", encoding="utf-8") as log_f:
                log_f.write(f"Iniciando processo {rp.name} (ID: {rp.id})\n")
                if rp.base_name:
                    log_f.write(f"Base: {rp.base_name}\n")
                if rp.agents:
                    log_f.write(f"Agentes: {', '.join(rp.agents)}\n")
                log_f.write(f"Comando: {' '.join(rp.command)}\n")
                log_f.write(f"Output Dir: {rp.output_dir}\n\n")

                # Inicia subprocesso
                process = subprocess.Popen(
                    rp.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding='utf-8',
                    errors='replace',
                    cwd=os.getcwd() # Garante cwd correto
                )
                rp.process = process

                # Loop de leitura de logs
                for line in process.stdout:
                    log_f.write(line)
                    log_f.flush()
                    
                    if rp._stop_event.is_set():
                        process.terminate()
                        break
                
                process.wait()
                rp.return_code = process.returncode
                rp.end_time = datetime.now()
                
                if rp._stop_event.is_set():
                    rp.status = "stopped"
                    log_f.write("\nProcesso interrompido pelo usuário.\n")
                elif rp.return_code == 0:
                    rp.status = "completed"
                    log_f.write("\nProcesso finalizado com sucesso.\n")
                else:
                    rp.status = "error"
                    log_f.write(f"\nProcesso finalizado com erro (Código {rp.return_code}).\n")

        except Exception as e:
            rp.status = "error"
            rp.end_time = datetime.now()
            # Tenta escrever no log se possível
            try:
                with open(rp.log_file, "a", encoding="utf-8") as log_f:
                    log_f.write(f"\nErro interno ao executar processo: {str(e)}\n")
            except:
                pass

    def stop_process(self, proc_id: str):
        with self.lock:
            # Busca também entre finalizados para update? Não, só running.
            if proc_id in self.processes:
                rp = self.processes[proc_id]
                if rp.status == "running":
                    rp._stop_event.set()
                    if rp.process:
                        try:
                            rp.process.terminate()
                        except:
                            pass
                    return True
        return False

    def get_process(self, proc_id: str):
        with self.lock:
            return self.processes.get(proc_id)

    def list_processes(self):
        with self.lock:
            return sorted(
                [p.to_dict() for p in self.processes.values()], 
                key=lambda x: x['start_time'], 
                reverse=True
            )

    def clear_finished(self):
        with self.lock:
            # Remove processos finalizados
            # Importante: Talvez limpar arquivos de log/temp? Por enquanto mantemos.
            to_remove = [pid for pid, p in self.processes.items() if p.status in ["completed", "error", "stopped"]]
            for pid in to_remove:
                del self.processes[pid]
            return len(to_remove)

    def get_logs(self, proc_id: str) -> str:
        with self.lock:
            rp = self.processes.get(proc_id)
            if rp and os.path.exists(rp.log_file):
                with open(rp.log_file, 'r', encoding="utf-8") as f:
                    return f.read()
            return "Log não encontrado ou processo inexistente."

# Instância global
manager = ProcessManager(log_dir=os.path.join(os.getcwd(), "logs", "robots"))

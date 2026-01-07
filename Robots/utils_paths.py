import os

def get_base_download_path(robot_name):
    """
    Determina a pasta base de downloads para um robô, 
    respeitando a variável de ambiente TUST_DOWNLOADS_BASE.
    """
    # Determina a raiz do projeto (assumindo que este arquivo está em /Robots)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Prioridade para variável de ambiente (usado no Docker)
    base = os.environ.get("TUST_DOWNLOADS_BASE")
    if not base:
        # Fallback para pasta local
        base = os.path.join(project_root, "downloads")
    
    # Estrutura padrão: {BASE}/TUST/{ROBOT_NAME}
    return os.path.join(base, "TUST", robot_name.upper())

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path

import os
import hashlib
from lxml import etree
from datetime import datetime

def calculate_file_hash(filepath):
    """Gera um hash SHA256 do arquivo para identificar duplicatas físicas."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Lê em blocos de 4kb para não estourar memória
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_xml_data(filepath):
    """
    Tenta extrair CNPJ, Competência e Valor de um XML de TUST.
    Retorna um dicionário com os dados encontrados.
    """
    try:
        # Carrega o XML
        tree = etree.parse(filepath)
        root = tree.getroot()
        
        # Remove namespaces para facilitar a busca (Gambi-bala técnica necessária para NFe/TUST)
        for elem in root.getiterator():
            if not (
                isinstance(elem.tag, str)
                and "}" in elem.tag
            ):
                continue
            elem.tag = elem.tag.split("}", 1)[1]

        # 1. CNPJ do Emissor (Transmissora)
        cnpj = None
        for path in [".//emit/CNPJ", ".//CNPJ", ".//emitente/CNPJ"]:
            elem = root.find(path)
            if elem is not None and elem.text:
                cnpj = elem.text.strip()
                break

        # 2. Competência (Mês/Ano)
        competencia = None
        for path in [".//dhEmi", ".//dEmi", ".//dhSaida", ".//dSaiEnt"]:
            elem = root.find(path)
            if elem is not None and elem.text:
                competencia = elem.text.strip()[:7]
                break
        
        if not competencia:
            competencia = datetime.now().strftime("%Y-%m")

        # 3. Valor Total
        valor = None
        for path in [".//vNF", ".//vServ", ".//vTotal", ".//vLiq"]:
            elem = root.find(path)
            if elem is not None and elem.text:
                valor = elem.text.strip()
                break

        return {
            "cnpj": cnpj,
            "competencia": competencia,
            "valor": valor,
            "hash": calculate_file_hash(filepath),
            "valid": cnpj is not None
        }

    except Exception as e:
        print(f"Erro ao ler XML {filepath}: {e}")
        return {
            "error": str(e),
            "valid": False
        }

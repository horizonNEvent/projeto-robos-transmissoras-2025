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

        # 1. Tentar achar o CNPJ do Emissor (Transmissora)
        # Geralmente em <emit><CNPJ>
        cnpj = None
        cnpj_elem = root.find(".//emit/CNPJ")
        if cnpj_elem is not None:
            cnpj = cnpj_elem.text

        # 2. Tentar achar a Competência (Mês/Ano)
        # Geralmente extraída da data de emissão <dhEmi> ou <ide><dEmi>
        competencia = None
        data_emi_elem = root.find(".//dhEmi") or root.find(".//dEmi")
        if data_emi_elem is not None:
            # Pega os primeiros 7 caracteres (YYYY-MM)
            # Ex: 2026-01-07T... -> 2026-01
            competencia = data_emi_elem.text[:7]

        # 3. Tentar achar o Valor Total
        # Geralmente em <total><ICMSTot><vNF>
        valor = None
        valor_elem = root.find(".//vNF") or root.find(".//vServ")
        if valor_elem is not None:
            valor = valor_elem.text

        return {
            "cnpj": cnpj,
            "competencia": competencia,
            "valor": valor,
            "hash": calculate_file_hash(filepath),
            "valid": cnpj is not None and competencia is not None
        }

    except Exception as e:
        print(f"Erro ao ler XML {filepath}: {e}")
        return {
            "error": str(e),
            "valid": False
        }

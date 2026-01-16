import os
import shutil
import re
import pdfplumber
from lxml import etree
from datetime import datetime

# ==========================
# UTIL
# ==========================

def normalizar_valor(valor):
    if not valor:
        return None
    return valor.replace(".", "").replace(",", ".").strip()

def normalizar_data_xml(data):
    try:
        return datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return None

def extrair_texto_pdf(path):
    texto = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
    return texto.upper()

# ==========================
# INDEXAÇÃO DE PDFs
# ==========================

def indexar_pdfs(base_dir):
    danfes = []
    boletos = []

    for nome in os.listdir(base_dir):
        if not nome.lower().endswith(".pdf"):
            continue

        path = os.path.join(base_dir, nome)
        texto = extrair_texto_pdf(path)

        # -------- DANFE --------
        chave = re.search(r'\d{44}', texto)
        if "DANFE" in texto and chave:
            danfes.append({
                "path": path,
                "chave": chave.group(0)
            })
            continue

        # -------- BOLETO --------
        if "ITAÚ" in texto or "PAGÁVEL" in texto:
            nf = re.search(r'(\d{3,6})\s*/\s*001', texto)
            valor = re.search(r'\d+,\d{2}', texto)
            datas = re.findall(r'\d{2}/\d{2}/\d{4}', texto)

            boletos.append({
                "path": path,
                "nf": nf.group(1) if nf else None,
                "valor": normalizar_valor(valor.group(0)) if valor else None,
                "datas": datas
            })

    return danfes, boletos

# ==========================
# XML
# ==========================

def ler_xml(path):
    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    tree = etree.parse(path)

    return {
        "chave": tree.findtext(".//nfe:chNFe", namespaces=ns),
        "nf": tree.findtext(".//nfe:nNF", namespaces=ns),
        "valor": normalizar_valor(tree.findtext(".//nfe:vDup", namespaces=ns)),
        "vencimento": normalizar_data_xml(
            tree.findtext(".//nfe:dVenc", namespaces=ns)
        )
    }

# ==========================
# ORGANIZA UMA PASTA
# ==========================

def organizar_pasta(base_dir):
    arquivos = os.listdir(base_dir)
    if not any(a.lower().endswith(".xml") for a in arquivos):
        return False  # nada a fazer

    print(f"\n📂 Processando: {base_dir}")

    danfes, boletos = indexar_pdfs(base_dir)

    for nome in arquivos:
        if not nome.lower().endswith(".xml"):
            continue

        xml_path = os.path.join(base_dir, nome)
        dados = ler_xml(xml_path)

        pasta_nf = os.path.join(base_dir, dados["chave"])
        os.makedirs(pasta_nf, exist_ok=True)

        shutil.move(xml_path, os.path.join(pasta_nf, "NF.xml"))
        print(f"  [XML] NF {dados['nf']}")

        # DANFE
        for d in danfes:
            if d["path"] and d["chave"] == dados["chave"]:
                shutil.move(
                    d["path"],
                    os.path.join(pasta_nf, f"DANFE_NF_{dados['nf']}.pdf")
                )
                d["path"] = None
                print(f"    [DANFE] OK")

        # BOLETO
        for b in boletos:
            if b["path"] is None:
                continue
            if b["nf"] != dados["nf"]:
                continue

            bate_valor = b["valor"] == dados["valor"]
            bate_venc = dados["vencimento"] in (b["datas"] or [])

            if bate_valor or bate_venc:
                shutil.move(
                    b["path"],
                    os.path.join(pasta_nf, f"BOLETO_{dados['nf']}_001.pdf")
                )
                b["path"] = None
                print(f"    [BOLETO] OK")

    return True

# ==========================
# MAIN
# ==========================

if __name__ == "__main__":
    caminho = input("Informe o caminho BASE (ex: ...\\MEZ\\RE):\n").strip('"')

    if not os.path.isdir(caminho):
        print("❌ Caminho inválido.")
        exit(1)

    processou = False

    for nome in os.listdir(caminho):
        sub = os.path.join(caminho, nome)
        if os.path.isdir(sub):
            if organizar_pasta(sub):
                processou = True

    if not processou:
        print("⚠️ Nenhuma subpasta com XML encontrada.")

    print("\n✅ Processamento finalizado.")

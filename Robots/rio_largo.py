import requests
import os
from datetime import datetime
import argparse

class RioLargoBot:
    def __init__(self, user_code):
        self.user_code = user_code
        self.base_url = "https://riolargotransmissora.com.br"
        self.session = requests.Session()
        # Mimic headers from HAR to avoid blocking
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/"
        })

    def login(self):
        """
        Performs login to retrieve the CGC (CNPJ) needed for listing files.
        """
        url = f"{self.base_url}/login.php"
        payload = {
            "acao": "VLDUSER",
            "cUser": self.user_code
        }
        
        print(f"Logging in with user code: {self.user_code}...")
        response = self.session.post(url, data=payload)
        response.raise_for_status()
        
        data = response.json()
        if data.get("status") == "OK":
            cgc = data.get("CGC")
            print(f"Login successful. CGC: {cgc}")
            return cgc
        else:
            raise Exception(f"Login failed: {data.get('msg')}")

    def get_files_list(self, cgc):
        """
        Retrieves the list of available documents (notas).
        """
        url = f"{self.base_url}/listarArquivos.php"
        payload = {
            "acao": "LISTAR",
            "cUser": cgc,        # The CGC returned from login
            "cCodCli": self.user_code # The original user code
        }
        
        print("Fetching file list...")
        response = self.session.post(url, data=payload)
        response.raise_for_status()
        
        # The response is HTML/Text but contains JSON content. 
        # Sometimes servers return encoding issues, but request.json() usually handles it.
        # Based on HAR, it returns: {"status": "OK", "notas": [...]}
        try:
            data = response.json()
        except requests.JSONDecodeError:
            # Fallback if raw text needs cleanup (HAR showed clear JSON but inside HTML response body potentially)
            # The HAR showed the content-type as text/html but the body was pure JSON string.
            print("Warning: Could not decode JSON directly, attempting to parse text...")
            import json
            data = json.loads(response.text)
            
        if data.get("status") == "OK":
            return data.get("notas", [])
        else:
            raise Exception("Failed to list files")

    def download_file(self, url, filepath):
        """
        Downloads a file from the given URL.
        """
        print(f"Downloading: {url}")
        try:
            response = self.session.get(url, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Saved to: {filepath}")
            else:
                print(f"Failed to download {url}. Status: {response.status_code}")
        except Exception as e:
            print(f"Error downloading {url}: {e}")

    def run(self, output_dir="downloads", target_date=None):
        """
        target_date: Optional string in 'YYYYMMDD' format (e.g., '20260116').
                     If provided, downloads files for that specific date.
                     If None, downloads only the most recent one.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Step 1: Login
        cgc = self.login()

        # Step 2: List Files
        notas = self.get_files_list(cgc)
        
        if not notas:
            print("No documents found.")
            return

        documents_to_process = []

        if target_date:
            # Filter by specific date
            print(f"Filtering for documents from date: {target_date}")
            documents_to_process = [n for n in notas if n['DtEmissao'] == target_date]
            
            if not documents_to_process:
                print(f"No documents found for date {target_date}.")
                
                # Check format just in case
                if "/" in target_date:
                     print("Note: The date format seems to be YYYYMMDD without separators based on robot logic.")
                
                return
        else:
            # Step 3: Find the most recent document
            # Sorting by DtEmissao (Issue Date) descending
            notas_sorted = sorted(notas, key=lambda x: x['DtEmissao'], reverse=True)
            if notas_sorted:
                documents_to_process = [notas_sorted[0]]
                print("No date specified. Defaulting to most recent document.")
        
        for doc in documents_to_process:
            print(f"Processing document: Date {doc['DtEmissao']}, Value {doc['totalNF']}")
            
            dt_emissao = doc['DtEmissao']
            danfe_num = doc['danfe']
            serie = doc['serie'].strip() # Remove whitespace from "2  "
            
            base_filename = f"{dt_emissao}_{danfe_num}_{serie}_{cgc}"
            
            pdf_filename = f"danfe_{base_filename}.pdf"
            xml_filename = f"xml_{base_filename}.xml"
            boleto_filename = f"boleto_{base_filename}.pdf"
            
            pdf_url = f"{self.base_url}/danfe/{cgc}/{pdf_filename}"
            xml_url = f"{self.base_url}/nfe/{cgc}/{xml_filename}"
            boleto_url = f"{self.base_url}/boleto/{cgc}/{boleto_filename}"

            # Step 5: Download and Log
            # XML
            self.log_download(cgc, danfe_num, serie, "XML")
            self.download_file(xml_url, os.path.join(output_dir, xml_filename))
            
            # PDF (Danfe)
            self.log_download(cgc, danfe_num, serie, "Danfe")
            self.download_file(pdf_url, os.path.join(output_dir, pdf_filename))
            
            # Boleto
            self.log_download(cgc, danfe_num, serie, "Boleto")
            self.download_file(boleto_url, os.path.join(output_dir, boleto_filename))

    def log_download(self, cgc, danfe, serie, file_type):
        """
        Logs the download action to the server (gravarlog.php).
        file_type should be: 'Danfe', 'XML', or 'Boleto'
        """
        url = f"{self.base_url}/gravarlog.php"
        # cNota format example: "Danfe 000041997_2"
        c_nota = f"{file_type} {danfe}_{serie}"
        
        payload = {
            "acao": "GRAVAR_DOWNLOAD",
            "cUser": self.user_code,
            "cCGC": cgc,
            "cNota": c_nota,
            "cTipo": file_type
        }
        
        try:
            # We don't strictly need the response, just sending the log event
            self.session.post(url, data=payload)
        except Exception as e:
            print(f"Warning: Failed to log download for {file_type}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rio Largo Transmissora Bot")
    parser.add_argument("--user", type=str, help="User Code (e.g., 3748)", required=False)
    parser.add_argument("--competencia", type=str, help="Date in YYYYMMDD format", default=None)
    parser.add_argument("--output_dir", type=str, default="downloads")
    
    # Arguments passed by the system
    parser.add_argument("--password", type=str, help="Ignored")
    parser.add_argument("--agente", type=str, help="Alternative for User Code")
    parser.add_argument("--empresa", type=str, help="Ignored")
    parser.add_argument("--headless", action="store_true", help="Ignored") 
    
    args = parser.parse_args()
    
    # Support both --user and --agente (backend often sends --agente)
    raw_codes = args.user or args.agente
    
    if not raw_codes:
        parser.error("You must provide either --user or --agente with the code (e.g. 3748)")
    
    # Handle multiple codes separated by comma
    codes = [c.strip() for c in raw_codes.split(',') if c.strip()]
    
    if not codes:
        print("No valid user codes found.")
    
    for code in codes:
        print(f"\n--- Processing Agent/User Code: {code} ---")
        try:
            bot = RioLargoBot(code)
            # Create specific directory for this agent
            agent_output_dir = os.path.join(args.output_dir, code)
            
            # If a date is passed via CLI, use it. Otherwise, defaults to None (most recent)
            bot.run(output_dir=agent_output_dir, target_date=args.competencia)
        except Exception as e:
            print(f"[X] Error processing agent {code}: {e}")

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.backend.models import Transmissora
except ImportError:
    from models import Transmissora  # type: ignore

from relatorio_geral import baixar_relatorio_com_login
from utils_paths import ensure_dir, get_base_download_path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AMSE")

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql_app.db"
)
DATABASE_URL = f"sqlite:///{DB_PATH}"
DEFAULT_FILENAME = "RelatorioCadastroGeral.xls"


class AmseScraper:
    """Baixa o Relatório Geral de Cadastro via Sintegre/SAAT (saatliquidacao.ons.org.br)."""

    def __init__(self, output_dir=None, exibir: str = "2"):
        self.exibir = exibir
        self.target_dir = output_dir or get_base_download_path("AMSE")
        ensure_dir(self.target_dir)

    def login(self, username: str, password: str) -> str | bool:
        """Autentica no ONS e retorna o caminho do .xls baixado."""
        destino = os.path.join(self.target_dir, DEFAULT_FILENAME)
        logger.info("Baixando relatório via Sintegre/SAAT (exibir=%s)...", self.exibir)
        try:
            path = baixar_relatorio_com_login(
                username,
                password,
                logger,
                exibir=self.exibir,
                destino=destino,
            )
            return str(path)
        except Exception as exc:
            logger.error("Falha ao baixar relatório AMSE/SAAT: %s", exc)
            return False


class AmseUpdater:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def process_file(self, file_path):
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return

        logger.info(f"Reading file: {file_path}")
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            logger.error(f"Error reading Excel: {e}")
            return

        df.columns = [str(c).upper().strip() for c in df.columns]
        logger.info(f"Columns found: {df.columns.tolist()}")

        session = self.Session()
        updated_count = 0
        new_count = 0

        try:
            col_cnpj = next((c for c in df.columns if "CNPJ" in c), None)
            col_nome = next(
                (c for c in df.columns if "RAZ" in c and "SOCIAL" in c), None
            )
            col_sigla = next((c for c in df.columns if "SIGLA" in c), None)
            col_ons = next(
                (
                    c
                    for c in df.columns
                    if "CODIGO" in c or "CDIGO" in c or "CÓDIGO" in c
                ),
                None,
            )

            if not col_cnpj:
                logger.error("Column CNPJ not found in Excel.")
                return

            for _, row in df.iterrows():
                raw_cnpj = row[col_cnpj]
                if pd.isna(raw_cnpj):
                    continue

                cnpj_clean = re.sub(r"[^0-9]", "", str(raw_cnpj))
                if not cnpj_clean:
                    continue

                nome = (
                    str(row[col_nome]).strip()
                    if col_nome and not pd.isna(row[col_nome])
                    else None
                )
                sigla = (
                    str(row[col_sigla]).strip()
                    if col_sigla and not pd.isna(row[col_sigla])
                    else None
                )
                cod_ons = (
                    str(row[col_ons]).strip()
                    if col_ons and not pd.isna(row[col_ons])
                    else None
                )

                transmissora = (
                    session.query(Transmissora).filter_by(cnpj=cnpj_clean).first()
                )

                is_new = False
                if not transmissora:
                    transmissora = Transmissora(cnpj=cnpj_clean)
                    is_new = True
                    new_count += 1
                else:
                    updated_count += 1

                if nome:
                    transmissora.nome = nome
                if sigla:
                    transmissora.sigla = sigla
                if cod_ons:
                    transmissora.codigo_ons = cod_ons

                import json as json_mod

                row_dict = {}
                for k, v in row.items():
                    row_dict[k] = None if pd.isna(v) else str(v)

                transmissora.dados_json = json_mod.dumps(row_dict)
                transmissora.ultima_atualizacao = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                if is_new:
                    session.add(transmissora)

            session.commit()
            logger.info(
                "Database update complete. New: %s, Updated: %s",
                new_count,
                updated_count,
            )

        except Exception as e:
            logger.error(f"Error updating database: {e}")
            session.rollback()
        finally:
            session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Baixa o Relatório Geral de Cadastro (AMSE/SAAT) e opcionalmente atualiza o banco."
    )
    parser.add_argument("--user", "--login", dest="user", help="E-mail/usuário ONS (Sintegre)")
    parser.add_argument(
        "--password", "--senha", dest="password", help="Senha ONS"
    )
    parser.add_argument("--output_dir", help="Pasta de saída do .xls")
    parser.add_argument(
        "--exibir",
        default="2",
        choices=("0", "1", "2"),
        help="0=Dados Gerais, 1=Representantes, 2=Ambos (padrão).",
    )
    parser.add_argument(
        "--credenciais",
        type=Path,
        help="JSON com login/senha (login + password ou senha).",
    )
    parser.add_argument("--headless", action="store_true", help="Ignorado (requests)")
    parser.add_argument(
        "--update-db", action="store_true", help="Atualizar banco após o download"
    )

    args = parser.parse_args()

    user = args.user
    password = args.password
    if (not user or not password) and args.credenciais:
        data = json.loads(args.credenciais.read_text(encoding="utf-8"))
        user = data.get("login") or data.get("user") or data.get("usuario")
        password = data.get("password") or data.get("senha")
        if user and password:
            logger.info("Credenciais lidas de %s", args.credenciais.name)

    if not user or not password:
        logger.error("Informe --user e --password (ou --credenciais).")
        sys.exit(1)

    scraper = AmseScraper(output_dir=args.output_dir, exibir=args.exibir)
    file_path = scraper.login(user, password)

    if not file_path:
        sys.exit(1)

    print(Path(file_path).resolve())

    if args.update_db:
        updater = AmseUpdater(DATABASE_URL)
        updater.process_file(file_path)

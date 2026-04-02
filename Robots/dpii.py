import requests
import os
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from base_robot import BaseRobot


class DPIIRobot(BaseRobot):
    """
    Robô DPII - Portal Dom Pedro (dompedro.useallcloud.com.br)
    Baixa faturas em aberto (XML de NF-e) para os agentes configurados.

    Parâmetros CLI (via BaseRobot):
        --empresa    : Base de agentes a filtrar (ex: AE, RE, DE) — opcional
        --agente     : Códigos ONS separados por vírgula (ex: 3859,3860) — opcional
        --competencia: Mês de referência no formato MM/AAAA ou AAAA-MM — opcional
        --output_dir : Pasta base para salvar os downloads

    Quando --agente não é passado, o robô carrega todos os agentes de
    empresas.json (filtrando por --empresa se fornecido).
    """

    BASE_PROXY_URL = "https://dompedro.useallcloud.com.br/"

    def __init__(self):
        super().__init__("dpii")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36",
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _carregar_empresas(self):
        """Carrega Data/empresas.json para resolução de nome do agente."""
        try:
            json_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "Data", "empresas.json"
            )
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Não foi possível carregar empresas.json: {e}")
            return {}

    def _resolver_agentes(self, empresas_data):
        """
        Retorna lista de (codigo_ons, base, nome) com base nos filtros CLI.
        Prioridade: --agente > empresas.json filtrado por --empresa.
        """
        agentes_alvo = self.get_agents()  # lista de strings de ONS passada via --agente
        empresa_filtro = (self.args.empresa or "").strip().upper()

        resultado = []

        for base, codigos_dict in empresas_data.items():
            if empresa_filtro and base.upper() != empresa_filtro:
                continue

            for codigo_ons, nome in codigos_dict.items():
                if agentes_alvo and str(codigo_ons).strip() not in agentes_alvo:
                    continue
                resultado.append((str(codigo_ons), base, nome))

        # Fallback: --agente sem correspondência no JSON → inclui do mesmo jeito
        if agentes_alvo and not resultado:
            self.logger.warning(
                "Nenhum agente encontrado no empresas.json para os ONS informados. "
                "Usando os códigos diretamente."
            )
            for ons in agentes_alvo:
                resultado.append((ons, empresa_filtro or "DPII", ons))

        return resultado

    def _competencia_alvo(self):
        """
        Retorna (mes, ano) do mês de referência.
        Aceita: MM/AAAA, AAAA-MM ou nenhum (usa mês corrente).
        """
        comp = (self.args.competencia or "").strip()
        if not comp:
            hoje = datetime.now()
            return hoje.month, hoje.year

        try:
            if "/" in comp:
                mes, ano = comp.split("/")
            elif "-" in comp:
                ano, mes = comp.split("-")
            else:
                raise ValueError("Formato inválido")
            return int(mes), int(ano)
        except Exception:
            self.logger.warning(
                f"Competência '{comp}' inválida. Usando mês corrente."
            )
            hoje = datetime.now()
            return hoje.month, hoje.year

    # ------------------------------------------------------------------
    # Lógica de Download
    # ------------------------------------------------------------------

    def _buscar_faturas_em_aberto(self, codigo_ons):
        """Retorna lista de faturas em aberto da API do portal."""
        url = self.BASE_PROXY_URL + "apiportaltransmissoras/api/VTcoFaturasParc/RecuperarFaturasEmAberto"
        try:
            resp = self.session.post(url, data={"Codigo": str(codigo_ons)}, timeout=30)
            if resp.status_code == 200:
                js = resp.json()
                if js.get("Success") and js.get("Content"):
                    return js["Content"][0].get("Faturas", [])
                else:
                    self.logger.warning(f"[ONS {codigo_ons}] Resposta sem faturas: {js.get('Message')}")
            else:
                self.logger.warning(f"[ONS {codigo_ons}] HTTP {resp.status_code} ao buscar faturas.")
        except Exception as e:
            self.logger.error(f"[ONS {codigo_ons}] Erro ao buscar faturas: {e}")
        return []

    def _obter_link_xml(self, codigo_nf):
        """Solicita o link de download do ZIP com o XML da NF-e."""
        url = self.BASE_PROXY_URL + "apiportaltransmissoras/api/VTcoFaturasParc/GerarZIPXmlNFePorChave"
        try:
            resp = self.session.post(
                url,
                data={"CodigoNf": str(codigo_nf), "CodigoEmpresa": "1"},
                timeout=30,
            )
            if resp.status_code == 200:
                js = resp.json()
                if js.get("Success") and js.get("Content"):
                    return "https:" + js["Content"]
                self.logger.warning(f"[NF {codigo_nf}] Falha ao gerar link: {js.get('Message')}")
            else:
                self.logger.warning(f"[NF {codigo_nf}] HTTP {resp.status_code} ao obter link XML.")
        except Exception as e:
            self.logger.error(f"[NF {codigo_nf}] Erro ao obter link XML: {e}")
        return None

    def _processar_fatura(self, codigo_nf, codigo_ons, base, nome, mes_alvo, ano_alvo):
        """Baixa, extrai e valida a fatura. Salva se for do mês correto."""
        link = self._obter_link_xml(codigo_nf)
        if not link:
            return

        try:
            zip_resp = self.session.get(link, timeout=60)
            if zip_resp.status_code != 200:
                self.logger.warning(f"[NF {codigo_nf}] HTTP {zip_resp.status_code} ao baixar ZIP.")
                return

            # Pasta temp isolada por NF
            pasta_temp = os.path.join(self.get_output_path(), base, str(codigo_ons), "temp")
            os.makedirs(pasta_temp, exist_ok=True)
            temp_zip = os.path.join(pasta_temp, f"{codigo_nf}.zip")

            with open(temp_zip, "wb") as f:
                f.write(zip_resp.content)

            with zipfile.ZipFile(temp_zip, "r") as zf:
                xml_files = [n for n in zf.namelist() if n.endswith(".xml")]
                if not xml_files:
                    self.logger.warning(f"[NF {codigo_nf}] ZIP sem arquivo XML.")
                    return

                xml_content = zf.read(xml_files[0])
                root = ET.fromstring(xml_content)

                ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
                dh_emi_el = root.find(".//nfe:dhEmi", ns)
                if dh_emi_el is None:
                    self.logger.warning(f"[NF {codigo_nf}] dhEmi não encontrado no XML.")
                    return

                data_emissao = datetime.strptime(
                    dh_emi_el.text.split("T")[0], "%Y-%m-%d"
                )

                if data_emissao.month == mes_alvo and data_emissao.year == ano_alvo:
                    # Pasta destino: output_dir / base / codigo_ons /
                    pasta_destino = os.path.join(
                        self.get_output_path(), base, str(codigo_ons)
                    )
                    os.makedirs(pasta_destino, exist_ok=True)
                    zf.extractall(pasta_destino)
                    self.logger.info(
                        f"✅ [NF {codigo_nf}] {nome} ({base}) — "
                        f"{data_emissao.strftime('%m/%Y')} salvo em {pasta_destino}"
                    )
                else:
                    self.logger.info(
                        f"⏭  [NF {codigo_nf}] {nome} ignorado "
                        f"(emissão: {data_emissao.strftime('%m/%Y')}, "
                        f"alvo: {mes_alvo:02d}/{ano_alvo})"
                    )

        except zipfile.BadZipFile:
            self.logger.error(f"[NF {codigo_nf}] Arquivo ZIP corrompido.")
        except Exception as e:
            self.logger.error(f"[NF {codigo_nf}] Erro inesperado: {e}")
        finally:
            # Remove temp
            try:
                if os.path.exists(temp_zip):
                    os.remove(temp_zip)
                if os.path.exists(pasta_temp) and not os.listdir(pasta_temp):
                    os.rmdir(pasta_temp)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Ponto de entrada
    # ------------------------------------------------------------------

    def run(self):
        mes_alvo, ano_alvo = self._competencia_alvo()
        self.logger.info(
            f"🚀 DPII iniciado — competência alvo: {mes_alvo:02d}/{ano_alvo}"
        )

        empresas_data = self._carregar_empresas()
        agentes = self._resolver_agentes(empresas_data)

        if not agentes:
            self.logger.warning("Nenhum agente para processar. Verifique --empresa / --agente.")
            return

        self.logger.info(f"📋 {len(agentes)} agente(s) a processar.")

        for codigo_ons, base, nome in agentes:
            self.logger.info(f"\n--- ONS {codigo_ons} | {nome} ({base}) ---")
            faturas = self._buscar_faturas_em_aberto(codigo_ons)

            if not faturas:
                self.logger.info(f"Nenhuma fatura em aberto para ONS {codigo_ons}.")
                continue

            for fatura in faturas:
                codigo_nf = fatura.get("CodigoCodNota")
                if not codigo_nf:
                    continue
                self._processar_fatura(codigo_nf, codigo_ons, base, nome, mes_alvo, ano_alvo)

        self.logger.info("🏁 DPII finalizado.")


if __name__ == "__main__":
    bot = DPIIRobot()
    bot.run()

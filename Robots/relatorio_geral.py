"""
Download do Relatório Geral de Cadastro de Agentes (XLS) via SAAT/ONS (Sintegre + SSO).

Fluxo:
  1) Login Keycloak (sintegre.ons.org.br)
  2) Federação POPs + DecidePerfil (perfil Agente Usuário / Liquidação)
  3) AMSE_frm_RelCadastroGeral.aspx — gerar, aguardar, baixar XLS
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SAAT_ORIGIN = "https://saatliquidacao.ons.org.br"
SINTEGRE_START = "https://sintegre.ons.org.br/"
REPORT_PATH = "/amse/amse/webforms/relatorios/AMSE_frm_RelCadastroGeral.aspx"
SAAT_AGENT_PERF_URL = (
    f"{SAAT_ORIGIN}/amse/amse/webforms/representantes/"
    "AMSE_frm_agenteperfagente_s.aspx?oper=N"
)
DECIDE_PERFIL_URL = f"{SAAT_ORIGIN}/AMSE/DecidePerfil.aspx"

DDL_EXIBIR = "_ctl0:ContentPlaceHolder1:ddl_exibir"
DDL_EXIBIR_TARGET = "_ctl0$ContentPlaceHolder1$ddl_exibir"
BTN_BAIXAR = "_ctl0:ContentPlaceHolder1:ibt_Baixar"
BTN_EXCEL = "_ctl0:ContentPlaceHolder1:ibt_Excel"


def _apply_browser_headers(session: requests.Session) -> None:
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }
    )


def _clean_label(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).split())


def _collect_form_payload(form: Any, overrides: dict[str, str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for tag in form.find_all("input"):
        name = tag.get("name")
        if not name:
            continue
        typ = (tag.get("type") or "text").lower()
        if typ in ("checkbox", "radio"):
            if tag.has_attr("checked"):
                data[name] = tag.get("value", "on")
            continue
        if typ == "submit":
            continue
        data[name] = tag.get("value") or ""
    for tag in form.find_all("select"):
        name = tag.get("name")
        if not name:
            continue
        selected = tag.find("option", selected=True) or tag.find("option")
        data[name] = selected.get("value", "") if selected else ""
    for tag in form.find_all("textarea"):
        name = tag.get("name")
        if name:
            data[name] = tag.string or ""
    data.update(overrides)
    return data


def _pick_aspnet_form(soup: BeautifulSoup) -> Any:
    return soup.find("form", id="aspnetForm") or soup.find("form")


def _follow_auto_forms(
    session: requests.Session,
    response: requests.Response,
    logger: logging.Logger,
    *,
    max_hops: int = 10,
) -> requests.Response:
    current = response
    for hop in range(max_hops):
        soup = BeautifulSoup(current.text, "html.parser")
        form = soup.find("form", id="FormRedirect") or soup.find("form")
        if not form:
            return current
        action = form.get("action") or current.url
        if not str(action).startswith("http"):
            action = urljoin(current.url, str(action))
        payload = {
            inp.get("name"): inp.get("value", "")
            for inp in form.find_all("input")
            if inp.get("name")
        }
        logger.debug("Federation hop %s: POST %s", hop + 1, str(action)[:100])
        current = session.post(
            action, data=payload, allow_redirects=True, verify=False
        )
    return current


def _get_saat(
    session: requests.Session,
    url: str,
    logger: logging.Logger,
    *,
    referer: str | None = None,
) -> requests.Response:
    headers = {"Referer": referer} if referer else None
    response = session.get(
        url, allow_redirects=False, verify=False, headers=headers
    )
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("Location")
        if location:
            next_url = urljoin(url, location)
            response = session.get(
                next_url,
                allow_redirects=True,
                verify=False,
                headers=headers,
            )
    return _follow_auto_forms(session, response, logger)


def login_sintegre_ons(
    session: requests.Session,
    username: str,
    password: str,
    logger: logging.Logger,
) -> None:
    _apply_browser_headers(session)
    logger.info("Acessando Sintegre (%s)...", SINTEGRE_START)
    response = session.get(SINTEGRE_START, allow_redirects=True, verify=False)

    if (
        response.ok
        and "sso.ons.org.br" not in response.url
        and "sintegre.ons.org.br" in response.url
        and "kc-form-login" not in response.text
    ):
        logger.info("Sessão Sintegre já autenticada.")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.find("form", id="kc-form-login")
    if not form:
        raise RuntimeError("Formulário Keycloak (kc-form-login) não encontrado.")

    action_url = form.get("action") or response.url
    if not str(action_url).startswith("http"):
        action_url = urljoin(response.url, action_url)

    payload: dict[str, str] = {
        "username": username,
        "password": password,
        "credentialId": "",
    }
    for hidden in form.find_all("input", type="hidden"):
        name = hidden.get("name")
        if name and name not in payload:
            payload[name] = hidden.get("value") or ""

    logger.info("Enviando credenciais ao SSO...")
    login_response = session.post(
        action_url, data=payload, allow_redirects=True, verify=False
    )

    if "kc-feedback-text" in login_response.text:
        soup_err = BeautifulSoup(login_response.text, "html.parser")
        err = soup_err.find("span", class_="kc-feedback-text")
        msg = err.get_text(strip=True) if err else "credenciais inválidas"
        raise RuntimeError(f"Falha no login ONS: {msg}")

    current = login_response
    soup_oidc = BeautifulSoup(current.text, "html.parser")
    oidc_form = soup_oidc.find("form")
    if oidc_form and oidc_form.get("action"):
        oidc_payload = {
            i.get("name"): i.get("value", "")
            for i in oidc_form.find_all("input")
            if i.get("name")
        }
        logger.info("Concluindo handshake OIDC...")
        current = session.post(
            oidc_form["action"], data=oidc_payload, allow_redirects=True, verify=False
        )

    for _ in range(5):
        soup_loop = BeautifulSoup(current.text, "html.parser")
        target_form = soup_loop.find("form", id="FormRedirect")
        if not target_form:
            forms = soup_loop.find_all("form")
            if len(forms) == 1 and "working" in current.text.lower():
                target_form = forms[0]
        if not target_form:
            break
        action = target_form.get("action") or current.url
        loop_payload = {
            i.get("name"): i.get("value", "")
            for i in target_form.find_all("input")
            if i.get("name")
        }
        current = session.post(
            action, data=loop_payload, allow_redirects=True, verify=False
        )

    logger.info("Login Sintegre/ONS concluído.")


def _decide_perfil_return_url(resp: requests.Response) -> str | None:
    qs = parse_qs(urlparse(resp.url).query)
    if qs.get("ReturnUrl"):
        return unquote(qs["ReturnUrl"][0])
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form", id="aspnetForm")
    act = (form.get("action") or "") if form else ""
    if "ReturnUrl=" in act:
        fragment = act.split("ReturnUrl=", 1)[1]
        return unquote(fragment.split("&")[0])
    return None


def _resolve_decide_perfil(
    session: requests.Session,
    resp: requests.Response,
    logger: logging.Logger,
) -> requests.Response:
    cur = resp
    if "decideperfil" not in (cur.url or "").lower():
        return cur

    soup = BeautifulSoup(cur.text, "html.parser")
    form = soup.find("form", id="aspnetForm")
    if not form:
        logger.warning("DecidePerfil: aspnetForm não encontrado.")
        return cur

    sel = None
    for s in form.find_all("select"):
        name = s.get("name") or ""
        if "ListaPerfis" in name or "ddwListaPerfis" in name:
            sel = s
            break
    if not sel or not sel.get("name"):
        logger.warning("DecidePerfil: combo de perfis não encontrado.")
        return cur

    selected_opt = sel.find("option", selected=True)
    selected_val = (selected_opt.get("value") or "").strip() if selected_opt else ""

    opts: list[tuple[str, str]] = []
    for opt in sel.find_all("option"):
        v = (opt.get("value") or "").strip()
        if v:
            opts.append((v, _clean_label(opt.get_text())))

    if not opts:
        raise RuntimeError("DecidePerfil: nenhuma opção de perfil com valor.")

    preferidos = (
        "Gestor Cadastro",
        "Agente Transmissão",
        "Gestor Financeiro",
        "Agente Usuário",
        "Liquidação",
    )
    first_real = opts[0][0]
    perfil_rotulo = opts[0][1]
    logger.info("Perfis SAAT: %s", "; ".join(label for _, label in opts))
    for pref in preferidos:
        for v, label in opts:
            if pref.lower() in label.lower():
                first_real = v
                perfil_rotulo = label
                break
        else:
            continue
        break
    if selected_val and selected_opt:
        perfil_rotulo = _clean_label(selected_opt.get_text()) or perfil_rotulo
    session.saat_perfil = perfil_rotulo  # type: ignore[attr-defined]

    ctl_name = sel.get("name")
    assert ctl_name

    if not selected_val:
        event_target = ctl_name.replace(":", "$")
        payload = _collect_form_payload(
            form,
            {
                ctl_name: first_real,
                "__EVENTTARGET": event_target,
                "__EVENTARGUMENT": "",
            },
        )
        post_url = urljoin(cur.url, form.get("action") or cur.url)
        logger.info("DecidePerfil: selecionando perfil %r", perfil_rotulo[:60])
        cur = session.post(
            post_url,
            data=payload,
            headers={
                "Referer": cur.url,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SAAT_ORIGIN,
            },
            allow_redirects=True,
            verify=False,
        )
        cur.raise_for_status()

    if "decideperfil" in (cur.url or "").lower():
        ru = _decide_perfil_return_url(cur)
        if ru:
            if not ru.startswith("http"):
                ru = urljoin(SAAT_ORIGIN + "/", ru)
            logger.info("DecidePerfil: ReturnUrl -> %s", ru.split("/")[-1][:60])
            cur = session.get(
                ru,
                allow_redirects=True,
                verify=False,
                headers={"Referer": cur.url},
            )
            cur.raise_for_status()

    return cur


def preparar_sessao_saat(session: requests.Session, logger: logging.Logger) -> requests.Response:
    session.headers.setdefault("Origin", SAAT_ORIGIN)
    _apply_browser_headers(session)

    logger.info("Abrindo SAAT (federação POPs)...")
    r = _get_saat(session, SAAT_AGENT_PERF_URL, logger)
    r.raise_for_status()

    if "decideperfil" in r.url.lower():
        r = _resolve_decide_perfil(session, r, logger)
    elif "ListaPerfis" not in r.text:
        r2 = _get_saat(session, DECIDE_PERFIL_URL, logger, referer=r.url)
        if "decideperfil" in r2.url.lower() or "ListaPerfis" in r2.text:
            r = _resolve_decide_perfil(session, r2, logger)

    logger.info("Sessão SAAT pronta (%s).", r.url.split("/")[-1][:50])
    return r


def _report_post(
    session: requests.Session,
    page_resp: requests.Response,
    overrides: dict[str, str],
    *,
    stream: bool = False,
) -> requests.Response:
    soup = BeautifulSoup(page_resp.text, "html.parser")
    form = _pick_aspnet_form(soup)
    if not form:
        raise RuntimeError("Formulário do relatório não encontrado.")
    payload = _collect_form_payload(form, overrides)
    post_url = urljoin(page_resp.url, form.get("action") or page_resp.url)
    return session.post(
        post_url,
        data=payload,
        headers={
            "Referer": page_resp.url,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": SAAT_ORIGIN,
        },
        stream=stream,
        verify=False,
    )


def _find_exibir_select(soup: BeautifulSoup) -> Any:
    ddl = soup.find("select", {"id": "ddl_exibir"})
    if ddl:
        return ddl
    return soup.find("select", id=lambda x: x and x.endswith("ddl_exibir"))


def _find_status_span(soup: BeautifulSoup) -> Any:
    span = soup.find("span", {"id": "status_relatorio"})
    if span:
        return span
    return soup.find("span", id=lambda x: x and x.endswith("status_relatorio"))


def _find_baixar_button(soup: BeautifulSoup) -> Any:
    btn = soup.find("input", {"id": "ibt_Baixar"})
    if btn:
        return btn
    return soup.find("input", id=lambda x: x and x.endswith("ibt_Baixar"))


def _pagina_relatorio_ok(soup: BeautifulSoup) -> bool:
    return _find_exibir_select(soup) is not None


def _relatorio_disponivel_para_download(status_text: str) -> bool:
    """Evita falso positivo quando o texto diz que NÃO há relatório disponível."""
    st = status_text.upper()
    if any(
        x in st
        for x in (
            "NÃO HÁ",
            "NAO HA",
            "NENHUM RELATÓRIO",
            "NENHUM RELATORIO",
            "NÃO EXISTE",
            "NAO EXISTE",
        )
    ):
        return False
    return any(
        x in st
        for x in (
            "FOI DISPONIBILIZADO",
            "PRONTO PARA DOWNLOAD",
            "CLIQUE EM 'BAIXAR'",
            'CLIQUE EM "BAIXAR"',
        )
    )


def _valor_exibir_selecionado(soup: BeautifulSoup) -> str:
    ddl = _find_exibir_select(soup)
    if not ddl:
        return "0"
    selected = ddl.find("option", selected=True) or ddl.find(
        "option", {"selected": "selected"}
    )
    if selected and selected.get("value") is not None:
        return str(selected["value"])
    return "0"


def _selecionar_exibir(
    session: requests.Session,
    resp: requests.Response,
    exibir: str,
    logger: logging.Logger,
) -> requests.Response:
    """Mantém o combo na opção desejada (postback ASP.NET)."""
    soup = BeautifulSoup(resp.text, "html.parser")
    if _valor_exibir_selecionado(soup) == exibir:
        return resp
    logger.info("Ajustando combo exibir para %s...", exibir)
    return _report_post(
        session,
        resp,
        {
            "__EVENTTARGET": DDL_EXIBIR_TARGET,
            DDL_EXIBIR: exibir,
        },
    )


def _abrir_pagina_relatorio(
    session: requests.Session,
    referer: str,
    logger: logging.Logger,
) -> tuple[str, requests.Response]:
    report_url = (
        f"{SAAT_ORIGIN}{REPORT_PATH}?"
        f"{urlencode({'compatibilityMode': 'IE=8,chrome=1'})}"
    )
    logger.info("Abrindo relatório geral de cadastro...")
    r = _get_saat(session, report_url, logger, referer=referer)

    if "decideperfil" in r.url.lower():
        r = _resolve_decide_perfil(session, r, logger)
        r = _get_saat(session, report_url, logger, referer=r.url)

    if not _pagina_relatorio_ok(BeautifulSoup(r.text, "html.parser")):
        raise RuntimeError(
            f"Página do relatório não carregou (URL: {r.url}). "
            "Verifique perfil SAAT ou permissões da conta."
        )
    return report_url, r


def baixar_relatorio_cadastro_geral(
    session: requests.Session,
    logger: logging.Logger,
    *,
    exibir: str = "2",
    destino: str | Path,
) -> Path:
    """Baixa o XLS (sessão ONS já autenticada)."""
    if exibir not in ("0", "1", "2"):
        raise ValueError("exibir deve ser '0', '1' ou '2'.")

    out = Path(destino)
    saat_page = preparar_sessao_saat(session, logger)
    report_url, resp_report = _abrir_pagina_relatorio(session, saat_page.url, logger)

    max_retries = 60
    retry_interval = 5

    for attempt in range(max_retries):
        resp_report = _selecionar_exibir(session, resp_report, exibir, logger)
        soup_rep = BeautifulSoup(resp_report.text, "html.parser")
        status_span = _find_status_span(soup_rep)
        status_text = status_span.get_text(strip=True) if status_span else ""
        current_val = _valor_exibir_selecionado(soup_rep)

        logger.info(
            "Status (%s/%s): %s | exibir=%s",
            attempt + 1,
            max_retries,
            status_text,
            current_val,
        )

        if "PROCESSAMENTO" in status_text.upper():
            time.sleep(retry_interval)
            resp_report = _get_saat(
                session, report_url, logger, referer=resp_report.url
            )
            continue

        disponivel = _relatorio_disponivel_para_download(status_text)

        if disponivel:
            logger.info("Relatório disponível; iniciando download...")
            resp_download = _report_post(
                session,
                resp_report,
                {
                    "__EVENTTARGET": "",
                    "__EVENTARGUMENT": "",
                    DDL_EXIBIR: exibir,
                    f"{BTN_BAIXAR}.x": "30",
                    f"{BTN_BAIXAR}.y": "5",
                },
                stream=True,
            )
            if resp_download.status_code != 200:
                raise RuntimeError(
                    f"Download falhou com HTTP {resp_download.status_code}"
                )
            content_type = (resp_download.headers.get("Content-Type") or "").lower()
            if "html" in content_type and len(resp_download.content) < 50000:
                raise RuntimeError(
                    "Resposta do download parece HTML (login expirado ou erro SAAT)."
                )

            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("wb") as f:
                for chunk in resp_download.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info("Arquivo salvo em %s", out)
            return out.resolve()

        logger.info("Solicitando geração do Excel...")
        resp_report = _report_post(
            session,
            resp_report,
            {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                DDL_EXIBIR: exibir,
                f"{BTN_EXCEL}.x": "35",
                f"{BTN_EXCEL}.y": "10",
            },
        )
        resp_report = _selecionar_exibir(session, resp_report, exibir, logger)
        time.sleep(retry_interval)

    raise TimeoutError(
        f"Relatório não ficou disponível após {max_retries} tentativas "
        f"({max_retries * retry_interval}s)."
    )


def baixar_relatorio_com_login(
    login: str,
    senha: str,
    logger: logging.Logger,
    *,
    exibir: str = "2",
    destino: str | Path,
) -> Path:
    """Autentica no Sintegre/ONS e baixa o Relatório Geral de Cadastro (.xls)."""
    session = requests.Session()
    login_sintegre_ons(session, login.strip(), senha, logger)
    return baixar_relatorio_cadastro_geral(
        session, logger, exibir=exibir, destino=destino
    )

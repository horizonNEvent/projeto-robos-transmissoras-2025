from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from .. import models
from ..database import get_db

router = APIRouter(prefix="/grupos", tags=["grupos"])


# ---- Schemas Pydantic ----

class GrupoTransmissoraCreate(BaseModel):
    grupo: str
    portal_url: Optional[str] = None
    codigo_ons: str
    nome_transmissora: Optional[str] = None
    cnpj: Optional[str] = None


class GrupoTransmissoraUpdate(BaseModel):
    grupo: Optional[str] = None
    portal_url: Optional[str] = None
    nome_transmissora: Optional[str] = None
    cnpj: Optional[str] = None


# ---- Endpoints ----

@router.get("")
def list_grupos(db: Session = Depends(get_db)):
    """Retorna todos os registros de grupos_transmissoras."""
    rows = db.query(models.GrupoTransmissora).order_by(
        models.GrupoTransmissora.grupo,
        models.GrupoTransmissora.codigo_ons
    ).all()
    return rows


@router.get("/nomes")
def list_group_names(db: Session = Depends(get_db)):
    """Retorna a lista de grupos distintos (para filtros/selects)."""
    rows = db.query(models.GrupoTransmissora.grupo).distinct().order_by(
        models.GrupoTransmissora.grupo
    ).all()
    return [r[0] for r in rows]


@router.post("", status_code=201)
def create_grupo(payload: GrupoTransmissoraCreate, db: Session = Depends(get_db)):
    """Adiciona uma transmissora a um grupo."""
    # Verifica duplicata (mesmo grupo + mesmo código ONS)
    existing = db.query(models.GrupoTransmissora).filter(
        models.GrupoTransmissora.grupo == payload.grupo,
        models.GrupoTransmissora.codigo_ons == payload.codigo_ons
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Transmissora ONS {payload.codigo_ons} já está no grupo '{payload.grupo}'."
        )

    new_entry = models.GrupoTransmissora(
        grupo=payload.grupo.strip(),
        portal_url=payload.portal_url.strip() if payload.portal_url else None,
        codigo_ons=payload.codigo_ons.strip(),
        nome_transmissora=payload.nome_transmissora.strip() if payload.nome_transmissora else None,
        cnpj=payload.cnpj.strip() if payload.cnpj else None
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry


@router.put("/{entry_id}")
def update_grupo(entry_id: int, payload: GrupoTransmissoraUpdate, db: Session = Depends(get_db)):
    """Atualiza nome do grupo, URL do portal, nome ou CNPJ de um registro."""
    entry = db.query(models.GrupoTransmissora).filter(models.GrupoTransmissora.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")

    if payload.grupo is not None:
        entry.grupo = payload.grupo.strip()
    if payload.portal_url is not None:
        entry.portal_url = payload.portal_url.strip()
    if payload.nome_transmissora is not None:
        entry.nome_transmissora = payload.nome_transmissora.strip()
    if payload.cnpj is not None:
        entry.cnpj = payload.cnpj.strip()

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}")
def delete_grupo(entry_id: int, db: Session = Depends(get_db)):
    """Remove uma transmissora de um grupo."""
    entry = db.query(models.GrupoTransmissora).filter(models.GrupoTransmissora.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    db.delete(entry)
    db.commit()
    return {"message": "Removido com sucesso."}


@router.post("/seed")
def seed_from_csv(db: Session = Depends(get_db)):
    """
    Importa os dados do CSV 'Volumetria por grupo' embutido.
    Pode ser chamado uma única vez para popular o banco inicial.
    """
    # Dados extraídos do CSV (grupos → transmissoras)
    SEED_DATA = [
        # grupo, portal_url, codigo_ons, nome, cnpj
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1015","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1017","EXPANSION TRANSMISSAO DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1021","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1022","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1023","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1025","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1026","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1027","EXPANSION TRANSMISSAO ITUMBIARA MARIMBONDO S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1029","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1034","EMPRESA DE TRANSMISSAO DO ALTO URUGUAI S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1036","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1037","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1042","PORTO PRIMAVERA TRANSMISSORA DE ENERGIA S A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1045","ITUMBIARA TRANSMISSORA DE ENERGIA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1046","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1051","SERRA DA MESA TRANSMISSORA DE ENERGIA S. A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1052","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1054","INTEGRACAO TRANSMISSORA DE ENERGIA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1059","SERRA PARACATU TRANSMISSORA DE ENERGIA S A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1060","RIBEIRAO PRETO TRANSMISSORA DE ENERGIA S A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1061","POCOS DE CALDAS TRANSMISSORA DE ENERGIA S A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1062","EVOLTZ VII - FOZ DO IGUACU TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1066","BRASNORTE TRANSMISSORA DE ENERGIA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1070","EVOLTZ VI - CAMPOS NOVOS TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1072","EVOLTZ IV - SAO MATEUS TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1073","EVOLTZ V - LONDRINA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1079","IRACEMA TRANSMISSORA DE ENERGIA S. A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1089","LINHAS DE TRANSMISSAO DO ITATIM S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1096","CATXERE TRANSMISSORA DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1102","ARARAQUARA TRANSMISSORA DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1117","LINHAS DE TRANSMISSAO DE MONTES CLAROS S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1118","MANAUS TRANSMISSORA DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1119","LINHAS DE MACAPA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1120","LINHAS DE XINGU TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1124","ATLANTICO - CONCESSIONARIA DE TRANSMISSAO DE ENERGIA DO BRASIL S. A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1131","TRANSMISSORA PORTO ALEGRENSE DE ENERGIA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1132","EVOLTZ VIII - TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1133","SAO GOTARDO TRANSMISSORA DE ENERGIA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1143","LUZIANIA-NIQUELANDIA TRANSMISSORA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1150","NORTE BRASIL TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1162","INTERLIGACAO ELETRICA GARANHUNS S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1163","MATRINCHA TRANSMISSORA DE ENERGIA (TP NORTE) S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1164","CENTRAIS ELETRICAS DO NORTE DO BRASIL S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1173","PARANAIBA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1177","VALE DO SAO BARTOLOMEU TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1179","MARECHAL RONDON TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1180","SAO JOAO TRANSMISSORA DE ENERGIA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1181","ARGO V TRANSMISSAO DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1182","GUARACIABA TRANSMISSORA DE ENERGIA (TP SUL) S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1183","LAGO AZUL TRANSMISSAO S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1184","ARGO VI TRANSMISSAO DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1186","TRIANGULO MINEIRO TRANSMISSORA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1189","SAO PEDRO TRANSMISSORA DE ENERGIA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1191","AMAZONAS GERACAO E TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1195","BELO MONTE TRANSMISSORA DE ENERGIA SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1196","LINHAS DE TAUBATE TRANSMISSORA DE ENERGIA SA",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1198","CANTAREIRA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1199","TRANSMISSORA JOSE MARIA DE MACEDO DE ELETRICIDADE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1200","CANARANA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1201","OURILANDIA DO NORTE TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1206","SPE SANTA MARIA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1207","HORIZON TRANSMISSAO ES S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1208","PARANAITA RIBEIRAOZINHO TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1212","LAGOA NOVA TRANSMISSORA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1216","SPE SANTA LUCIA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1217","ARCOVERDE TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1220","EQUATORIAL TRANSMISSORA 8 SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1221","ENERGISA PARANAITA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1222","XINGU RIO TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1224","ARGO TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1226","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1227","GIOVANNI SANGUINETTI TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1228","MARIANA TRANSMISSORA DE ENERGIA ELETRICA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1229","SE VINEYARDS TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1230","EQUATORIAL TRANSMISSORA 1 SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1231","EQUATORIAL TRANSMISSORA 2 SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1233","HORIZON TRANSMISSAO MA II S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1235","LEST - LINHAS DE ENERGIA DO SERTAO TRANSMISSORA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1239","CGI - TRANSMISSORA CAMPINA GRANDE IGARACU S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1241","ARGO III TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1242","ARTEON Z2 ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1243","ARTEON Z1 ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1244","MANTIQUEIRA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1249","BELEM TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1252","EQUATORIAL TRANSMISSORA 4 SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1256","EQUATORIAL TRANSMISSORA 5 SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1261","ARGO IX TRANSMISSAO DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1264","EQUATORIAL TRANSMISSORA 6 SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1265","HORIZON TRANSMISSAO MA I S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1267","TRANSMISSORA SERTANEJA DE ELETRICIDADE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1268","COLINAS TRANSMISSORA DE ENERGIA ELETRICA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1269","EQUATORIAL TRANSMISSORA 3 SPE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1270","ALIANCA TRANSMISSORA DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1272","ARGO IV TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1273","ARGO II TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1275","CHIMARRAO TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1276","JANAUBA TRANSMISSORA DE ENERGIA ELETRICA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1281","ARTEON Z3 ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1286","TRANSMISSORA SP-MG S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1288","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1289","INTERLIGACAO ELETRICA AIMORES S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1291","SIMOES TRANSMISSORA DE ENERGIA ELETRICA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1295","GOYAZ TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1296","SOLARIS TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1297","MATA GRANDE TRANSMISSORA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1298","INTERLIGACAO ELETRICA PARAGUACU S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1299","SPE TRANSMISSORA DE ENERGIA LINHA VERDE II S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1303","BORBOREMA TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1304","FS TRANSMISSORA DE ENERGIA ELETRICA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1307","ITAMARACA TRANSMISSORA SPE SA",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1311","EMPRESA DE TRANSMISSAO TIMOTEO-MESQUITA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1316","TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1320","TBO - TRANSMISSORA BARREIRAS OESTE S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1321","MARITUBA TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1322","PAMPA TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1327","AGUA VERMELHA TRANSMISSORA DE ENERGIA S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1329","SILVANIA TRANSMISSORA DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1330","SPE TRANSMISSORA DE ENERGIA LINHA VERDE I S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1332","SAO FRANCISCO TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1337","DUNAS TRANSMISSAO DE ENERGIA S.A.",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1350","PITIGUARI TRANSMISSORA DE ENERGIA ELETRICA S/A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1353","RIALMA TRANSMISSORA DE ENERGIA V S.A",None),
        ("SigetPlus","https://sys.sigetplus.com.br/portal","1361","TANGARA TRANSMISSORA DE ENERGIA ELETRICA S/A",None),
        # Glorian
        ("Glorian","https://bp.glorian.com.br/bpglportal/","1202","CELG (LT ITUMBIARA - PARANAIBA)","07.779.299/0001-73"),
        ("Glorian","https://bp.glorian.com.br/bpglportal/","1205","CELG (SE LUZIANIA)","07.779.299/0001-73"),
        ("Glorian","https://bp.glorian.com.br/bpglportal/","1002","CELG-T","07.779.299/0001-73"),
        ("Glorian","https://bp.glorian.com.br/bpglportal/","1271","EDP LITORAL SUL","25.022.221/0001-91"),
        ("Glorian","https://bp.glorian.com.br/bpglportal/","1342","EDP NORTE","43.076.117/0002-42"),
        ("Glorian","https://bp.glorian.com.br/bpglportal/","1351","EDP NORTE 2","49.537.506/0002-04"),
        ("Glorian","https://bp.glorian.com.br/bpglportal/","1360","EDP NORTE NORDESTE 2",None),
        # Light
        ("Light","https://nfe.light.com.br/Web/wfmAutenticar.aspx","1020","LIGHT","1917818000136"),
        # Equatorial
        ("Equatorial","https://www.equatorial-t.com.br/segunda-via-transmissao/","1220","EQUATORIAL TRANSMISSORA 8 SPE S.A.","27.967.244/0001-02"),
        ("Equatorial","https://www.equatorial-t.com.br/segunda-via-transmissao/","1230","EQUATORIAL TRANSMISSORA 1 SPE S.A.","26.845.650/0001-21"),
        ("Equatorial","https://www.equatorial-t.com.br/segunda-via-transmissao/","1231","EQUATORIAL TRANSMISSORA 2 SPE S.A.","26.845.497/0001-32"),
        ("Equatorial","https://www.equatorial-t.com.br/segunda-via-transmissao/","1252","EQUATORIAL TRANSMISSORA 4 SPE S.A.","26.845.393/0001-28"),
        ("Equatorial","https://www.equatorial-t.com.br/segunda-via-transmissao/","1256","EQUATORIAL TRANSMISSORA 5 SPE S.A.","26.845.283/0001-66"),
        ("Equatorial","https://www.equatorial-t.com.br/segunda-via-transmissao/","1264","EQUATORIAL TRANSMISSORA 6 SPE S.A.","26.845.173/0001-02"),
        ("Equatorial","https://www.equatorial-t.com.br/segunda-via-transmissao/","1269","EQUATORIAL TRANSMISSORA 3 SPE S.A.","26.845.460/0001-04"),
        # Harpix
        ("Harpix","https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT","1262","MEZ 5 ENERGIA S.A.","40.215.231/0001-37"),
        ("Harpix","https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT","1308","MEZ 4 ENERGIA S.A.","31.231.479/0001-09"),
        ("Harpix","https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT","1325","MEZ 1 ENERGIA S.A.","33.950.678/0001-94"),
        ("Harpix","https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT","1334","MEZ 3 ENERGIA S.A.","31.231.893/0001-00"),
        ("Harpix","https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT","1338","MEZ 2 ENERGIA S.A.","36.243.890/0001-00"),
        # Rialma V
        ("Rialma V",None,"1353","RIALMA TRANSMISSORA DE ENERGIA V S.A.","51.715.706/0003-32"),
        # CEEE
        ("CEEE","https://getweb.cpfl.com.br/getweb/getweb.jsf","1001","CEEE – COMPANHIA ESTADUAL DE GERACAO E TRANSMISSAO DE ENERGIA ELETRICA (CEEE-GT)","92.715.812/0001-31"),
        ("CEEE","https://getweb.cpfl.com.br/getweb/getweb.jsf","1328","CEEE (CACHOEIRINHA 3)","92.715.812/0001-31"),
        ("CEEE","https://getweb.cpfl.com.br/getweb/getweb.jsf","1033","CEEE (LT P. MEDICI-PELOTAS 3)","92.715.812/0001-31"),
        # ONS
        ("ONS","https://sintegre.ons.org.br/","1","OPERADOR NACIONAL DO SISTEMA ELETRICO (ONS)","02.831.210/0002-38"),
        # I.E (ISA Energia)
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1009","Isa Energia",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1030","IE Jaguar 6",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1057","IE Minas Gerais",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1077","IE Jaguar 9",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1081","IESUL",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1083","IENNE",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1093","IE Jaguar 8",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1097","IE Serra do Japi",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1099","IESUL",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1109","IE Pinheiros",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1122","IE Itapura",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1223","IE Jaguar 6",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1240","Isa Energia",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1248","IE Itaquere",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1254","IE Tibagi",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1258","IE Aguapei",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1292","IE Tibagi",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1294","IE Itapura",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1301","IE Biguacu",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1305","IE Ivai",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1314","IE Itaunas",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1323","IE Minas Gerais",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1347","Evrecy",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1354","IE Riacho Grande",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1355","IE Tibagi",None),
        ("I.E","https://faturamento2.isaenergiabrasil.com.br/","1358","Isa Energia",None),
        # AXIA (Eletrobras)
        ("AXIA","https://portaldocliente.eletrobras.com","1191","AMAZONAS GT",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1006","CHESF",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1211","CHESF (LT MESSIAS-MACEIO II)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1136","CHESF (LT ACARAU II-SOBRAL III)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1188","CHESF (LT CEARA-MIRIM II-TOUROS)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1214","CHESF (LT Eunapolis-T.Freitas II C1)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1215","CHESF (LT Eunapolis-T.Freitas II C2)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1135","CHESF (LT EXTREMOZ II-J CAMARA)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1141","CHESF (LT IGAP. II-B.J.LAPA II)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1165","CHESF (LT IGAPORA II-IGAPORAIII)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1098","CHESF (LT JARDIM-PENEDO)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1064","CHESF (LT MILAGRES-COREMAS)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1194","CHESF (LT MORRO DO CHAPEU-IRECE)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1105","CHESF (LT NATALIII-ST.RITA-ZEBU)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1166","CHESF (LT PARAISO-LAGOA NOVA II)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1074","CHESF (LT PICOS-TAUA)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1055","CHESF (LT TAUA-MILAGRES)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1197","CHESF (LT TERESINA II-TERESINA III)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1126","CHESF (SE ARAPIRACA III)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1110","CHESF (SE CAMACARI IV)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1171","CHESF (SE MIRUEIRA II)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1170","CHESF (SE POLO)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1106","CHESF (SE SUAPE II e III)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1013","ELETROSUL",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1038","ELETROSUL (ARTEMIS)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1067","ELETROSUL (SE MISSOES)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1161","ELETROSUL (CONV URUGUAIANA)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1069","ELETROSUL (LT P.MEDICI-S.CRUZ 1)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1114","ELETROSUL (RS ENERGIA F DO CHAP)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1053","ELETROSUL (RS ENERGIA)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1115","ELETROSUL (RS ENERGIA IJUI2-CAX6)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1121","ELETROSUL (RS ENERGIA M.C-GARIB1)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1044","ELETROSUL (SC ENERGIA)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1167","ELETROSUL (SE IVINHEMA2)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1148","ETN",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1018","FURNAS",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1075","FURNAS (LT MACAE-CAMPOS)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1204","FURNAS (LT MASCARENHA-LINHARES)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1169","FURNAS (LT B.DESPACHO3-O.PRETO2)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1019","FURNAS (LT IBIUNA-BATEIAS)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1113","FURNAS (LT T.PRETO-ITAPETI-NORD)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1172","FURNAS (LT XAVANTES-PIRINEUS)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1152","FURNAS (SE ZONA OESTE)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1012","ELETRONORTE",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1111","ELETRONORTE (ETE)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1164","ELETRONORTE (LVTE)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1103","ELETRONORTE (PVTE)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1100","ELETRONORTE (RBTE)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1116","ELETRONORTE (SE L. DO R. VERDE)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1154","ELETRONORTE (SE TUCURUI)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1134","ELETRONORTE (LECH-J.TEIXE-C1 C2)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1156","ELETRONORTE (LECHU-J.TEIXE-C3)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1095","ELETRONORTE (LT RG - BALSAS)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1080","ELETRONORTE (SE MIRANDA II)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1129","ELETRONORTE (SE NOBRES)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1076","ELETRONORTE (SLUISII-SLUISIII)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1128","TDG",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1138","TSBE",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1174","FOTE",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1153","TSLE",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1178","TGO",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1107","CHESF (LT IBICOARA-BRUMADO II)",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1186","TMT",None),
        ("AXIA","https://portaldocliente.eletrobras.com","1357","ELETRONORTE (CALADINHO II)",None),
        # Celeo group
        ("Celeo","https://boleto.celeoredes.com.br/","1137","CAIUA",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1198","CANTAREIRA",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1068","COQUEIROS",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1031","CPTE",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1101","ENCRUZO NOVO",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1149","IMTE",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1065","JTE",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1127","LTC",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1078","PEDRAS",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1058","TRIANGULO",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1041","VCTE",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1082","BRILHANTE",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1146","BRILHANTE II",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1236","SITE",None),
        ("Celeo","https://boleto.celeoredes.com.br/","1318","PATE",None),
        # Neoenergia
        ("Neoenergia",None,"1007","AFLUENTE","10.338.320/0001-00"),
        ("Neoenergia",None,"1159","NARANDIBA","10.337.920/0001-53"),
        ("Neoenergia",None,"1185","POTIGUAR","17.873.542/0001-71"),
        ("Neoenergia",None,"1234","SOBRAL (EKTT 15-A)","27.853.556/0001-87"),
        ("Neoenergia",None,"1237","ATIBAIA (EKTT 13-A)","27.848.099/0001-32"),
        ("Neoenergia",None,"1247","BIGUACU","27.853.497/0001-47"),
        ("Neoenergia",None,"1246","DOURADOS","27.847.973/0001-17"),
        ("Neoenergia",None,"1274","SANTA LUZIA","28.443.625/0001-47"),
        ("Neoenergia",None,"1284","JALAPAO","28.443.567/0001-51"),
        ("Neoenergia",None,"1312","RIO FORMOSO","28.438.816/0001-10"),
        ("Neoenergia",None,"1313","LAGOA DOS PATOS","28.439.014/0001-25"),
        ("Neoenergia",None,"1324","VALE DO ITAJAI","28.443.452/0001-67"),
        ("Neoenergia",None,"1331","MORRO DO CHAPEU","28.438.834/0001-00"),
        ("Neoenergia",None,"1340","GUANABARA (EKTT-03)","28.438.913/0001-03"),
        ("Neoenergia",None,"1341","ITABAPOANA (EKTT-04)","28.439.049/0001-64"),
        ("Neoenergia",None,"1343","PARAISO","36.257.187/0001-50"),
        ("Neoenergia",None,"1344","ESTREITO (EKTT-08)","28.438.899/0001-48"),
        ("Neoenergia",None,"1348","ALTO DO PARABAIBA (EKTT-09)","28.438.777/0001-51"),
        # Cemig
        ("Cemig","https://www.cemig.com.br/","1004","CEMIG",None),
        ("Cemig","https://www.cemig.com.br/","1071","CENTROESTE DE MINAS",None),
        ("Cemig","https://www.cemig.com.br/","1139","SLTE",None),
        # Copel
        ("Copel",None,"1008","COPEL",None),
        ("Copel",None,"1155","COPEL (F. DO CHOPIM-S. OSORIO)",None),
        ("Copel",None,"1203","COPEL (LT ARARAQUARA 2-TAUBATE)",None),
        ("Copel",None,"1176","COPEL (LT BATEIAS-CTBA NORTE)",None),
        ("Copel",None,"1219","COPEL (LT CTBA LESTE-BLUMENAU)",None),
        ("Copel",None,"1091","COPEL (LT FOZ - CASCAVEL OESTE)",None),
        ("Copel",None,"1140","COPEL (SE CERQUILHO III)",None),
        ("Copel",None,"1193","COPEL (LT ASSIS - LONDRINA C2)",None),
        ("Copel",None,"1168","COPEL (LT ASSIS-P. PAULISTA II)",None),
        ("Copel",None,"1024","COPEL (LT BATEIAS-JAGUARIAIVA)",None),
        ("Copel",None,"1063","COPEL (LT BATEIAS-PILARZINHO)",None),
        ("Copel",None,"1187","COPEL (LT FOZ DO CHOPIM-REALEZA)",None),
        ("Copel",None,"1144","COSTA OESTE",None),
        ("Copel",None,"1043","UIRAPURU",None),
        ("Copel",None,"1218","MSGT",None),
        ("Copel",None,"1158","MARUMBI",None),
        # TBE
        ("TBE","https://portalcliente.tbenergia.com.br/","1010","EATE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1084","EBTE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1011","ECTE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1032","ENTE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1028","ERTE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1112","ESDE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1016","ETEP",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1151","ETSE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1049","LUMITRANS",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1050","STC",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1048","TRANSIRAPÉ",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1039","TRANSLESTE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1047","TRANSUDESTE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1232","EDTE",None),
        ("TBE","https://portalcliente.tbenergia.com.br/","1287","ESTE",None),
        # Alupar
        ("Alupar",None,"1040","STN - SISTEMA DE TRANSMISSAO NORDESTE S. A.",None),
        ("Alupar",None,"1320","RIALMA TRANSMISSORA DE ENERGIA IV S/A",None),
        ("Alupar",None,"1336","EMPRESA LITORANEA DE TRANSMISSAO DE ENERGIA S.A.",None),
        ("Alupar",None,"1056","EMPRESA DE TRANSMISSAO DO ESPIRITO SANTO S.A. ETES",None),
        ("Alupar",None,"1094","TRANSMISSORA MATOGROSSENSE DE ENERGIA S/A",None),
        ("Alupar",None,"1092","EMPRESA DE TRANSMISSAO DE ENERGIA DO MATO GROSSO S.A",None),
        ("Alupar",None,"1108","EMPRESA DE TRANSMISSAO DE VARZEA GRANDE S.A. - ETVG",None),
        ("Alupar",None,"1157","TRANSNORTE ENERGIA S.A",None),
        ("Alupar",None,"1225","EMPRESA TRANSMISSORA CAPIXABA S.A",None),
        ("Alupar",None,"1213","EMPRESA TRANSMISSORA AGRESTE POTIGUAR S.A",None),
        ("Alupar",None,"1263","TRANSMISSORA CAMINHO DO CAFE S.A.",None),
        ("Alupar",None,"1250","TRANSMISSORA PARAISO DE ENERGIA S.A.",None),
        ("Alupar",None,"1283","TRANSMISSORA SERRA DA MANTIQUEIRA S.A.",None),
        ("Alupar",None,"1245","ETB- EMPRESA DE TRANSMISSAO BAIANA S.A",None),
        ("Alupar",None,"1035","AMAZONIA- ELETRONORTE TRASMISSORA DE ENERGIA S.A",None),
        ("Alupar",None,"1339","TRANSMISSORA DE ENERGIA CENTRAL PAULISTANA S.A",None),
        # Energisa
        ("Energisa",None,"1266","ENERGISA AMAZONAS TRANSMISSORA DE ENERGIA S.A","34.025.997/0001-56"),
        ("Energisa",None,"1238","ENERGISA GOIAS TRANSMISSORA DE ENERGIA S.A","28.092.478/0001-08"),
        ("Energisa",None,"1260","ENERGISA PARA II TRANSMISSORA DE ENERGIA S.A","28.201.009/0001-80"),
        ("Energisa",None,"1221","ENERGISA PARANAITA TRANSMISSORA DE ENERGIA S.A","24.950.223/0001-88"),
        ("Energisa",None,"1309","ENERGISA TOCANTINS TRANSMISSORA DE ENERGIA S.A","32.655.445/0001-04"),
        ("Energisa",None,"1333","ENERGISA TOCANTINS TRANSMISSORA DE ENERGIA II S.A","34.025.976/0001-30"),
        ("Energisa",None,"1253","ENERGISA PARA I TRANSMISSORA DE ENERGIA S.A","28.091.111/0001-70"),
        ("Energisa",None,"1120","LINHAS DE XINGU TRANSMISSORA DE ENERGIA S.A","10.240.186/0001-00"),
        ("Energisa",None,"1119","LINHAS DE MACAPA TRANSMISSORA DE ENERGIA S.A","10.234.027/0001-00"),
        ("Energisa",None,"1196","LINHAS DE TAUBATE TRANSMISSORA DE ENERGIA S.A","14.395.590/0001-03"),
        ("Energisa",None,"1349","ENERGISA AMAPA TRANSMISSORA DE ENERGIA S.A","34.025.952/0001-81"),
        # Grupo CPFL
        ("Grupo CPFL",None,"1290","CPFL MARACANAÚ","31161310000200"),
        ("Grupo CPFL",None,"1310","CPFL SUL I","33062635000253"),
        ("Grupo CPFL",None,"1302","CPFL SUL II","33062600000214"),
        ("Grupo CPFL",None,"1160","CPFL-T","17079395000243"),
        ("Grupo CPFL",None,"1190","MORRO AGUDO","21986001000208"),
        ("Grupo CPFL",None,"1192","TESB","13289882000107"),
        # Zopone
        ("Zopone",None,"1319","ACRE","36242938000165"),
        ("Zopone",None,"1352","ACRE II","47439944000123"),
        ("Zopone",None,"1209","AGUA-AZUL","24905442000145"),
        ("Zopone",None,"1285","AMAPAR","32668008000117"),
        ("Zopone",None,"1293","LAGOS","31484507000191"),
    ]

    # Verifica se já foi seeded (evita duplicatas)
    count = db.query(models.GrupoTransmissora).count()
    if count > 0:
        return {"message": f"Seed ignorado: banco já possui {count} registros.", "inserted": 0}

    inserted = 0
    for grupo, portal_url, codigo_ons, nome, cnpj in SEED_DATA:
        entry = models.GrupoTransmissora(
            grupo=grupo,
            portal_url=portal_url,
            codigo_ons=codigo_ons,
            nome_transmissora=nome,
            cnpj=cnpj
        )
        db.add(entry)
        inserted += 1

    db.commit()
    return {"message": "Seed concluído com sucesso.", "inserted": inserted}

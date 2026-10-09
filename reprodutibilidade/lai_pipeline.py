#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
 LAI 15 ANOS — PIPELINE COMPLETO E REPRODUTÍVEL
 Da coleta automatizada à geração das análises discorridas (relatório em markdown)
==========================================================================================

Uso:
    python3 lai_pipeline.py --etapa diagnostico
    python3 lai_pipeline.py --etapa coleta        [--anos 2012-2025] [--textos 2015-2025]
    python3 lai_pipeline.py --etapa preparacao
    python3 lai_pipeline.py --etapa estruturada   [--ano 2025]
    python3 lai_pipeline.py --etapa textual       [--ano 2024] [--limiar 5]
    python3 lai_pipeline.py --etapa relatorio
    python3 lai_pipeline.py --etapa tudo

Requisitos: pandas, numpy, scikit-learn, matplotlib (opcional, para figuras).
Para o teste de lematização: spacy + pt_core_news_sm  (pip install spacy &&
python -m spacy download pt_core_news_sm)

--------------------------------------------------------------------------------
LIÇÕES DE CAMPO INCORPORADAS (todas medidas, não supostas)
--------------------------------------------------------------------------------
1. O download EXIGE cabeçalho de navegador (User-Agent + Referer da página oficial).
   Sem isso, o WAF da CGU devolve página de erro em vez do arquivo.
2. O WAF ESTRANGULA EM RAJADA: baixar vários arquivos seguidos derruba as últimas
   tentativas (o arquivo volta com ~2 KB). Por isso: pausa entre arquivos,
   até 3 tentativas e verificação de assinatura ZIP ('PK') antes de aceitar.
3. O ESQUEMA DA PÁGINA OFICIAL ESTÁ DESATUALIZADO. O CSV real de Pedidos tem 23
   colunas (a página lista 20) e o de Recursos tem 21 (a página lista 17).
   O script SEMPRE lê o cabeçalho do arquivo, nunca uma lista fixa.
4. Os CSVs são UTF-16 com separador ';' (não UTF-8, não vírgula).
5. Os campos de texto contêm quebras de linha dentro de aspas: a leitura precisa
   de quoting padrão; contar linhas com 'wc -l' subestima as linhas.
6. Os pacotes de texto são SUBCONJUNTO ESTRITO da base estruturada (100% dos
   identificadores existem na base; a fatia publicada vai de 74,3% a 55,8%).
   O script declara isso e mede a diferença em vez de supor cobertura total.
==========================================================================================
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import time
import unicodedata
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd

# ============================== CONFIGURAÇÃO ==============================

CONF = {
    "raiz": os.environ.get("LAI_RAIZ", "/root/lai"),
    "pagina_oficial": ("https://www.gov.br/acessoainformacao/pt-br/falabr/visao-geral/"
                       "busca-de-pedidos-e-respostas-download-de-dados"),
    "base_download": "https://dadosabertos-download.cgu.gov.br/FalaBR",
    "user_agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "pausa_entre_arquivos_s": 20,
    "tentativas": 3,
    "pausa_retentativa_s": 75,
    "encoding": "utf-16",
    "sep": ";",
    "limiar_padronizacao": 5,      # nº mínimo de ocorrências para considerar a abertura "padronizada"
    "limiar_caracteres_abertura": 250,
    "semente": 20261006,
    "anos_estruturado": list(range(2012, 2026)),
    "anos_texto": list(range(2015, 2026)),
}

DIRS = ["zips", "csv", "txt", "saida", "figuras", "serie_textual"]


def dirs() -> dict:
    d = {k: os.path.join(CONF["raiz"], k) for k in DIRS}
    d["raiz"] = CONF["raiz"]
    for v in d.values():
        os.makedirs(v, exist_ok=True)
    return d


def log(msg: str) -> None:
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def gravar_json(obj, caminho: str) -> None:
    with io.open(caminho, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=str)


# ============================== 1. COLETA ==============================

ARQUIVOS_ESTRUTURADOS = [
    ("Pedidos_%d.zip", "%s/FalaBR/Arquivos_csv_%d.zip"),
    ("Recursos_Reclamacoes_%d.zip", "%s/FalaBR/Recursos_Reclamacoes_csv_%d.zip"),
    ("SolicitantesPedidos_%d.zip", "%s/FalaBR/SolicitantesPedidos_csv_%d.zip"),
]
ARQUIVO_TEXTOS = ("textos_%d.zip", "%s/Arquivos_FalaBR_Filtrado/Arquivos_csv_%d.zip")


def _baixar(url: str, destino: str) -> bool:
    """Baixa validando assinatura ZIP. Repete com pausa: o WAF estrangula em rajada."""
    if os.path.exists(destino) and os.path.getsize(destino) > 1_000_000:
        with open(destino, "rb") as fh:
            if fh.read(2) == b"PK":
                log("já existe e é válido: %s" % os.path.basename(destino))
                return True
    for tentativa in range(1, CONF["tentativas"] + 1):
        subprocess.run([
            "curl", "-sS", "--max-time", "900", "-o", destino,
            "-A", CONF["user_agent"], "-H", "Referer: " + CONF["pagina_oficial"], url,
        ], check=False)
        if os.path.exists(destino):
            tam = os.path.getsize(destino)
            with open(destino, "rb") as fh:
                assinatura = fh.read(2)
            if tam > 1_000_000 and assinatura == b"PK":
                log("baixado: %s (%.1f MB)" % (os.path.basename(destino), tam / 1048576))
                return True
            log("tentativa %d falhou (%s, %d bytes, início %r) — pausa %ds" % (
                tentativa, os.path.basename(destino), tam, assinatura, CONF["pausa_retentativa_s"]))
        time.sleep(CONF["pausa_retentativa_s"])
    log("FALHOU definitivamente: %s" % url)
    return False


def etapa_coleta(anos_estruturado=None, anos_texto=None, apenas_verificar=False) -> dict:
    """Coleta automatizada: estruturados (2012–2025) e textos filtrados (2015–2025)."""
    d = dirs()
    anos_estruturado = anos_estruturado or CONF["anos_estruturado"]
    anos_texto = anos_texto or CONF["anos_texto"]
    resultado = {"estruturado": {}, "textos": {}}

    for ano in anos_estruturado:
        for padrao_local, padrao_url in ARQUIVOS_ESTRUTURADOS:
            url = padrao_url % (CONF["base_download"], ano)
            destino = os.path.join(d["zips"], padrao_local % ano)
            if apenas_verificar:
                r = subprocess.run(["curl", "-sS", "-I", "--max-time", "60", "-A", CONF["user_agent"],
                                    "-H", "Referer: " + CONF["pagina_oficial"], url],
                                   capture_output=True, text=True)
                resultado["estruturado"][destino] = "200" in r.stdout
            else:
                ok = _baixar(url, destino)
                resultado["estruturado"][destino] = ok
            time.sleep(2)

    for ano in anos_texto:
        url = ARQUIVO_TEXTOS[1] % (CONF["base_download"], ano)
        destino = os.path.join(d["zips"], ARQUIVO_TEXTOS[0] % ano)
        if apenas_verificar:
            r = subprocess.run(["curl", "-sS", "-I", "--max-time", "60", "-A", CONF["user_agent"],
                                "-H", "Referer: " + CONF["pagina_oficial"], url],
                               capture_output=True, text=True)
            resultado["textos"][destino] = "200" in r.stdout
        else:
            resultado["textos"][destino] = _baixar(url, destino)
            time.sleep(CONF["pausa_entre_arquivos_s"])

    gravar_json(resultado, os.path.join(d["saida"], "coleta.json"))
    log("coleta: %d estruturados, %d textos" % (len(resultado["estruturado"]), len(resultado["textos"])))
    return resultado


# ============================== 2. PREPARAÇÃO ==============================

def _extrair(zip_path: str, destino_dir: str, contem: str = "") -> list:
    """Extrai do zip os CSVs cujo nome contém `contem`. Devolve os caminhos extraídos."""
    extraidos = []
    if not os.path.exists(zip_path):
        return extraidos
    with zipfile.ZipFile(zip_path) as z:
        for nome in z.namelist():
            if nome.lower().endswith(".csv") and (contem.lower() in nome.lower() if contem else True):
                alvo = os.path.join(destino_dir, os.path.basename(nome))
                if not os.path.exists(alvo) or os.path.getsize(alvo) < 100_000:
                    z.extract(nome, destino_dir)
                extraidos.append(alvo)
    return extraidos


def cabecalho(caminho: str) -> list:
    """Lê o cabeçalho REAL do arquivo (nunca a lista publicada na página oficial)."""
    return list(pd.read_csv(caminho, sep=CONF["sep"], encoding=CONF["encoding"],
                            dtype=str, nrows=0).columns)


def resolver(colunas: list, candidatos: list) -> str | None:
    """Resolve o nome real de uma coluna a partir de candidatos (sem acento, minúsculo)."""
    def normal(s):
        return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                       if unicodedata.category(c) != "Mn")
    nc = {normal(c): c for c in colunas}
    for cand in candidatos:
        if normal(cand) in nc:
            return nc[normal(cand)]
    for cand in candidatos:
        for k, v in nc.items():
            if normal(cand) in k:
                return v
    return None


def etapa_preparacao(anos_estruturado=None, anos_texto=None) -> dict:
    """Extrai zips e inventaria colunas reais de cada arquivo."""
    d = dirs()
    anos_estruturado = anos_estruturado or CONF["anos_estruturado"]
    anos_texto = anos_texto or CONF["anos_texto"]
    inv = {"estruturado": {}, "textos": {}}

    for ano in anos_estruturado:
        for padrao_local, _ in ARQUIVOS_ESTRUTURADOS:
            zip_path = os.path.join(d["zips"], padrao_local % ano)
            for caminho in _extrair(zip_path, d["csv"]):
                try:
                    inv["estruturado"][os.path.basename(caminho)] = {
                        "ano": ano, "bytes": os.path.getsize(caminho), "colunas": cabecalho(caminho)}
                except Exception as e:
                    inv["estruturado"][os.path.basename(caminho)] = {"erro": str(e)[:200]}

    for ano in anos_texto:
        zip_path = os.path.join(d["zips"], ARQUIVO_TEXTOS[0] % ano)
        for caminho in _extrair(zip_path, d["txt"]):
            try:
                inv["textos"][os.path.basename(caminho)] = {
                    "ano": ano, "bytes": os.path.getsize(caminho), "colunas": cabecalho(caminho)}
            except Exception as e:
                inv["textos"][os.path.basename(caminho)] = {"erro": str(e)[:200]}

    gravar_json(inv, os.path.join(d["saida"], "inventario_colunas.json"))
    log("preparação: %d arquivos estruturados, %d de texto" % (len(inv["estruturado"]), len(inv["textos"])))
    return inv


# ============================== 3. CLASSIFICAÇÃO DE ÓRGÃOS ==============================
# Regra DECLARADA e auditável. A ordem importa: o primeiro padrão que casa define o grupo.
# Cada grupo tem uma justificativa normativa/institucional explícita.

GRUPOS = [
    # (grupo, regex, observação)
    ("Controle interno", r"controladoria|^cgu\b|cgu\s*-|corregedoria|ouvidoria-geral da uniao",
     "órgãos de controle interno e correição"),
    ("Controle externo (tribunais de contas)", r"tribunal de contas|tce\b|tcm\b",
     "cortes de contas — no acervo aparecem apenas estaduais/municipais"),
    ("Ministério Público", r"ministerio publico|procuradoria-geral de justica|\bmpf\b|\bmpt\b|\bmprj\b|\bmpsp\b",
     "guardião clássico — verificar ausência"),
    ("Defensoria", r"defensoria", "função essencial à justiça"),
    ("Judiciário", r"\bstf\b|supremo tribunal|tribunal de justica|\btj[/ -]|\btrf\b|justica federal|"
                   r"justica do trabalho|\btrt\b|\btst\b|\btse\b|\bstj\b|\bstm\b|tribunal superior|"
                   r"tribunal regional eleitoral|\btre\b", "Poder Judiciário"),
    ("Legislativo", r"camara dos deputados|senado federal|congresso nacional|assembleia legislativa|"
                    r"camara municipal|camara legislativa|senado", "Poder Legislativo"),
    ("Universidades e institutos federais", r"universidade|instituto federal|colegio pedro ii|"
                                            r"escola tecnica|cefet", "educação federal"),
    ("Estatais, bancos e empresas públicas",
     r"banco do brasil|caixa economica|petrobras|correios|bndes|embrapa|dataprev|serpro|conab|"
     r"hemobras|finep|eletronuclear|infraero|infra s\.a|codevasf|embratur|"
     r"casa da moeda|cmb\b|cprm|companhia de pesquisa|cbtu|trensurb|amazul|imnel|imbel|"
     r"ebc\b|empresa brasil de comunicacao|telebras|pssa|pre-sal|cdp\b|cdrj|nuclep|"
     r"\bs\.?a\.?\b|companhia|empresa publica|sociedade de economia mista|ebserh|"
     r"hospital das clinicas|\bep[e]?\b|servico social autonomo",
     "estatais e empresas públicas"),
    ("Autarquias, fundações e agências",
     r"autarquia|fundacao|agencia nacional|instituto nacional|"
     r"consulado|superintendencia|delegacia", "administração indireta federal"),
    ("Executivo federal (ministérios e Presidência)",
     r"^ministerio|ministerio d|presidencia da republica|casa civil|advocacia-geral|"
     r"secretaria-geral|gabinete de seguranca", "administração direta federal"),
    ("Conselhos profissionais", r"conselho (regional|federal) de|conselho de fiscalizacao",
     "autarquias corporativas"),
    ("Esfera estadual", r"^estado d|governo do estado|secretaria de estado|"
                        r"procuradoria-geral do estado|polícia militar|policia militar",
     "administração estadual"),
    ("Esfera municipal", r"^municipio|prefeitura|^camara municipal de", "administração municipal"),
]

# Ordem de avaliação: declaração explícita (primeiro casamento define o grupo)
ORDEM = ["Ministério Público", "Defensoria", "Judiciário", "Legislativo",
         "Controle externo (tribunais de contas)", "Controle interno",
         "Conselhos profissionais", "Estatais, bancos e empresas públicas",
         "Universidades e institutos federais", "Autarquias, fundações e agências",
         "Executivo federal (ministérios e Presidência)",
         "Esfera estadual", "Esfera municipal"]

SEPARADOR = r"[-–—/|,;()]+"


def classificar_orgao(nome: str, esfera: str = "") -> str:
    """Classifica um órgão pela regra declarada; a esfera serve de desempate."""
    if not isinstance(nome, str) or not nome.strip():
        return "não classificado"
    def norm(s):
        return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                       if unicodedata.category(c) != "Mn")
    t = norm(nome)
    regras = {g: rx for g, rx, _ in GRUPOS}
    # 1) três exceções nominais que a ordem genérica erraria
    if "agencia brasileira de apoio" in t or "agsus" in t:
        return "Autarquias, fundações e agências"
    if "ebserh" in t or "hospital das clinicas" in t and "universidade" in t:
        return "Estatais, bancos e empresas públicas"
    if re.search(r"(^|\W)ministerio(\W|$)", t):
        return "Executivo federal (ministérios e Presidência)"
    for grupo in ORDEM:
        if re.search(regras[grupo], t):
            return grupo
    # 2) desempate pela esfera declarada no arquivo
    e = norm(esfera or "")
    if "municipal" in e:
        return "Esfera municipal"
    if "estadual" in e or "distrital" in e:
        return "Esfera estadual"
    if "federal" in e:
        return "Autarquias, fundações e agências"   # default federal conservador
    return "não classificado"


# ============================== 4. ANÁLISE ESTRUTURADA ==============================

def _ler(caminho: str, usecols=None, chunksize=250_000):
    return pd.read_csv(caminho, sep=CONF["sep"], encoding=CONF["encoding"], dtype=str,
                       usecols=usecols, chunksize=chunksize, low_memory=False)


def _para_dias(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie.astype(str).str.strip().str.replace(",", ".", regex=False),
                         errors="coerce")


def arquivo_estruturado(ano: int, tipo: str = "Pedidos") -> str | None:
    """Escolhe o CSV certo DENTRO do zip do tipo pedido: o nome interno não começa por 'Pedidos',
    começa pela data — por isso a escolha é por pontuação no nome, nunca por posição na lista."""
    d = dirs()
    for padrao, _ in ARQUIVOS_ESTRUTURADOS:
        if tipo.lower() not in padrao.lower():
            continue
        achados = _extrair(os.path.join(d["zips"], padrao % ano), d["csv"])

        def pontuar(caminho):
            b = os.path.basename(caminho).lower()
            if tipo.lower() == "pedidos":
                if "solicitante" in b or "recurso" in b:
                    return -1
                return 2 if "pedido" in b else 0
            if tipo.lower() == "recursos":
                return 2 if ("recurso" in b or "reclamac" in b) else 0
            return 0

        candidatos = [a for a in achados if pontuar(a) > 0]
        if candidatos:
            return max(candidatos, key=pontuar)
    return None


def analisar_ano_estruturado(ano: int) -> dict:
    """Volume, prazos, decisões, prorrogação, negativa e grupos de órgão — para um ano."""
    caminho = arquivo_estruturado(ano, "Pedidos")
    if not caminho:
        return {"ano": ano, "erro": "arquivo de pedidos não encontrado"}
    cols = cabecalho(caminho)
    c_org = resolver(cols, ["OrgaoDestinatario", "Órgão Destinatário"])
    c_esf = resolver(cols, ["Esfera"])
    c_dec = resolver(cols, ["Decisao", "Decisão"])
    c_sit = resolver(cols, ["Situacao", "Situação"])
    c_prazo = resolver(cols, ["PrazoAtendimento", "Prazo Restricao Acesso", "PrazoRestricaoAcesso"])
    c_mot = resolver(cols, ["MotivoNegativaAcesso"])
    c_dpror = resolver(cols, ["DataProrrogacao"])
    c_reg = resolver(cols, ["DataRegistro"])
    c_rsp = resolver(cols, ["DataResposta"])
    c_prorrog = resolver(cols, ["FoiProrrogado"])
    usar = [c for c in [c_org, c_esf, c_dec, c_sit, c_prazo, c_mot, c_dpror] if c]
    if c_org:
        usar.append(c_org)
    usar = list(dict.fromkeys(usar))

    n = 0
    grupos = {}
    decisoes, motivos = {}, {}
    for ch in _ler(caminho, usecols=usar):
        n += len(ch)
        if c_dec:
            for k, v in ch[c_dec].fillna("(vazio)").value_counts().items():
                decisoes[k] = decisoes.get(k, 0) + int(v)
        if c_mot:
            m = ch[c_mot].fillna("").astype(str).str.strip()
            for k, v in m[m != ""].value_counts().items():
                motivos[k[:80]] = motivos.get(k[:80], 0) + int(v)
        if c_org:
            esf = ch[c_esf] if c_esf else pd.Series("", index=ch.index)
            chave = list(zip(ch[c_org].astype(str), esf.astype(str)))
            from collections import Counter
            for (org, e), qtd in Counter(chave).items():
                g = grupos.setdefault(classificar_orgao(org, e), {"pedidos": 0, "negado": 0, "concedido": 0,
                                                                  "parcial": 0, "prorrogado": 0})
                g["pedidos"] += qtd
                if c_dec:
                    pass  # decisões por grupo são contadas abaixo, em segunda passada
    # segunda passada: decisões, prorrogação e PRAZO por grupo (mesma linha: órgão, decisão, datas)
    marcas, dias_por_grupo, dias_global = {}, {}, []
    if c_org and c_dec:
        colunas2 = [c_org, c_dec] + [c for c in [c_dpror, c_reg, c_rsp, c_prorrog, c_esf] if c]
        for ch in _ler(caminho, usecols=list(dict.fromkeys(colunas2))):
            ch = ch.copy()
            # MESMA classificação da primeira passagem: (órgão, esfera) — sem isso os totais
            # e as decisões viriam de agrupamentos diferentes e os percentuais sairiam impossíveis.
            esf2 = ch[c_esf].astype(str) if c_esf else pd.Series("", index=ch.index)
            ch["_grupo"] = [classificar_orgao(o, e) for o, e in
                            zip(ch[c_org].astype(str), esf2)]
            if c_reg and c_rsp:
                d0 = pd.to_datetime(ch[c_reg], errors="coerce", dayfirst=True)
                d1 = pd.to_datetime(ch[c_rsp], errors="coerce", dayfirst=True)
                ch["_dias"] = (d1 - d0).dt.days
                validos = ch["_dias"].dropna()
                validos = validos[(validos >= 0) & (validos <= 3650)]
                dias_global.extend(validos.tolist())
            for g, sub in ch.groupby("_grupo"):
                m = marcas.setdefault(g, {"negado": 0, "concedido": 0, "parcial": 0, "prorrogado": 0})
                vc = sub[c_dec].fillna("(vazio)").value_counts()
                m["negado"] += int(vc.get("Acesso Negado", 0))
                m["concedido"] += int(vc.get("Acesso Concedido", 0))
                m["parcial"] += int(vc.get("Acesso Parcialmente Concedido", 0))
                if c_prorrog:
                    m["prorrogado"] += int(sub[c_prorrog].fillna("").astype(str).str.strip()
                                            .str.lower().isin(["sim", "true", "1"]).sum())
                elif c_dpror:
                    m["prorrogado"] += int(sub[c_dpror].fillna("").astype(str).str.strip().ne("").sum())
                if "_dias" in sub:
                    v = sub["_dias"].dropna()
                    v = v[(v >= 0) & (v <= 3650)]
                    dias_por_grupo.setdefault(g, []).extend(v.tolist())
    for g in grupos:
        if g in marcas:
            grupos[g].update(marcas[g])
    for g, v in dias_por_grupo.items():
        if not v:
            continue
        s = pd.Series(v)
        grupos[g].update({"dias_mediana": float(s.median()), "dias_p90": float(s.quantile(0.90)),
                          "pct_acima_20": round(100.0 * (s > 20).sum() / len(s), 1), "dias_n": len(s)})

    series_dias = pd.Series(dias_global) if dias_global else None
    ano_res = {"ano": ano, "arquivo": os.path.basename(caminho), "pedidos": n,
               "colunas_lidas": usar, "decisoes": dict(sorted(decisoes.items(), key=lambda x: -x[1])[:10]),
               "motivos_negativa": dict(sorted(motivos.items(), key=lambda x: -x[1])[:10]),
               "prazos": ({"n": int(len(dias_global)),
                           "mediana": float(series_dias.median()),
                           "p90": float(series_dias.quantile(0.90)),
                           "pct_acima_20": round(100.0 * (series_dias > 20).sum() / len(series_dias), 1)}
                          if series_dias is not None else None),
               "grupos": grupos}
    gravar_json(ano_res, os.path.join(dirs()["saida"], "estruturado_%d.json" % ano))
    log("%d: %d pedidos | %d grupos | decisões: %s" % (
        ano, n, len(grupos), list(ano_res["decisoes"].items())[:2]))
    return ano_res


def analisar_recursos(ano: int) -> dict:
    """Taxa de recurso: nº de recursos no ano / nº de pedidos do ano."""
    cam_rec = arquivo_estruturado(ano, "Recursos")
    if not cam_rec:
        return {"ano": ano, "erro": "arquivo de recursos não encontrado"}
    n = 0
    for ch in _ler(cam_rec, usecols=[cabecalho(cam_rec)[0]]):
        n += len(ch)
    return {"ano": ano, "recursos": n}


def etapa_estruturada(anos=None) -> dict:
    d = dirs()
    anos = anos or CONF["anos_estruturado"]
    anos = [a for a in anos if arquivo_estruturado(a, "Pedidos")]
    res = {}
    for ano in anos:
        res[ano] = analisar_ano_estruturado(ano)
        r = analisar_recursos(ano)
        if "recursos" in r:
            ped = res[ano].get("pedidos") or 0
            res[ano]["recursos"] = r["recursos"]
            res[ano]["taxa_recurso_pct"] = round(100.0 * r["recursos"] / ped, 1) if ped else None
    gravar_json(res, os.path.join(d["saida"], "estruturado_serie.json"))
    return res


# ============================== 5. ANÁLISE TEXTUAL ==============================

PUNC = re.compile(r"[^a-z0-9 ]+")


def normalizar_abertura(texto: str, limite: int | None = None) -> str:
    """Normalização SIMPLES (minúsculas, sem pontuação) — a medida central não usa lematização."""
    limite = limite if limite is not None else CONF["limiar_caracteres_abertura"]
    t = (texto or "")[:limite].lower()
    return re.sub(r"\s+", " ", PUNC.sub(" ", t)).strip()


def _hash(t: str) -> str:
    return hashlib.md5(t.encode("utf-8")).hexdigest()


def analisar_texto_ano(ano: int, limiar: int | None = None, amostra: int | None = None) -> dict:
    """Cobertura, extensão, padronização por abertura, quase-duplicatas e taxonomia-proxy."""
    d = dirs()
    limiar = limiar or CONF["limiar_padronizacao"]
    alvos = glob.glob(os.path.join(d["txt"], "*Pedidos_csv_%d.csv" % ano))
    if not alvos:
        z = os.path.join(d["zips"], ARQUIVO_TEXTOS[0] % ano)
        alvos = [a for a in _extrair(z, d["txt"], "Pedidos_csv") if str(ano) in a]
    if not alvos:
        return {"ano": ano, "erro": "pacote de texto não disponível"}
    caminho = alvos[0]
    cols = cabecalho(caminho)
    c_res = resolver(cols, ["ResumoSolicitacao"])
    c_det = resolver(cols, ["DetalhamentoSolicitacao"])
    c_rsp = resolver(cols, ["Resposta"])
    c_dec = resolver(cols, ["Decisao"])
    c_id = resolver(cols, ["IdPedido"])
    usar = [c for c in [c_id, c_res, c_det, c_rsp, c_dec] if c]

    # amostra: leitura em blocos com reservatório determinístico por ano
    rng = random.Random(CONF["semente"])
    tot = tem_res = tem_det = tem_rsp = 0
    soma_res, soma_rsp, tam_res = 0, 0, []
    cont_hash, cont_abert = {}, {}
    decisoes = {}
    inicial = None
    if amostra:
        fracao = float(amostra)
        for ch in _ler(caminho, usecols=usar, chunksize=50_000):
            ch = ch.sample(frac=min(1.0, fracao / max(tot + len(ch), 1) * 40), random_state=CONF["semente"])
            if inicial is None and len(ch):
                inicial = ch
            else:
                if len(ch):
                    inicial = pd.concat([inicial, ch]).head(amostra) if inicial is not None else ch
        dados = inicial if inicial is not None else pd.DataFrame(columns=usar)
    else:
        dados = pd.DataFrame(columns=usar)

    for ch in _ler(caminho, usecols=usar):
        tot += len(ch)
        if c_res:
            r = ch[c_res].fillna("").astype(str).str.strip()
            tem_res += int(r.ne("").sum()); soma_res += int(r.str.len().sum())
        if c_det:
            tem_det += int(ch[c_det].fillna("").astype(str).str.strip().ne("").sum())
        if c_rsp:
            p = ch[c_rsp].fillna("").astype(str).str.strip()
            nao_vazias = p[p.ne("")]
            tem_rsp += int(len(nao_vazias))
            soma_rsp += int(nao_vazias.str.len().sum())
            tam_res.extend(nao_vazias.str.len().head(5000).tolist())
            for t in nao_vazias:
                cont_hash[_hash(normalizar_abertura(t))] = cont_hash.get(_hash(normalizar_abertura(t)), 0) + 1
                cont_abert[normalizar_abertura(t)[:120]] = cont_abert.get(normalizar_abertura(t)[:120], 0) + 1
        if c_dec:
            for k, v in ch[c_dec].fillna("(vazio)").value_counts().items():
                decisoes[k] = decisoes.get(k, 0) + int(v)

    padronizadas = sum(v for v in cont_hash.values() if v >= limiar)
    duplicatas_exatas = sum(v for v in cont_hash.values() if v >= 2) - len([v for v in cont_hash.values() if v >= 2])
    maiores = sorted(cont_abert.items(), key=lambda x: -x[1])[:3]
    out = {
        "ano": ano, "pedidos": tot,
        "pct_resumo": round(100.0 * tem_res / tot, 1) if tot else None,
        "pct_detalhamento": round(100.0 * tem_det / tot, 1) if tot else None,
        "pct_resposta": round(100.0 * tem_rsp / tot, 1) if tot else None,
        "extensao_media_resumo": round(soma_res / max(tem_res, 1), 0),
        "extensao_media_resposta": round(soma_rsp / max(tem_rsp, 1), 0),
        "extensao_mediana_resposta": float(np.median(tam_res)) if tam_res else None,
        "aberturas_distintas": len(cont_hash),
        "pct_padronizada": round(100.0 * padronizadas / max(tem_rsp, 1), 1),
        "limiar": limiar,
        "quase_duplicatas_respostas": duplicatas_exatas,
        "maiores_aberturas": [{"n": int(v), "inicio": k[:90]} for k, v in maiores],
        "decisoes": dict(sorted(decisoes.items(), key=lambda x: -x[1])[:8]),
    }
    gravar_json(out, os.path.join(d["serie_textual"], "texto_%d.json" % ano))
    log("%d: %d pedidos | resposta %.0f car. | %.1f%% padronizada (limiar %d)" % (
        ano, tot, out["extensao_media_resposta"] or 0, out["pct_padronizada"], limiar))
    return out


def comparar_subconjunto(ano: int) -> dict:
    """Prova que o pacote de textos é subconjunto estrito e mede o viés de composição."""
    d = dirs()
    estr = arquivo_estruturado(ano, "Pedidos")
    txts = glob.glob(os.path.join(d["txt"], "*Pedidos_csv_%d.csv" % ano))
    if not estr or not txts:
        return {"ano": ano, "erro": "arquivos ausentes"}
    ce, ct = cabecalho(estr), cabecalho(txts[0])
    ide = resolver(ce, ["IdPedido"]); idt = resolver(ct, ["IdPedido"])
    dece = resolver(ce, ["Decisao"]); dect = resolver(ct, ["Decisao"])
    se, st, de, dt = set(), set(), {}, {}
    for ch in _ler(estr, usecols=[x for x in [ide, dece] if x]):
        se.update(ch[ide].dropna().astype(str))
        for k, v in ch[dece].fillna("(vazio)").value_counts().items():
            de[k] = de.get(k, 0) + int(v)
    for ch in _ler(txts[0], usecols=[x for x in [idt, dect] if x]):
        st.update(ch[idt].dropna().astype(str))
        for k, v in ch[dect].fillna("(vazio)").value_counts().items():
            dt[k] = dt.get(k, 0) + int(v)
    def pct(dic, chave):
        base = sum(dic.values()) or 1
        return round(100.0 * dic.get(chave, 0) / base, 1)
    return {"ano": ano, "estruturado": len(se), "textos": len(st), "em_comum": len(se & st),
            "cobertura_pct": round(100.0 * len(st) / max(len(se), 1), 1),
            "subconjunto_estrito": len(st - se) == 0,
            "negado_base_pct": pct(de, "Acesso Negado"), "negado_subconjunto_pct": pct(dt, "Acesso Negado"),
            "concedido_base_pct": pct(de, "Acesso Concedido"), "concedido_subconjunto_pct": pct(dt, "Acesso Concedido")}


def contraste_agrupamento(ano: int, limiar: int | None = None) -> dict:
    """Contraste de robustez: TF-IDF + KMeans contra decisão formal e taxonomia léxica."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        from sklearn.metrics import adjusted_rand_score
    except Exception as e:
        return {"ano": ano, "erro": "scikit-learn ausente: %s" % e}
    d = dirs()
    alvos = glob.glob(os.path.join(d["txt"], "*Pedidos_csv_%d.csv" % ano))
    if not alvos:
        return {"ano": ano, "erro": "pacote não disponível"}
    caminho = alvos[0]
    cols = cabecalho(caminho)
    c_rsp = resolver(cols, ["Resposta"]); c_dec = resolver(cols, ["Decisao"])
    pedacos, rotulos = [], []
    lidos = 0
    for ch in _ler(caminho, usecols=[x for x in [c_rsp, c_dec] if x], chunksize=20_000):
        if lidos >= 12_000:
            break
        ch = ch[ch[c_rsp].fillna("").astype(str).str.strip().ne("")]
        pedacos.append(ch[[c_rsp, c_dec]]); lidos += len(ch)
    D = pd.concat(pedacos).sample(min(12_000, lidos), random_state=CONF["semente"])
    textos = D[c_rsp].astype(str).map(normalizar_abertura).tolist()
    X = TfidfVectorizer(min_df=5, max_features=20_000, ngram_range=(1, 2)).fit_transform(textos)
    km = KMeans(n_clusters=5, random_state=CONF["semente"], n_init=10).fit(X)
    from collections import Counter
    dist = Counter(km.labels_)
    return {"ano": ano, "n": len(textos),
            "ari_contra_decisao": round(adjusted_rand_score(D[c_dec].fillna("(vazio)"), km.labels_), 3),
            "tamanho_maior_cluster": max(dist.values()),
            "observacao": "contraste de robustez; NÃO é instrumento de medida"}


def etapa_textual(anos=None, limiar=None) -> dict:
    d = dirs()
    anos = anos or [a for a in CONF["anos_texto"]
                    if glob.glob(os.path.join(d["txt"], "*Pedidos_csv_%d.csv" % a)) or
                    os.path.exists(os.path.join(d["zips"], ARQUIVO_TEXTOS[0] % a))]
    res = {}
    for ano in anos:
        res[ano] = analisar_texto_ano(ano, limiar=limiar)
    try:
        tabela = pd.DataFrame(list(res.values()))
        tabela.to_csv(os.path.join(d["serie_textual"], "serie_textual.csv"), index=False)
    except Exception:
        pass
    gravar_json(res, os.path.join(d["saida"], "textual_serie.json"))
    return res


# ============================== 6. RELATÓRIO DISCORRIDO ==============================

def etapa_relatorio() -> str:
    """Gera o relatório em markdown com as análises discorridas a partir dos números medidos."""
    d = dirs()
    saida = os.path.join(d["saida"], "ANALISES-DISCORRIDAS.md")
    L = ["# LAI 15 anos — análises discorridas",
         "",
         "*Relatório gerado automaticamente pelo pipeline a partir das medições. Todos os números "
         "abaixo vêm dos arquivos de `saida/`, `serie_textual/` e `zips/`; nenhum é estimado.*",
         "", "Gerado em: " + datetime.now().strftime("%d/%m/%Y %H:%M"), ""]

    # --- estruturado
    f_est = os.path.join(d["saida"], "estruturado_serie.json")
    if os.path.exists(f_est):
        est = json.load(open(f_est, encoding="utf-8"))
        L += ["## 1. Base estruturada", ""]
        tot_ped = sum(v.get("pedidos") or 0 for v in est.values())
        tot_rec = sum(v.get("recursos") or 0 for v in est.values())
        anos = sorted(est.keys())
        L += ["A base reúne **%s pedidos** e **%s recursos/reclamações** entre %s e %s. "
              % ("{:,}".format(tot_ped).replace(",", "."), "{:,}".format(tot_rec).replace(",", "."),
                 anos[0], anos[-1]), ""]
        L += ["| Ano | Pedidos | Recursos | Taxa de recurso (%) |", "|---|---|---|---|"]
        for a in anos:
            v = est[a]
            L.append("| %s | %s | %s | %s |" % (
                a, "{:,}".format(v.get("pedidos") or 0).replace(",", "."),
                "{:,}".format(v.get("recursos") or 0).replace(",", "."),
                v.get("taxa_recurso_pct")))
        L.append("")
        ult = est[anos[-1]]
        if ult.get("grupos"):
            L += ["### 1.1 Grupos de órgãos (%s)" % anos[-1], "",
                  "| Grupo | Pedidos | Negado (%) | Concedido (%) | Parcial (%) |", "|---|---|---|---|---|"]
            for g, v in sorted(ult["grupos"].items(), key=lambda x: -x[1]["pedidos"]):
                n = v["pedidos"] or 1
                L.append("| %s | %s | %.1f | %.1f | %.1f |" % (
                    g, "{:,}".format(v["pedidos"]).replace(",", "."),
                    100.0 * v.get("negado", 0) / n, 100.0 * v.get("concedido", 0) / n,
                    100.0 * v.get("parcial", 0) / n))
            L.append("")
        if ult.get("motivos_negativa"):
            L += ["### 1.2 Motivos de negativa registrados (%s)" % anos[-1], ""]
            for k, v in list(ult["motivos_negativa"].items())[:8]:
                L.append("- %s: %s" % (k, "{:,}".format(v).replace(",", ".")))
            L.append("")

    # --- textual
    f_txt = os.path.join(d["saida"], "textual_serie.json")
    if os.path.exists(f_txt):
        txt = json.load(open(f_txt, encoding="utf-8"))
        L += ["## 2. Base textual", ""]
        L += ["| Ano | Pedidos com texto | Resposta preenchida (%) | Extensão média da resposta | Padronizadas (%) |",
              "|---|---|---|---|---|"]
        for a in sorted(txt.keys()):
            v = txt[a]
            if "erro" in v:
                L.append("| %s | — | — | — | (%s) |" % (a, v["erro"]))
                continue
            L.append("| %s | %s | %s | %s | %s |" % (
                a, "{:,}".format(v["pedidos"]).replace(",", "."), v.get("pct_resposta"),
                v.get("extensao_media_resposta"), v.get("pct_padronizada")))
        L.append("")

    L += ["## 3. Declaração de limites do próprio relatório", "",
          "1. O pacote de textos é subconjunto publicado da base estruturada; a cobertura é medida, não suposta.",
          "2. O esquema de colunas é lido do arquivo, porque a página oficial está desatualizada.",
          "3. As medidas de padronização dependem do limiar de repetição declarado e do tamanho do conjunto medido.",
          "4. A taxonomia léxica é proxy; a versão anotada, com kappa, é etapa separada.",
          ""]
    with io.open(saida, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    log("relatório gravado: %s" % saida)
    return saida


# ============================== 7. VERIFICAÇÃO CONTRA AS MEDIÇÕES GRAVADAS ==============================

ESPERADO_2025 = {   # medições de referência (a classificação declarada deve reproduzi-las)
    "Executivo federal (ministérios e Presidência)": 45296,
    "Autarquias, fundações e agências": 43339,
    "Universidades e institutos federais": 20703,
    "Estatais, bancos e empresas públicas": 19262,
    "Esfera municipal": 10246,
    "Esfera estadual": 7134,
    "Controle interno": 1852,
    "Conselhos profissionais": 759,
    "Controle externo (tribunais de contas)": 500,
    "Judiciário": 378,
    "Legislativo": 173,
    "Defensoria": 34,
}


def etapa_verificacao() -> dict:
    """Compara a classificação produzida com as medições de referência (2025)."""
    d = dirs()
    f = os.path.join(d["saida"], "estruturado_2025.json")
    if not os.path.exists(f):
        analisar_ano_estruturado(2025)
    est = json.load(open(f, encoding="utf-8"))
    linhas, divergentes = [], 0
    for g, esperado in ESPERADO_2025.items():
        obtido = est["grupos"].get(g, {}).get("pedidos", 0)
        bate = obtido == esperado
        if not bate:
            divergentes += 1
        linhas.append({"grupo": g, "esperado": esperado, "obtido": obtido,
                       "diferenca": obtido - esperado, "bate": bate})
    resultado = {"divergentes": divergentes, "linhas": linhas,
                 "total_esperado": sum(ESPERADO_2025.values()),
                 "total_obtido": sum(l["obtido"] for l in linhas)}
    gravar_json(resultado, os.path.join(d["saida"], "verificacao.json"))
    log("verificação: %d de %d grupos divergem do esperado" % (divergentes, len(ESPERADO_2025)))
    for l in linhas:
        if not l["bate"]:
            log("  %-45s esperado %7d | obtido %7d (%+d)" % (l["grupo"], l["esperado"], l["obtido"], l["diferenca"]))
    return resultado


# ============================== CLI ==============================

def interpretar_intervalo(s: str, padrao: list) -> list:
    if not s:
        return padrao
    if "-" in s:
        a, b = s.split("-")[:2]
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in re.split(r"[,\s]+", s) if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description="Pipeline LAI 15 anos (Fala.BR/CGU)")
    ap.add_argument("--etapa", default="tudo",
                    choices=["diagnostico", "coleta", "preparacao", "estruturada", "textual",
                             "relatorio", "verificacao", "tudo"])
    ap.add_argument("--anos", default="", help="ex.: 2012-2025 ou 2025")
    ap.add_argument("--textos", default="", help="ex.: 2015-2025")
    ap.add_argument("--ano", type=int, default=None, help="ano único para as etapas de análise")
    ap.add_argument("--limiar", type=int, default=None, help="limiar de padronização (padrão 5)")
    ap.add_argument("--apenas-verificar", action="store_true", help="na coleta, só testa disponibilidade")
    args = ap.parse_args()

    d = dirs()
    log("raiz de trabalho: %s" % CONF["raiz"])

    if args.etapa in ("diagnostico", "tudo"):
        inv = etapa_preparacao()
        log("coloquei o inventário de colunas em %s" % os.path.join(d["saida"], "inventario_colunas.json"))

    if args.etapa in ("coleta", "tudo"):
        etapa_coleta(interpretar_intervalo(args.anos, CONF["anos_estruturado"]),
                     interpretar_intervalo(args.textos, CONF["anos_texto"]),
                     apenas_verificar=args.apenas_verificar)

    if args.etapa in ("preparacao", "tudo"):
        etapa_preparacao(interpretar_intervalo(args.anos, CONF["anos_estruturado"]),
                         interpretar_intervalo(args.textos, CONF["anos_texto"]))

    if args.etapa in ("estruturada", "tudo"):
        etapa_estruturada([args.ano] if args.ano else interpretar_intervalo(args.anos, None))

    if args.etapa in ("textual", "tudo"):
        etapa_textual([args.ano] if args.ano else None, limiar=args.limiar)

    if args.etapa == "verificacao":
        etapa_verificacao()

    if args.etapa in ("relatorio", "tudo"):
        print(etapa_relatorio())


if __name__ == "__main__":
    main()

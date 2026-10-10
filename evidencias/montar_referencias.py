#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta a base de referências dos dois artigos novos a partir de buscas no Crossref.

Método: cada referência nasce de uma CONSULTA REAL à API do Crossref; o registro devolvido
(título, autores, ano, veículo, DOI) é o que entra na base. Nada é escrito de memória.

Uso:  python3 montar_referencias.py
Saída:  evidencias/referencias-artigoA_v1.csv e referencias-artigoB_v1.csv
"""
import csv, json, os, time, urllib.parse, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(os.path.dirname(AQUI), "evidencias", "referencias")
os.makedirs(SAIDA, exist_ok=True)
API = "https://api.crossref.org/works"
UA = "lai-replicacao/1.1 (mailto:douglasferreirapinto@gmail.com)"

# eixos de busca — cada consulta devolve os 6 primeiros registros por relevância
CONSULTAS_A = {
    "onus_administrativo": "administrative burden citizens state",
    "acesso_informacao": "freedom of information act transparency compliance",
    "recurso_administrativo": "administrative appeal review citizens decision",
    "controle_externo": "supreme audit institution oversight accountability",
    "silêncio_administrativo": "administrative silence non-response public administration",
    "ouvidoria": "ombudsman complaint handling public administration",
    "contestação_cidadão": "citizen complaints public services response",
    "transparência_negativa": "information refusal denial freedom of information",
    "justiça_administrativa": "administrative justice redress bureaucratic decision",
    "dados_abertos_governo": "open government data transparency accountability",
}

CONSULTAS_B = {
    "concordancia": "intercoder agreement content analysis reliability",
    "kappa": "Cohen kappa agreement coefficient reliability",
    "fleiss": "Fleiss kappa multiple raters agreement",
    "gwet": "Gwet AC1 agreement coefficient prevalence",
    "amostragem_estratificada": "stratified sampling design survey public administration",
    "anotacao_manual": "manual annotation human coding text classification reliability",
    "resposta_evasiva": "nonresponse evasion administrative reply quality",
    "quase_duplicata": "near duplicate detection text similarity MinHash",
}


def consulta(termo, linhas=6):
    url = "%s?query.bibliographic=%s&rows=%d&select=DOI,title,author,issued,container-title,type,is-referenced-by-count" % (
        API, urllib.parse.quote(termo), linhas)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)["message"]["items"]


def registro(it, eixo):
    titulo = (it.get("title") or [""])[0]
    autores = it.get("author") or []
    nomes = "; ".join(("%s, %s" % (a.get("family", ""), a.get("given", ""))).strip(", ") for a in autores[:4])
    ano = None
    for k in ("issued", "published-print", "published-online"):
        if it.get(k, {}).get("date-parts"):
            ano = it[k]["date-parts"][0][0]
            break
    return {"eixo": eixo, "autores": nomes, "titulo": titulo, "ano": ano or "",
            "veiculo": (it.get("container-title") or [""])[0] or it.get("type", ""),
            "doi": it.get("DOI", ""), "citacoes_crossref": it.get("is-referenced-by-count", 0)}


def roda(consultas, arquivo):
    linhas = []
    for eixo, termo in consultas.items():
        try:
            for it in consulta(termo):
                linhas.append(registro(it, eixo))
        except Exception as e:
            print("  falha em %s: %s" % (eixo, e))
        time.sleep(0.4)
    with open(os.path.join(SAIDA, arquivo), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
    print("\n== %s: %d registros" % (arquivo, len(linhas)))
    for eixo in consultas:
        cand = [l for l in linhas if l["eixo"] == eixo]
        cand.sort(key=lambda x: -int(x["citacoes_crossref"] or 0))
        print("\n[%s]" % eixo)
        for l in cand[:3]:
            print("   %-64s %s | %s | DOI %s | %s citações" % (
                (l["titulo"][:64] or "(sem título)"), l["ano"], (l["veiculo"][:26] or "?"),
                l["doi"], l["citacoes_crossref"]))
    return linhas


if __name__ == "__main__":
    print("=== ARTIGO A — contestação, ônus e controle ===")
    roda(CONSULTAS_A, "referencias-artigoA_v1.csv")
    print("\n\n=== ARTIGO B — anotação, concordância e amostra ===")
    roda(CONSULTAS_B, "referencias-artigoB_v1.csv")

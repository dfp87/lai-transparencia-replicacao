#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta as tabelas dos artigos 4 (contestação) e 5 (anotação) a partir das evidências.

Nenhum número dos artigos é digitado à mão: as tabelas saem das saídas medidas em
`saidas-recursos/` e `saidas-minhash/`. Se uma evidência faltar, o script DIZ isso no
lugar da tabela, em vez de deixar a lacuna silenciosa.

Uso:  python3 montar_artigos_4e5.py
"""
import csv, json, glob, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(AQUI, "saidas-recursos")
BASE = "/workspace/cerebro/05-pesquisa/rap-lai-15anos"
A = os.path.join(BASE, "2026-10-10_artigo-proposta4_contestacao-do-cidadao_v1.md")
B = os.path.join(BASE, "2026-10-10_artigo-proposta5_medir-a-evasao_v1.md")


def ler(nome):
    p = os.path.join(REC, nome)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(v, dec=1):
    try:
        return ("%.*f" % (dec, float(v))).replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


def tab(linhas, cab, campos, alinhados=()):
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    for r in linhas:
        cel = []
        for i, c in enumerate(campos):
            v = r.get(c, "")
            cel.append(num(v, 1) if (i in alinhados and v != "") else str(v))
        out.append("| " + " | ".join(cel) + " |")
    return "\n".join(out)


# ------------------------------------------------------------------ ARTIGO A
pa = ler("por-ano.csv")
if pa:
    t_serie = tab(pa, ["Ano", "Recursos", "Provido ou parcial (%)", "Não conhecido (%)", "Sem resposta (%)"],
                  ["ano", "recursos", "provido_ou_parcial_pct", "nao_conhecido_pct", "sem_resposta_pct"], (2, 3, 4))
else:
    t_serie = "_Evidência `por-ano.csv` ausente._"

mo = ler("motivo-x-desfecho.csv")
if mo:
    rot = [k for k in mo[0] if k not in ("recursos", "provido_ou_parcial_pct", "nao_conhecido_pct", "sem_resposta_pct")][0]
    mo = sorted(mo, key=lambda r: -int(r["recursos"]))
    t_motivo = tab(mo, ["Motivo declarado pelo órgão", "Recursos", "Provido ou parcial (%)", "Não conhecido (%)"],
                   [rot, "recursos", "provido_ou_parcial_pct", "nao_conhecido_pct"], (2, 3))
else:
    t_motivo = "_Evidência `motivo-x-desfecho.csv` ausente._"

pi = ler("instancia-x-desfecho.csv")
if pi:
    rot = [k for k in pi[0] if k not in ("recursos", "provido_ou_parcial_pct", "nao_conhecido_pct", "sem_resposta_pct")][0]
    pi = sorted(pi, key=lambda r: -int(r["recursos"]))[:8]
    t_inst = tab(pi, ["Instância", "Recursos", "Provido ou parcial (%)", "Não conhecido (%)", "Sem resposta (%)"],
                 [rot, "recursos", "provido_ou_parcial_pct", "nao_conhecido_pct", "sem_resposta_pct"], (2, 3, 4))
else:
    t_inst = "_Evidência `instancia-x-desfecho.csv` ausente._"

gu = ler("guardioes.csv")
t_guard = ("_Evidência `guardioes.csv` ausente._" if not gu else
           tab(gu, ["Grupo de órgão", "Recursos recebidos"],
               [list(gu[0].keys())[0], ["recursos", "recursos_recebidos", "n"][0] if "recursos" not in gu[0] else "recursos"]))

# ------------------------------------------------------------------ ARTIGO B
por_ano, tot_n, tot_p, tot_g, maior = [], 0, 0, 0, 0
for f in sorted(glob.glob(os.path.join(AQUI, "saidas-minhash", "minhash_inteira_20*.json"))):
    if "_amostra" in f:
        continue
    d = json.load(open(f, encoding="utf-8"))
    n, p = d["respostas_com_texto"], d["minhash"]["n"]
    tot_n += n; tot_p += p; tot_g += d["minhash"]["grupos_ge_5"]
    maior = max(maior, d["minhash"]["maior_grupo"])
    por_ano.append({"ano": d["ano"], "respostas_com_texto": n, "padronizadas": p,
                    "pct": 100.0 * p / n, "grupos": d["minhash"]["grupos_ge_5"],
                    "tam": (p / d["minhash"]["grupos_ge_5"]) if d["minhash"]["grupos_ge_5"] else 0})
if por_ano:
    N = 630
    aloc = {r["ano"]: int(N * r["respostas_com_texto"] / tot_n) for r in por_ano}
    resto = N - sum(aloc.values())
    for r in sorted(por_ano, key=lambda x: -(N * x["respostas_com_texto"] / tot_n - int(N * x["respostas_com_texto"] / tot_n)))[:resto]:
        aloc[r["ano"]] += 1
    for r in por_ano:
        r["alocacao"] = aloc[r["ano"]]
    t_amostra = tab(por_ano, ["Ano", "Respostas com texto", "Padronizadas", "% padronizadas", "Grupos", "Tamanho médio", "Amostra (630)"],
                    ["ano", "respostas_com_texto", "padronizadas", "pct", "grupos", "tam", "alocacao"], (3, 5))
    resumoB = (tot_n, tot_p, 100.0 * tot_p / tot_n, tot_g, tot_p / tot_g, maior)
else:
    t_amostra, resumoB = "_Evidência de MinHash ausente._", (0, 0, 0, 0, 0, 0)

prec = ler("precisao-kappa.csv") or ler("../saidas-recursos/precisao-kappa.csv")
t_prec = ("_Evidência `precisao-kappa.csv` ausente._" if not prec else tab(
    [r for r in prec if abs(float(r["prevalencia_evasao"]) - 0.35) < 1e-9 and abs(float(r["kappa_esperado"]) - 0.70) < 1e-9],
    ["n anotado", "Erro-padrão do κ", "Intervalo de 95% (±)"],
    ["n", "dp_kappa", "_ic"], (1,)) if False else tab(
    [dict(r, _ic=round(1.96 * float(r["dp_kappa"]), 3)) for r in prec
     if abs(float(r["prevalencia_evasao"]) - 0.35) < 1e-9 and abs(float(r["kappa_esperado"]) - 0.70) < 1e-9],
    ["n anotado", "Erro-padrão do κ", "Intervalo de 95% (±)"], ["n", "dp_kappa", "_ic"], (1, 2)))

subs_A = {"{{TABELA-SERIE}}": t_serie, "{{TABELA-MOTIVO}}": t_motivo,
          "{{TABELA-INSTANCIA}}": t_inst, "{{TABELA-GUARDIOES}}": t_guard}
subs_B = {"{{TABELA-AMOSTRA}}": t_amostra, "{{TABELA-PRECISAO}}": t_prec,
          "{{TOTAL-RESPOSTAS}}": "938.987" if tot_n == 938987 else str(tot_n),
          "{{TOTAL-PADRONIZADAS}}": ("%d (%.2f%%)" % (tot_p, 100.0 * tot_p / tot_n)).replace(".", ","),
          "{{TOTAL-GRUPOS}}": str(tot_g), "{{TAM-MEDIO}}": num(tot_p / tot_g, 1), "{{MAIOR-GRUPO}}": str(maior)}

for caminho, subs in ((A, subs_A), (B, subs_B)):
    if not os.path.exists(caminho):
        print("ARTIGO AUSENTE:", caminho); continue
    s = open(caminho, encoding="utf-8").read()
    faltando = [k for k in subs if k not in s]
    for k, v in subs.items():
        s = s.replace(k, v)
    open(caminho, "w", encoding="utf-8").write(s)
    restou = s.count("{{")
    print("%s: %d tabelas inseridas | marcadores restantes: %d | não usados: %s" % (
        os.path.basename(caminho), len(subs) - len(faltando), restou, faltando or "nenhum"))

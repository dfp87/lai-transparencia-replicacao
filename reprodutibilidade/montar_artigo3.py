#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta as tabelas do artigo 3 a partir dos CSVs consolidados e as insere no manuscrito.

Uso:
    python3 montar_artigo3.py                      # gera a versão com as tabelas
    python3 montar_artigo3.py --origem <arquivo.md> --destino <saida.md>
"""
import argparse, csv, json, os

AQUI = os.path.dirname(os.path.abspath(__file__))
AN = os.path.join(AQUI, "saidas-analise")
BASE = "/workspace/cerebro/05-pesquisa/rap-lai-15anos"


def ler_csv(nome):
    with open(os.path.join(AN, nome), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fmt(v, dec=2, sufixo=""):
    if v in (None, "", "None"):
        return "—"
    try:
        f = float(v)
    except ValueError:
        return str(v)
    return ("%.*f" % (dec, f)).replace(".", ",") + sufixo


def tabela_a():
    L = ler_csv("tabela-A-medidas-por-ano.csv")
    linhas = ["| Ano | Respostas | Literal — janela 250 | Literal — resposta inteira | Δ (p.p.) | Quase — janela 250 | Quase — resposta inteira | Δ (p.p.) |",
              "|---|---|---|---|---|---|---|---|"]
    for r in L:
        linhas.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["ano"], f'{int(r["respostas_com_texto"]):,}'.replace(",", "."),
            fmt(r["literal_janela250_pct"]), fmt(r["literal_inteira_pct"]), fmt(r["delta_literal_pp"], 2),
            fmt(r["quase_janela250_pct"]), fmt(r["quase_inteira_pct"]), fmt(r["delta_quase_pp"], 2)))
    return "\n".join(linhas)


def tabela_b():
    L = ler_csv("tabela-B-por-grupo-e-ano.csv")
    if not L:
        return "_medição por grupo ainda em processamento_"
    anos = sorted({r["ano"] for r in L}, key=int)
    grupos, vol = {}, {}
    for r in L:
        grupos.setdefault(r["grupo"], {})[r["ano"]] = r
        vol[r["grupo"]] = vol.get(r["grupo"], 0) + int(r["respostas"])
    top = sorted(vol, key=vol.get, reverse=True)
    linhas = ["| Grupo de órgãos | Respostas | " + " | ".join(anos) + " |",
              "|---" * (len(anos) + 2) + "|"]
    for g in top:
        cels = []
        for a in anos:
            r = grupos[g].get(a)
            cels.append(fmt(r["quase_pct"]) if r else "—")
        linhas.append("| %s | %s | %s |" % (g, f'{vol[g]:,}'.replace(",", "."), " | ".join(cels)))
    linhas.append("\n*Células: % de quase-repetição (resposta inteira), por grupo e ano.*")
    return "\n".join(linhas)


def tabela_c():
    L = ler_csv("tabela-C-plataformizacao.csv")
    linhas = ["| Ano | Pedidos | % pela plataforma | % por e-mail | Quase-repetição (resposta inteira) |",
              "|---|---|---|---|---|"]
    for r in L:
        linhas.append("| %s | %s | %s | %s | %s |" % (
            r["ano"], f'{int(r["pedidos_total"]):,}'.replace(",", ".") if r["pedidos_total"] else "—",
            fmt(r["plataforma_pct"]), fmt(r["email_pct"]), fmt(r["quase_inteira_pct"])))
    return "\n".join(linhas)


def correlacao():
    d = json.load(open(os.path.join(AN, "resumo.json"), encoding="utf-8"))
    c = d.get("correlacoes", {})
    if not c:
        return "_correlação ainda não calculada_"
    partes = []
    for k, v in c.items():
        nome = ("quase-repetição" if k.startswith("quase") else "repetição literal")
        if k.endswith("residuos_tendencia"):
            nome = nome + ", resíduos"
        if k.endswith("residuos_tendencia"):
            partes.append("**%s × plataformização, sem a tendência do tempo:** Pearson r = %s · "
                          "Spearman ρ = %s (n = %d anos; correlação entre os resíduos de cada série "
                          "sobre o ano)" % (nome, fmt(v["pearson"], 3), fmt(v["spearman"], 3), v["n"]))
            continue
        partes.append("**%s × plataformização:** Pearson r = %s · Spearman ρ = %s (n = %d anos)"
                      % (nome, fmt(v["pearson"], 3), fmt(v["spearman"], 3), v["n"]))
    return "\n\n".join(partes)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default=os.path.join(BASE, "2026-10-09_artigo-proposta3_resposta-inteira_v1.md"))
    ap.add_argument("--destino", default=os.path.join(BASE, "2026-10-09_artigo-proposta3_resposta-inteira_v1.md"))
    a = ap.parse_args()
    s = open(a.origem, encoding="utf-8").read()
    s = s.replace("{{TABELA_A}}", tabela_a()).replace("{{TABELA_B}}", tabela_b())
    s = s.replace("{{TABELA_C}}", tabela_c()).replace("{{CORRELACAO}}", correlacao())
    open(a.destino, "w", encoding="utf-8").write(s)
    print("tabelas inseridas em:", a.destino)
    print("\n--- TABELA A ---\n" + tabela_a())
    print("\n--- CORRELAÇÃO ---\n" + correlacao())
    print("\n--- GRUPOS (linhas) ---\n" + tabela_b()[:1200])

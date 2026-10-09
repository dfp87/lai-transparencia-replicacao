#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REPLICAÇÃO — "Os guardiões fora do espelho: perímetro institucional e desempenho
da LAI na administração pública brasileira (2012-2025)".

O que este script faz, do zero, a partir das evidências guardadas na base:
  1. le as 14 fotografias anuais (evidencias/estruturado/estruturado_<ano>.json);
  2. recalcula a serie anual de pedidos, decisoes e prazos;
  3. recalcula a fotografia de 2025 com a classificacao AUDITADA de grupos
     (evidencias/p6_grupos_v3_2025.json) -- volume, mediana, % acima de 20 dias
     e % de negativa integral por grupo;
  4. recalcula a serie por grupo (nos anos em que a classificacao existe);
  5. regrava as TABELAS em CSV e as FIGURAS em PNG (matplotlib);
  6. imprime um relatorio de conferencia: cada numero publicado no artigo e
     comparado com o recalculado, marcado BATE ou DIFERE.

PROCEDENCIA DOS DADOS (protocolo completo, para replicar de ponta a ponta):
  Os arquivos anuais vem do pacote de dados abertos da LAI (CGU/Fala.BR), CSV
  por ano. O protocolo que os transforma em evidencias esta em
  reprodutibilidade/lai_pipeline.py --etapa estruturada --anos 2012-2025,
  que le o diretorio dos CSV originais e escreve saida/estruturado_<ano>.json.
  Este script parte dessas evidencias (que estao versionadas na base) e por isso
  roda em segundos; para refazer a partir do CSV bruto, rode o pipeline antes.

Uso:  python3 reprodutibilidade/replicacao-artigo1.py
Saidas: reprodutibilidade/saidas-py/ (CSV) e reprodutibilidade/figuras-py/ (PNG)
"""
import csv
import glob
import json
import os
import statistics
import sys
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(RAIZ, "evidencias")
SAIDA = os.path.join(RAIZ, "reprodutibilidade", "saidas-py")
FIG = os.path.join(RAIZ, "reprodutibilidade", "figuras-py")
ANOS = list(range(2012, 2026))

# ---------------------------------------------------------------- numeros do artigo
# Cada item: (rotulo, valor publicado). Sao o alvo da conferencia.
PUBLICADO = [
    ("2025: pedidos", 150189),
    ("2025: pedidos com data valida", 148681),
    ("2025: mediana de dias", 13),
    ("2025: p90 de dias", 30),
    ("2025: % acima de 20 dias", 26.2),
    ("2012: pedidos", 55212),
    ("2015: pedidos", 102423),
    ("2020: pedidos", 154079),
    ("2025: pedidos (serie)", 150189),
    ("2012-2025: pedidos (total)", 1641939),
    ("2025: grupo Executivo federal (pedidos)", 45296),
    ("2025: grupo Executivo federal (% acima de 20 dias)", 31.5),
    ("2025: grupo Executivo federal (% de negativa)", 8.4),
    ("2025: grupo Autarquias (pedidos)", 43339),
    ("2025: grupo Autarquias (% acima de 20 dias)", 19.8),
    ("2025: grupo Estatais (% de negativa)", 14.8),
    ("2025: grupo Controle externo (pedidos)", 500),
    ("2025: grupo Judiciario (pedidos)", 378),
    ("2025: grupo Legislativo (pedidos)", 173),
    ("2025: grupo Defensoria (pedidos)", 34),
]


def carrega_anuais():
    dados = {}
    for ano in ANOS:
        p = os.path.join(EVID, "estruturado", "estruturado_%d.json" % ano)
        if os.path.exists(p):
            dados[ano] = json.load(open(p, encoding="utf-8"))
    return dados


def serie_anual(dados):
    linhas = []
    for ano in sorted(dados):
        d = dados[ano]
        pr = d.get("prazos") or {}
        dec = d.get("decisoes") or {}
        neg = dec.get("Acesso Negado", 0)
        tot_dec = sum(v for k, v in dec.items() if k.strip())
        linhas.append({
            "ano": ano, "pedidos": d.get("pedidos"),
            "com_data": pr.get("n"), "mediana_dias": pr.get("mediana"),
            "p90_dias": pr.get("p90"), "pct_acima_20": pr.get("pct_acima_20"),
            "negado": neg, "decisoes": tot_dec,
            "pct_negativa": round(100.0 * neg / tot_dec, 2) if tot_dec else None,
        })
    return linhas


def foto_2025(dados):
    """2025 pela classificacao auditada (v3), com os quatro indicadores."""
    p = os.path.join(EVID, "p6_grupos_v3_2025.json")
    if not os.path.exists(p):
        return [], None
    linhas = json.load(open(p, encoding="utf-8"))
    total_bruto = None
    if 2025 in dados:
        total_bruto = (dados[2025].get("prazos") or {}).get("n")
    for r in linhas:
        for k in ("p20", "neg", "con", "pro", "med", "pct"):
            if r.get(k) is None:
                r[k] = 0.0
        r["pct_acervo"] = round(100.0 * r["pedidos"] / total_bruto, 2) if total_bruto else None
    linhas.sort(key=lambda r: -r["pedidos"])
    return linhas, total_bruto


def serie_por_grupo(dados):
    """Serie por grupo, so nos anos em que o JSON anual traz a classificacao."""
    anos_com = {a: d for a, d in dados.items() if d.get("grupos")}
    return anos_com


def escreve_csv(nome, linhas, campos=None):
    if not linhas:
        print("   (nada para gravar em %s)" % nome)
        return None
    campos = campos or list(linhas[0].keys())
    p = os.path.join(SAIDA, nome)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    print("   tabela: %s (%d linhas)" % (os.path.relpath(p, RAIZ), len(linhas)))
    return p


def figuras(serie, grupos, por_grupo):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print("   (matplotlib indisponivel: %s -- figuras nao geradas)" % e)
        return 0
    os.makedirs(FIG, exist_ok=True)
    n = 0
    anos = [r["ano"] for r in serie]
    pedidos = [r["pedidos"] for r in serie]

    # Fig. 5 / G4 — serie de pedidos 2012-2025
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(anos, [p / 1000.0 for p in pedidos], marker="o", color="#1f4e79")
    ax.set_title("Pedidos de acesso a informacao no Brasil, 2012-2025")
    ax.set_xlabel("Ano"); ax.set_ylabel("Pedidos (milhares)")
    ax.grid(alpha=.3, axis="y")
    for x, y in zip(anos, pedidos):
        if x in (2012, 2015, 2020, 2025):
            ax.annotate("%.1f" % (y / 1000.0), (x, y / 1000.0), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "G4_serie-de-pedidos.png"), dpi=300); plt.close(fig); n += 1

    # Fig. 1 / G3 — volume por grupo (2025)
    if grupos:
        nomes = [g["grupo"][:38] for g in grupos][::-1]
        vals = [g["pedidos"] for g in grupos][::-1]
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.barh(nomes, vals, color="#2e6f95")
        ax.set_title("Onde esta o acervo da LAI: pedidos por grupo de orgao (2025)")
        ax.set_xlabel("Pedidos")
        for i, v in enumerate(vals):
            ax.text(v, i, " %d" % v, va="center", fontsize=8)
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "G3_grupos-volume.png"), dpi=300); plt.close(fig); n += 1

        # Fig. 2 / G1 — % acima de 20 dias por grupo
        ord1 = sorted(grupos, key=lambda g: g["p20"])
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.barh([g["grupo"][:38] for g in ord1], [g["p20"] for g in ord1], color="#a33c3c")
        ax.axvline(26.2, ls="--", color="#333", lw=1)
        ax.text(26.2, -0.9, " media nacional 2025: 26,2%", fontsize=8, color="#333")
        ax.set_title("Percentual de respostas acima de 20 dias, por grupo de orgao (2025)")
        ax.set_xlabel("% acima de 20 dias")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "G1_grupos-acima-de-20-dias.png"), dpi=300); plt.close(fig); n += 1

        # Fig. 3 / G2 — negativa integral por grupo
        ord2 = sorted(grupos, key=lambda g: g["neg"])
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.barh([g["grupo"][:38] for g in ord2], [g["neg"] for g in ord2], color="#7a5c1e")
        ax.set_title("Negativa integral por grupo de orgao (2025)")
        ax.set_xlabel("% de negativa integral")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "G2_grupos-negativa.png"), dpi=300); plt.close(fig); n += 1

    # Fig. 4 / G5 — parcela dos orgaos de controle e justica no acervo
    guardioes = ("Judici", "Legislativo", "Controle externo", "Controle interno", "Defensoria", "Conselhos")
    frac = []
    for a, d in sorted(por_grupo.items()):
        g = d["grupos"]
        tot = sum(v.get("pedidos", 0) for v in g.values())
        parc = sum(v.get("pedidos", 0) for k, v in g.items() if any(x in k for x in guardioes))
        frac.append((a, 100.0 * parc / tot if tot else 0.0))
    if frac:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot([x[0] for x in frac], [x[1] for x in frac], marker="o", color="#4b6e2f")
        ax.set_title("A parcela dos orgaos de controle e de justica no acervo da LAI, 2012-2025")
        ax.set_xlabel("Ano"); ax.set_ylabel("% do acervo"); ax.grid(alpha=.3, axis="y")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "G5_parcela-guardioes.png"), dpi=300); plt.close(fig); n += 1
    # Fig. 6 — canal de entrega (2012-2025)
    pc = os.path.join(EVID, "canal_entrega.json")
    if os.path.exists(pc):
        d = json.load(open(pc, encoding="utf-8"))
        anos_c = [x["ano"] for x in d]
        cats = ["email", "plataforma", "orientacao", "outras"]
        cores = ["#1f4e79", "#2e8b57", "#c07a1e", "#8b3a3a"]
        fig, ax = plt.subplots(figsize=(9, 5))
        for cat, cor in zip(cats, cores):
            ax.plot(anos_c, [x["canal"].get(cat, {}).get("pct", 0) for x in d], marker="o", color=cor, label=cat)
        ax.set_title("Canal de entrega da resposta da LAI, 2012-2025")
        ax.set_xlabel("Ano"); ax.set_ylabel("% dos pedidos"); ax.legend(); ax.grid(alpha=.3, axis="y")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "F2_canal-de-entrega.png"), dpi=300); plt.close(fig); n += 1

    # Fig. 7 — tipologia da negativa no registro (2012-2025)
    pt = os.path.join(EVID, "tipologia_negativa.json")
    if os.path.exists(pt):
        d = json.load(open(pt, encoding="utf-8"))
        anos_t = sorted(int(a) for a in d)
        fams = sorted({f for a in d.values() for f in a.get("familias", {})})
        fig, ax = plt.subplots(figsize=(10, 5.5))
        for i, f in enumerate(fams):
            ax.plot(anos_t, [100.0 * d[str(a)]["familias"].get(f, 0) / max(1, d[str(a)]["negados"]) for a in anos_t],
                    marker="o", label=f[:26])
        ax.set_title("Tipologia da negativa no registro, 2012-2025")
        ax.set_xlabel("Ano"); ax.set_ylabel("% dos pedidos negados"); ax.legend(fontsize=7, ncol=2); ax.grid(alpha=.3, axis="y")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "F3_tipologia-da-negativa.png"), dpi=300); plt.close(fig); n += 1
    return n


def confere(serie, grupos, total):
    """Compara o recalculado com o publicado e imprime BATE / DIFERE."""
    idx = {r["ano"]: r for r in serie}
    g = {x["grupo"].lower(): x for x in grupos}
    calc = {
        "2025: pedidos": idx.get(2025, {}).get("pedidos"),
        "2025: pedidos com data valida": idx.get(2025, {}).get("com_data"),
        "2025: mediana de dias": idx.get(2025, {}).get("mediana_dias"),
        "2025: p90 de dias": idx.get(2025, {}).get("p90_dias"),
        "2025: % acima de 20 dias": idx.get(2025, {}).get("pct_acima_20"),
        "2012: pedidos": idx.get(2012, {}).get("pedidos"),
        "2015: pedidos": idx.get(2015, {}).get("pedidos"),
        "2020: pedidos": idx.get(2020, {}).get("pedidos"),
        "2025: pedidos (serie)": idx.get(2025, {}).get("pedidos"),
        "2012-2025: pedidos (total)": total,
    }
    for rot, chave in [("Executivo federal", "executivo federal"),
                       ("Autarquias", "autarquias"),
                       ("Estatais", "estatais")]:
        reg = next((v for k, v in g.items() if chave in k), None)
        if reg:
            calc["2025: grupo %s (pedidos)" % rot] = reg["pedidos"]
            calc["2025: grupo %s (%% acima de 20 dias)" % rot] = round(reg["p20"], 1)
            calc["2025: grupo %s (%% de negativa)" % rot] = round(reg["neg"], 1)
    for rot, chave in [("Controle externo", "controle externo"), ("Judiciario", "judici"),
                       ("Legislativo", "legislativo"), ("Defensoria", "defensoria")]:
        reg = next((v for k, v in g.items() if chave in k), None)
        if reg:
            calc["2025: grupo %s (pedidos)" % rot] = reg["pedidos"]

    print("\n=== CONFERENCIA: recalculado x publicado ===")
    bate = difere = 0
    for rot, pub in PUBLICADO:
        c = calc.get(rot)
        if c is None:
            print("   %-52s publicado %-10s recalculado: INDISPONIVEL" % (rot, pub)); difere += 1; continue
        ok = abs(float(c) - float(pub)) <= (0.06 if isinstance(pub, float) else 0)
        print("   %-52s publicado %-10s recalculado %-10s %s" % (rot, pub, round(float(c), 2) if isinstance(c, float) else c, "BATE" if ok else "DIFERE"))
        bate += 1 if ok else 0
        difere += 0 if ok else 1
    print("\n   BATE: %d | DIFERE: %d" % (bate, difere))
    return bate, difere


def main():
    os.makedirs(SAIDA, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    print("=== REPLICACAO — artigo 1: os guardioes fora do espelho ===")
    dados = carrega_anuais()
    print("anos carregados: %d (%s)" % (len(dados), ", ".join(str(a) for a in sorted(dados))))
    if not dados:
        print("ERRO: nenhuma evidencia anual encontrada em %s" % os.path.join(EVID, "estruturado"))
        return 1

    serie = serie_anual(dados)
    total = sum(r["pedidos"] or 0 for r in serie)
    print("total de pedidos 2012-2025 (soma das evidencias anuais): %d" % total)
    escreve_csv("tabela-serie-anual.csv", serie)

    grupos, base_2025 = foto_2025(dados)
    print("fotografia de 2025 com classificacao auditada: %d grupos (base: %s pedidos com data)" % (len(grupos), base_2025))
    if grupos:
        escreve_csv("tabela-grupos-2025.csv", grupos)

    por_grupo = serie_por_grupo(dados)
    print("anos com classificacao por grupo: %s" % ", ".join(str(a) for a in sorted(por_grupo)))
    linhas_g = []
    for a, d in sorted(por_grupo.items()):
        for k, v in d["grupos"].items():
            linhas_g.append({"ano": a, "grupo": k, **v})
    if linhas_g:
        escreve_csv("tabela-serie-por-grupo.csv", linhas_g)

    print("\nfiguras:")
    n = figuras(serie, grupos, por_grupo)
    print("   %d figuras em %s" % (n, os.path.relpath(FIG, RAIZ)))

    bate, difere = confere(serie, grupos, total)
    print("\nfiguras/tabelas regravadas: %s | %s" % (os.path.relpath(FIG, RAIZ), os.path.relpath(SAIDA, RAIZ)))
    return 0 if difere == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

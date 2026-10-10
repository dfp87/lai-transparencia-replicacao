#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Figuras do artigo A (contestação) e análise de precisão do artigo B (concordância).

A) figuras do Estudo A a partir de `saidas-recursos/*.csv`
B) precisão esperada de um κ de Cohen para diferentes n e prevalências — é o cálculo que
   dimensiona a amostra de anotação do Estudo B antes de qualquer anotação existir.
"""
import csv, json, math, os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(AQUI, "saidas-recursos")
FIGS = os.path.join(REC, "figuras")
os.makedirs(FIGS, exist_ok=True)
plt.rcParams.update({"font.size": 9, "figure.dpi": 300, "savefig.dpi": 300,
                     "axes.spines.top": False, "axes.spines.right": False})


def ler(nome):
    with open(os.path.join(REC, nome), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------------ A) FIGURAS
pa = ler("por-ano.csv")
anos = [int(r["ano"]) for r in pa]


def col(r, k):
    v = r.get(k, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# A1 — desfechos por ano
fig, ax = plt.subplots(figsize=(7.2, 4))
for k, rot, cor in (("provido_ou_parcial_pct", "provido ou parcialmente provido", "#1d4ed8"),
                    ("nao_conhecido_pct", "não conhecido", "#b91c1c"),
                    ("sem_resposta_pct", "sem resposta registrada", "#6b7280")):
    ax.plot(anos, [col(r, k) for r in pa], "o-", lw=1.5, ms=3.5, color=cor, label=rot)
ax.set_xlabel("ano do recurso"); ax.set_ylabel("% dos recursos")
ax.set_title("O que acontece com a contestação do cidadão (2012–2025)")
ax.legend(frameon=False, fontsize=8); ax.grid(alpha=.25, lw=.5)
fig.tight_layout(); fig.savefig(os.path.join(FIGS, "A1-desfechos-por-ano.png")); plt.close(fig)

# A2 — volume e taxa de provimento na mesma série
fig, ax = plt.subplots(figsize=(7.2, 4))
ax.bar(anos, [int(r["recursos"]) for r in pa], color="#c7d2fe", label="recursos (eixo esquerdo)")
ax.set_ylabel("recursos por ano", color="#3730a3")
ax2 = ax.twinx()
ax2.plot(anos, [col(r, "provido_ou_parcial_pct") for r in pa], "s-", color="#b91c1c", lw=1.6, ms=3.5,
         label="provido ou parcial (%)")
ax2.set_ylabel("% provido ou parcial", color="#b91c1c")
ax.set_title("Volume de contestações e taxa de provimento")
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="lower right")
ax.grid(alpha=.2, lw=.5)
fig.tight_layout(); fig.savefig(os.path.join(FIGS, "A2-volume-e-provimento.png")); plt.close(fig)

# A3 — instância × desfecho (barras empilhadas)
pi = ler("instancia-x-desfecho.csv")
rot = [k for k in pi[0] if k not in ("recursos", "provido_ou_parcial_pct", "nao_conhecido_pct",
                                      "sem_resposta_pct", "Provido", "Provido em parte",
                                      "Não provido", "Não conhecido", "Perda de objeto",
                                      "Sem resposta registrada", "Outros")][0]
pi = [r for r in pi if int(r["recursos"]) >= 200][:7]
vias = [("Provido", "#1d4ed8"), ("Provido em parte", "#60a5fa"),
        ("Não provido", "#b91c1c"), ("Não conhecido", "#f59e0b"),
        ("Perda de objeto", "#9ca3af"), ("Sem resposta registrada", "#4b5563"),
        ("Outros", "#d1d5db")]
fig, ax = plt.subplots(figsize=(7.6, 4))
esq = [0] * len(pi)
for v, cor in vias:
    vals = [100 * col(r, v) / int(r["recursos"]) for r in pi]
    ax.barh([r[rot][:22] for r in pi], vals, left=esq, color=cor, label=v, height=.62)
    esq = [a + b for a, b in zip(esq, vals)]
ax.set_xlabel("% dos recursos da instância"); ax.set_title("Desfecho por instância de julgamento")
ax.legend(frameon=False, fontsize=7, ncol=4, loc="lower right")
ax.grid(alpha=.2, lw=.5, axis="x")
fig.tight_layout(); fig.savefig(os.path.join(FIGS, "A3-desfecho-por-instancia.png")); plt.close(fig)

# ------------------------------------------------------------- B) PRECISÃO DO κ
def var_kappa(k, n, p1):
    """Variância aproximada do κ de Cohen (fórmula de Fleiss et al.) para duas categorias."""
    p2 = 1 - p1
    # concordância observada implícita no κ, com concordância esperada por acaso
    pe = p1 ** 2 + p2 ** 2
    po = k * (1 - pe) + pe
    a = p1 * (po + p1 - 1) * (1 - p1)
    b = (1 - p1) * (po + 1 - 2 * p1) * p1
    return (a + b) / (n * (1 - pe) ** 2)


cenarios = []
for n in (100, 200, 300, 400, 500, 630, 800, 1000):
    for prev in (0.20, 0.35, 0.50):
        for k in (0.60, 0.70, 0.80):
            v = var_kappa(k, n, prev)
            cenarios.append({"n": n, "prevalencia_evasao": prev, "kappa_esperado": k,
                             "dp_kappa": round(math.sqrt(v), 3)})
with open(os.path.join(REC, "precisao-kappa.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(cenarios[0])); w.writeheader(); w.writerows(cenarios)

# figura: dp do κ por n, para κ = 0,70 e três prevalências
fig, ax = plt.subplots(figsize=(5.6, 3.8))
for prev, cor in ((0.20, "#6b7280"), (0.35, "#1d4ed8"), (0.50, "#b91c1c")):
    xs = [c["n"] for c in cenarios if abs(c["prevalencia_evasao"] - prev) < 1e-9 and abs(c["kappa_esperado"] - 0.70) < 1e-9]
    ys = [c["dp_kappa"] for c in cenarios if abs(c["prevalencia_evasao"] - prev) < 1e-9 and abs(c["kappa_esperado"] - 0.70) < 1e-9]
    ax.plot(xs, ys, "o-", lw=1.5, ms=3.5, color=cor, label="evasão em %.0f%% das respostas" % (100 * prev))
ax.axhline(0.05, ls="--", lw=1, color="#9ca3af")
ax.set_xlabel("nº de respostas anotadas por dois codificadores")
ax.set_ylabel("erro-padrão do κ")
ax.set_title("Precisão do κ de Cohen (κ esperado = 0,70)")
ax.legend(frameon=False, fontsize=7.5); ax.grid(alpha=.25, lw=.5)
fig.tight_layout(); fig.savefig(os.path.join(FIGS, "B1-precisao-kappa.png")); plt.close(fig)

print("figuras:", sorted(os.listdir(FIGS)))
print("\nprecisão do κ (κ esperado = 0,70, prevalência de evasão 35%):")
for c in cenarios:
    if abs(c["prevalencia_evasao"] - 0.35) < 1e-9 and abs(c["kappa_esperado"] - 0.70) < 1e-9:
        print("   n=%4d  dp(κ)=%.3f  intervalo ±1,96 dp = ±%.3f" % (c["n"], c["dp_kappa"], 1.96 * c["dp_kappa"]))

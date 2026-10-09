#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolida a medição da RESPOSTA INTEIRA e cruza com a plataformização do atendimento.

Entradas:
  reprodutibilidade/saidas-minhash/minhash_inteira_<ano>.json      (medição nova, resposta inteira)
  reprodutibilidade/saidas-minhash/consolidado_minhash_FINAL.json  (medição antiga, janela de 250)
  reprodutibilidade/saidas-grupo-ano/grupo-ano_<ano>.json          (por grupo de órgão e ano)
  evidencias/canal_entrega.json                                    (canal de resposta por ano)

Saídas (em reprodutibilidade/saidas-analise/):
  tabela-A-medidas-por-ano.csv        as duas medidas lado a lado, ano a ano
  tabela-B-por-grupo-e-ano.csv        respostas, literal e quase-repetição por grupo e ano
  tabela-C-plataformizacao.csv        canal do atendimento por ano, com a padronização ao lado
  tabela-D-correlacao.csv             correlação entre padronização e plataformização
  resumo.json                         os números citáveis, com o total e as médias ponderadas
  figuras/                            F1 (as duas medidas), F2 (por grupo), F3 (dispersão)
"""
import csv, glob, json, os, statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDAS = os.path.join(AQUI, "saidas-analise")
FIGS = os.path.join(SAIDAS, "figuras")
os.makedirs(FIGS, exist_ok=True)

# ----------------------------------------------------------------- entrada
def ler_json(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)

inteira = {}
for f in sorted(glob.glob(os.path.join(AQUI, "saidas-minhash", "minhash_inteira_*.json"))):
    if "_amostra" in f:
        continue
    d = ler_json(f)
    if d.get("respostas_com_texto"):
        inteira[int(d["ano"])] = d

janela_cons = ler_json(os.path.join(AQUI, "saidas-minhash", "consolidado_minhash_FINAL.json"))
janela = {int(a): v for a, v in janela_cons.get("por_ano", {}).items()}

grupo_ano = {}
for f in sorted(glob.glob(os.path.join(AQUI, "saidas-grupo-ano", "grupo-ano_*.json"))):
    if "_amostra" in f:
        continue
    d = ler_json(f)
    if d.get("grupos"):
        grupo_ano[int(d["ano"])] = d

canal = {int(r["ano"]): r for r in ler_json(os.path.join(RAIZ, "evidencias", "canal_entrega.json"))}

anos = sorted(set(inteira) | set(janela) | set(grupo_ano))
anos_com_medida = sorted(inteira)

# ----------------------------------------------------------------- tabela A
linhas_a = []
for a in anos_com_medida:
    n = inteira[a]["respostas_com_texto"]
    j = janela.get(a, {})
    linhas_a.append({
        "ano": a, "respostas_com_texto": n,
        "literal_janela250_pct": j.get("md5_250_pct"),
        "quase_janela250_pct": j.get("minhash_final_pct", j.get("minhash_pct")),
        "literal_inteira_pct": inteira[a]["literal_inteira_md5"]["pct"],
        "quase_inteira_pct": inteira[a]["minhash"]["pct"],
        "tamanho_medio_caracteres": inteira[a]["tamanho_texto"]["media"],
        "baldes_descartados": inteira[a]["minhash"]["baldes_ignorados_por_tamanho"],
        "maior_grupo_de_repeticao": inteira[a]["minhash"]["maior_grupo"],
        "grupos_ge_5": inteira[a]["minhash"]["grupos_ge_5"],
    })
for r in linhas_a:
    q, l = r["quase_janela250_pct"], r["quase_inteira_pct"]
    r["delta_quase_pp"] = round(l - q, 2) if (q is not None and l is not None) else None
    r["delta_literal_pp"] = (round(r["literal_inteira_pct"] - r["literal_janela250_pct"], 2)
                             if r["literal_janela250_pct"] is not None else None)

with open(os.path.join(SAIDAS, "tabela-A-medidas-por-ano.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(linhas_a[0])); w.writeheader(); w.writerows(linhas_a)

# médias ponderadas pelo número de respostas
def ponderada(campo):
    num = den = 0.0
    for r in linhas_a:
        v = r.get(campo)
        if v is not None:
            num += v * r["respostas_com_texto"]; den += r["respostas_com_texto"]
    return round(num / den, 2) if den else None

total_respostas = sum(r["respostas_com_texto"] for r in linhas_a)
resumo = {
    "anos_medidos": [r["ano"] for r in linhas_a],
    "total_respostas_com_texto": total_respostas,
    "quase_janela250_pct_ponderado": ponderada("quase_janela250_pct"),
    "quase_inteira_pct_ponderado": ponderada("quase_inteira_pct"),
    "literal_janela250_pct_ponderado": ponderada("literal_janela250_pct"),
    "literal_inteira_pct_ponderado": ponderada("literal_inteira_pct"),
}

# ----------------------------------------------------------------- tabela B (grupo x ano)
linhas_b = []
for a in sorted(grupo_ano):
    for g in grupo_ano[a]["grupos"]:
        linhas_b.append({"ano": a, "grupo": g["grupo"], "respostas": g["respostas"],
                         "literal_pct": g["literal_pct"], "quase_pct": g["quase_pct"]})
if linhas_b:
    with open(os.path.join(SAIDAS, "tabela-B-por-grupo-e-ano.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas_b[0])); w.writeheader(); w.writerows(linhas_b)

# ----------------------------------------------------------------- tabela C (plataformização) e D (correlação)
linhas_c = []
for r in linhas_a:
    a = r["ano"]
    c = canal.get(a, {}).get("canal", {})
    linhas_c.append({
        "ano": a, "pedidos_total": canal.get(a, {}).get("pedidos"),
        "plataforma_pct": (c.get("plataforma") or {}).get("pct"),
        "email_pct": (c.get("email") or {}).get("pct"),
        "quase_inteira_pct": r["quase_inteira_pct"],
        "literal_inteira_pct": r["literal_inteira_pct"],
    })
if linhas_c:
    with open(os.path.join(SAIDAS, "tabela-C-plataformizacao.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas_c[0])); w.writeheader(); w.writerows(linhas_c)


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs) ** 0.5
    syy = sum((y - my) ** 2 for y in ys) ** 0.5
    return round(sxy / (sxx * syy), 3) if sxx and syy else None


def spearman(xs, ys):
    def ordem(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(o):
            r[i] = pos + 1
        return r
    return pearson(ordem(xs), ordem(ys))


pares = [(r["plataforma_pct"], r["quase_inteira_pct"]) for r in linhas_c
         if r["plataforma_pct"] is not None and r["quase_inteira_pct"] is not None]
pares_lit = [(r["plataforma_pct"], r["literal_inteira_pct"]) for r in linhas_c
             if r["plataforma_pct"] is not None and r["literal_inteira_pct"] is not None]
corr = {}
if len(pares) >= 3:
    xs, ys = zip(*pares)
    corr["quase_inteira_vs_plataforma"] = {"n": len(pares), "pearson": pearson(list(xs), list(ys)),
                                           "spearman": spearman(list(xs), list(ys))}
if len(pares_lit) >= 3:
    xs, ys = zip(*pares_lit)
    corr["literal_inteira_vs_plataforma"] = {"n": len(pares_lit), "pearson": pearson(list(xs), list(ys)),
                                             "spearman": spearman(list(xs), list(ys))}
# robustez: correlação entre os RESÍDUOS de cada série sobre o ano (sem a tendência do tempo)
def _residuos(vals, xs):
    n = len(xs); mx = sum(xs) / n; my = sum(vals) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, vals)) / sum((x - mx) ** 2 for x in xs)
    a = my - b * mx
    return [y - (a + b * x) for x, y in zip(xs, vals)]

_pares_res = [(r["plataforma_pct"], r["quase_inteira_pct"], r["literal_inteira_pct"]) for r in linhas_c
              if r["plataforma_pct"] is not None and r["quase_inteira_pct"] is not None]
if len(_pares_res) >= 3:
    xs = [p[0] for p in _pares_res]
    rx = _residuos(xs, [r["ano"] for r in linhas_c if r["plataforma_pct"] is not None and r["quase_inteira_pct"] is not None])
    for nome, idx in (("quase_inteira_vs_plataforma_residuos_tendencia", 1),
                      ("literal_inteira_vs_plataforma_residuos_tendencia", 2)):
        ys = [p[idx] for p in _pares_res]
        if any(v is None for v in ys):
            continue
        ry = _residuos(ys, [r["ano"] for r in linhas_c if r["plataforma_pct"] is not None and r["quase_inteira_pct"] is not None])
        corr[nome] = {"n": len(xs), "pearson": pearson(rx, ry), "spearman": spearman(rx, ry)}

resumo["correlacoes"] = corr
with open(os.path.join(SAIDAS, "tabela-D-correlacao.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["par", "n", "pearson", "spearman"])
    for k, v in corr.items():
        w.writerow([k, v["n"], v["pearson"], v["spearman"]])

with open(os.path.join(SAIDAS, "resumo.json"), "w", encoding="utf-8") as fh:
    json.dump(resumo, fh, ensure_ascii=False, indent=1)

# ----------------------------------------------------------------- figuras
plt.rcParams.update({"font.size": 9, "figure.dpi": 300, "savefig.dpi": 300,
                     "axes.spines.top": False, "axes.spines.right": False})

# F1 — as duas medidas, ano a ano
x = [r["ano"] for r in linhas_a]
fig, ax = plt.subplots(figsize=(7.2, 4))
ax.plot(x, [r["quase_janela250_pct"] for r in linhas_a], "o-", lw=1.4, ms=3.5,
        color="#6b7280", label="quase-repetição — janela de 250 caracteres")
ax.plot(x, [r["quase_inteira_pct"] for r in linhas_a], "s-", lw=1.6, ms=3.5,
        color="#1d4ed8", label="quase-repetição — resposta inteira")
ax.plot(x, [r["literal_janela250_pct"] for r in linhas_a], "^--", lw=1.2, ms=3.2,
        color="#9ca3af", label="repetição literal — janela de 250")
ax.plot(x, [r["literal_inteira_pct"] for r in linhas_a], "v--", lw=1.4, ms=3.2,
        color="#b91c1c", label="repetição literal — resposta inteira")
ax.set_xlabel("ano da resposta"); ax.set_ylabel("% das respostas com texto")
ax.set_title("Resposta padronizada: o que a janela de 250 caracteres mede e o que a resposta inteira mede")
ax.legend(frameon=False, fontsize=7.5); ax.grid(alpha=.25, lw=.5)
fig.tight_layout(); fig.savefig(os.path.join(FIGS, "F1-duas-medidas.png")); plt.close(fig)

# F2 — por grupo de órgão (série dos grupos com maior volume)
if linhas_b:
    por_grupo = {}
    for r in linhas_b:
        por_grupo.setdefault(r["grupo"], {})[r["ano"]] = r
    volume = {g: sum(v[a]["respostas"] for a in v) for g, v in por_grupo.items()}
    top = sorted(volume, key=volume.get, reverse=True)[:6]
    fig, ax = plt.subplots(figsize=(7.2, 4))
    for g in top:
        ys = [por_grupo[g].get(a, {}).get("quase_pct") for a in x]
        ax.plot(x, ys, "o-", lw=1.3, ms=3, label="%s (n=%s)" % (g.split(",")[0][:26], f"{volume[g]:,}".replace(",", ".")))
    ax.set_xlabel("ano"); ax.set_ylabel("% de quase-repetição (resposta inteira)")
    ax.set_title("Padronização da resposta por grupo de órgãos")
    ax.legend(frameon=False, fontsize=7); ax.grid(alpha=.25, lw=.5)
    fig.tight_layout(); fig.savefig(os.path.join(FIGS, "F2-por-grupo.png")); plt.close(fig)

# F3 — dispersão padronização x plataformização
if len(pares) >= 3:
    xs, ys = zip(*pares)
    fig, ax = plt.subplots(figsize=(5.2, 4))
    ax.scatter(xs, ys, s=22, color="#1d4ed8")
    for xx, yy, a in zip(xs, ys, [r["ano"] for r in linhas_c if r["plataforma_pct"] is not None
                                  and r["quase_inteira_pct"] is not None]):
        ax.annotate(str(a), (xx, yy), fontsize=6.5, xytext=(3, 3), textcoords="offset points")
    n = len(xs); mx, my = sum(xs) / n, sum(ys) / n
    b = sum((p - mx) * (q - my) for p, q in zip(xs, ys)) / sum((p - mx) ** 2 for p in xs)
    a0 = my - b * mx
    lim = [min(xs), max(xs)]
    ax.plot(lim, [a0 + b * v for v in lim], "--", color="#b91c1c", lw=1.1,
            label="reta ajustada (r = %s)" % corr["quase_inteira_vs_plataforma"]["pearson"])
    ax.set_xlabel("% do atendimento pela plataforma"); ax.set_ylabel("% de quase-repetição")
    ax.set_title("Padronização da resposta e plataformização do atendimento")
    ax.legend(frameon=False, fontsize=7.5); ax.grid(alpha=.25, lw=.5)
    fig.tight_layout(); fig.savefig(os.path.join(FIGS, "F3-plataformizacao.png")); plt.close(fig)

print(json.dumps(resumo, ensure_ascii=False, indent=1))
print("\nanos sem medição da resposta inteira:", sorted(set(range(min(anos), max(anos) + 1)) - set(anos_com_medida)))

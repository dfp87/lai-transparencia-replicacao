#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estudo A — o recurso como ato administrativo: base analítica e primeira bateria descritiva.

Fonte: arquivos abertos anuais `*Recursos_Reclamacoes_csv_<ano>.csv` (Fala.BR/CGU), 2012-2025.
Os campos são CODIFICADOS — não há texto livre do cidadão: tipo do recurso, especificação,
instância, resposta ao recurso e informação concedida.

Saídas em `saidas-recursos/`:
  base-recursos.csv, por-ano.csv, motivo-x-desfecho.csv, instancia-x-desfecho.csv,
  guardioes.csv, resumo.json
"""
import glob, json, os, re, statistics

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "saidas-recursos")
os.makedirs(SAIDA, exist_ok=True)
DIR = "/root/lai/csv"

COLS = ["IdRecurso", "IdPedido", "Esfera", "UF", "Municipio", "OrgaoDestinatario", "Instancia",
        "Situacao", "DataRegistro", "PrazoAtendimento", "DataResposta", "TipoRecurso",
        "TipoResposta", "EspecificacaoRecurso", "DetalhamentoRecurso", "InformacaoConcedida"]

VIAS = {"Deferido": "Provido", "Parcialmente deferido": "Provido em parte",
        "Indeferido": "Não provido", "Não conhecimento": "Não conhecido",
        "Perda de objeto": "Perda de objeto"}
VIAS_ORDEM = ["Provido", "Provido em parte", "Não provido", "Não conhecido",
              "Perda de objeto", "Sem resposta registrada", "Outros"]

partes = []
for f in sorted(glob.glob(os.path.join(DIR, "*Recursos_Reclamacoes_csv_*.csv"))):
    ano = int(os.path.basename(f).rsplit("_", 1)[1].split(".")[0])
    d = pd.read_csv(f, sep=";", encoding="utf-16", dtype=str)
    d = d[[c for c in COLS if c in d.columns]].copy()
    d["ano"] = ano
    r = d["TipoResposta"].fillna("").astype(str).str.strip() if "TipoResposta" in d.columns else ""
    d["via"] = r.map(VIAS).fillna(pd.Series(["Sem resposta registrada"] * len(d), index=d.index)) if isinstance(r, pd.Series) else "Sem resposta registrada"
    if isinstance(r, pd.Series):
        d.loc[r.ne("").fillna(False) & d["via"].eq("Sem resposta registrada"), "via"] = "Outros"
    d["dias"] = (pd.to_datetime(d.get("DataResposta"), dayfirst=True, errors="coerce")
                 - pd.to_datetime(d.get("DataRegistro"), dayfirst=True, errors="coerce")).dt.days
    partes.append(d)

base = pd.concat(partes, ignore_index=True)
base.to_csv(os.path.join(SAIDA, "base-recursos.csv"), index=False, encoding="utf-8")
tot = len(base)

# ---- por ano
g = base.groupby(["ano", "via"]).size().unstack(fill_value=0).reindex(columns=VIAS_ORDEM, fill_value=0)
dias = base[(base["dias"].notna()) & (base["dias"] >= 0)].groupby("ano")["dias"].median()
por_ano = g.copy()
por_ano["recursos"] = g.sum(axis=1)
por_ano["provido_ou_parcial_pct"] = (100 * (g.get("Provido", 0) + g.get("Provido em parte", 0)) / por_ano["recursos"]).round(2)
por_ano["nao_conhecido_pct"] = (100 * g.get("Não conhecido", 0) / por_ano["recursos"]).round(2)
por_ano["sem_resposta_pct"] = (100 * g.get("Sem resposta registrada", 0) / por_ano["recursos"]).round(2)
por_ano["dias_mediana"] = dias
por_ano.to_csv(os.path.join(SAIDA, "por-ano.csv"), encoding="utf-8")

def crosstab(col, nome, rotulo):
    if col not in base.columns:
        return []
    t = base.groupby([col, "via"]).size().unstack(fill_value=0).reindex(columns=VIAS_ORDEM, fill_value=0)
    t["recursos"] = t.sum(axis=1)
    t["provido_ou_parcial_pct"] = (100 * (t.get("Provido", 0) + t.get("Provido em parte", 0)) / t["recursos"]).round(2)
    t["nao_conhecido_pct"] = (100 * t.get("Não conhecido", 0) / t["recursos"]).round(2)
    t["sem_resposta_pct"] = (100 * t.get("Sem resposta registrada", 0) / t["recursos"]).round(2)
    t = t.sort_values("recursos", ascending=False)
    t.to_csv(os.path.join(SAIDA, nome), encoding="utf-8")
    return t.reset_index().rename(columns={col: rotulo}).to_dict("records")

l_mot = crosstab("TipoRecurso", "motivo-x-desfecho.csv", "motivo")
l_ins = crosstab("Instancia", "instancia-x-desfecho.csv", "instancia")

# ---- guardiões: os mesmos grupos procurados no artigo 1
orgaos = base["OrgaoDestinatario"].fillna("").astype(str).str.strip()
orgaos = orgaos[orgaos.ne("")]
padroes = {"Ministério Público": r"minist[ée]rio p[úu]blico|procuradoria-geral de justi[çc]a|\bmpf\b|\bmpt\b",
           "Judiciário": r"\bstf\b|supremo tribunal|tribunal de justi[çc]a|\btrf\b|\btrt\b|\btst\b|\btse\b|\bstj\b",
           "Legislativo": r"c[âa]mara dos deputados|senado federal|congresso nacional|assembleia legislativa",
           "Controle externo": r"tribunal de contas|\btce\b|\btcm\b|\btcu\b",
           "Controle interno": r"controladoria|corregedoria|ouvidoria-geral"}
tot_org = len(orgaos)
guard = [{"grupo": k, "recursos": int(orgaos.str.contains(rx, case=False, regex=True).sum()),
          "pct": round(100 * orgaos.str.contains(rx, case=False, regex=True).sum() / tot_org, 3)}
         for k, rx in padroes.items()]
pd.DataFrame(guard).to_csv(os.path.join(SAIDA, "guardioes.csv"), index=False, encoding="utf-8")

resumo = {"total_recursos": tot, "recursos_com_orgao": tot_org, "orgaos_distintos": int(orgaos.nunique()),
          "provido_ou_parcial_pct": round(100 * (g.get("Provido", 0).sum() + g.get("Provido em parte", 0).sum()) / tot, 2),
          "nao_conhecido_pct": round(100 * g.get("Não conhecido", 0).sum() / tot, 2),
          "sem_resposta_pct": round(100 * g.get("Sem resposta registrada", 0).sum() / tot, 2),
          "top_orgaos": orgaos.value_counts().head(8).to_dict(),
          "por_ano": json.loads(por_ano.reset_index().to_json(orient="records", date_format="iso")),
          "motivos": l_mot[:6], "instancias": l_ins[:6], "guardioes": guard}
with open(os.path.join(SAIDA, "resumo.json"), "w", encoding="utf-8") as fh:
    json.dump(resumo, fh, ensure_ascii=False, indent=1)

print(json.dumps({k: resumo[k] for k in ("total_recursos", "recursos_com_orgao", "orgaos_distintos",
                                         "provido_ou_parcial_pct", "nao_conhecido_pct", "sem_resposta_pct")},
                 ensure_ascii=False))
print("\nPOR ANO:")
for a, r in por_ano.iterrows():
    print("  %d  n=%6d  provido+parcial=%5.1f%%  não conhecido=%5.1f%%  sem resposta=%5.1f%%  mediana=%s d" %
          (a, r["recursos"], r["provido_ou_parcial_pct"], r["nao_conhecido_pct"], r["sem_resposta_pct"], r["dias_mediana"]))
print("\nINSTÂNCIA × DESFECHO:")
for r in l_ins:
    print("  %-17s n=%7d provido+parcial=%5.1f%%  não conhecido=%5.1f%%  sem resposta=%5.1f%%" %
          (str(r["instancia"])[:17], r["recursos"], r["provido_ou_parcial_pct"], r["nao_conhecido_pct"], r["sem_resposta_pct"]))
print("\nMOTIVO × DESFECHO (top 6):")
for r in l_mot[:6]:
    print("  %-52s n=%6d provido+parcial=%5.1f%%  não conhecido=%5.1f%%" %
          (str(r["motivo"])[:52], r["recursos"], r["provido_ou_parcial_pct"], r["nao_conhecido_pct"]))
print("\nGUARDIÕES:")
for x in guard:
    print("  %-20s %6d  %.3f%%" % (x["grupo"], x["recursos"], x["pct"]))
print("\ntop órgãos:", [(k[:36], v) for k, v in list(resumo["top_orgaos"].items())[:5]])

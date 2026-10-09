#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Padronização da resposta por GRUPO DE ÓRGÃO e por ANO — dados abertos da LAI (2015-2025).

Para cada ano e cada grupo de órgãos, mede duas coisas sobre a MESMA definição operacional:

  1. resposta padronizada por repetição LITERAL — md5 da resposta inteira normalizada
     (minúsculas, sem pontuação), contando os grupos de resposta com 5 ou mais ocorrências no ano;
  2. resposta padronizada por QUASE-REPETIÇÃO — MinHash/LSH com os mesmos parâmetros do
     minhash_resposta_inteira.py (shingle de 5 palavras, 128 permutações, semente 20261008,
     Jaccard >= 0,80, banda de 8 linhas x 16 bandas, baldes > 200 descartados e contados,
     grupo mínimo de 5 respostas no ano).

ATENÇÃO — regra de classificação: é a regra DECLARADA em `lai_pipeline.py::classificar_orgao`,
aplicada UNIFORMEMENTE a todos os anos (é isso que permite comparar anos entre si). A tabela de
perímetro do artigo 1 usa, para 2025, uma revisão auditada da classificação (v3, arquivo
`p6_grupos_v3_2025.json`), cujos rótulos e fronteiras diferem desta regra: os dois conjuntos não
devem ser misturados numa mesma tabela.

Uso:
    python3 padronizacao_por_grupo_ano.py --anos 2015-2025
    python3 padronizacao_por_grupo_ano.py --ano 2025 --amostra 20000
"""
import argparse, hashlib, inspect, json, os, sys, time

import numpy as np
import pandas as pd

DIR_TXT = "/root/lai/txt"
AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "saidas-grupo-ano")
sys.path.insert(0, AQUI)

# funções e parâmetros vêm do próprio módulo de medição (uma só definição para o projeto)
from minhash_resposta_inteira import (  # noqa: E402
    normalizar, assinatura, banda_chaves, K, BANDAS, LINHAS_BANDA,
    JACCARD, LIMIAR_GRUPO, MAX_BALDE, SEMENTE, SHINGLE,
)
from lai_pipeline import classificar_orgao  # noqa: E402

CHUNK = 20000


def processar(ano, amostra=None):
    arqs = sorted(p for p in os.listdir(DIR_TXT) if p.endswith("Pedidos_csv_%d.csv" % ano))
    if not arqs:
        return {"ano": ano, "erro": "pacote do ano ausente"}
    t0 = time.time()
    colunas = ("IdPedido", "Esfera", "OrgaoDestinatario", "Resposta")

    sigs, grupos_sig = [], []
    memo_grupo = {}
    md5_por_grupo = {}          # md5 -> [grupo, n]
    n_por_grupo = {}
    lidos = 0
    leitor = pd.read_csv(os.path.join(DIR_TXT, arqs[0]), sep=";", encoding="utf-16",
                         dtype=str, chunksize=CHUNK, usecols=lambda c: c in colunas)
    for ch in leitor:
        if "Resposta" not in ch.columns:
            continue
        txt = ch["Resposta"].fillna("").astype(str).str.strip()
        org = ch["OrgaoDestinatario"].fillna("").astype(str) if "OrgaoDestinatario" in ch.columns else None
        esf = ch["Esfera"].fillna("").astype(str) if "Esfera" in ch.columns else None
        for i in np.flatnonzero(txt.ne("").to_numpy()):
            if amostra is not None and lidos >= amostra:
                break
            lidos += 1
            o = org.iloc[i] if org is not None else ""
            e = esf.iloc[i] if esf is not None else ""
            k = (o, e)
            g = memo_grupo.get(k)
            if g is None:
                g = memo_grupo[k] = classificar_orgao(o, e)
            n_por_grupo[g] = n_por_grupo.get(g, 0) + 1
            n_txt = normalizar(txt.iloc[i])
            chave = hashlib.md5(n_txt.encode()).digest()
            reg = md5_por_grupo.get(chave)
            if reg is None:
                md5_por_grupo[chave] = [g, 1]
            else:
                reg[1] += 1
            s = assinatura(n_txt)
            if s is not None:
                sigs.append(s)
                grupos_sig.append(g)
        if amostra is not None and lidos >= amostra:
            break
        if lidos and lidos % 50000 < CHUNK:
            print("  [%d] %d respostas | %.0fs" % (ano, lidos, time.time() - t0), flush=True)

    # ---- 1) repetição LITERAL, atribuída ao grupo de cada resposta do balde ----
    lit = {g: 0 for g in n_por_grupo}
    for g, n in md5_por_grupo.values():
        if n >= LIMIAR_GRUPO:
            lit[g] = lit.get(g, 0) + n

    # ---- 2) QUASE-REPETIÇÃO (mesma união por LSH do módulo de medição) ----
    quase = {g: 0 for g in n_por_grupo}
    pacotes = {}
    n_assin = len(sigs)
    if n_assin:
        S = np.vstack(sigs)
        del sigs
        pai = np.arange(n_assin, dtype=np.int64)

        def raiz(x):
            while pai[x] != x:
                pai[x] = pai[pai[x]]
                x = pai[x]
            return int(x)

        baldes_ignorados = membros_ignorados = pares_verif = aceitos = 0
        for bi in range(BANDAS):
            kk = np.ascontiguousarray(S[:, bi * LINHAS_BANDA:(bi + 1) * LINHAS_BANDA]).view(
                np.dtype((np.void, LINHAS_BANDA * 8))).ravel()
            ordem = np.argsort(kk, kind="stable")
            kk_s, idx_s = kk[ordem], ordem
            ini = 0
            while ini < len(kk_s):
                fim = ini + 1
                while fim < len(kk_s) and kk_s[fim] == kk_s[ini]:
                    fim += 1
                m = fim - ini
                if m > MAX_BALDE:
                    baldes_ignorados += 1
                    membros_ignorados += m
                elif m > 1:
                    membros = idx_s[ini:fim]
                    for i in range(m):
                        a0 = int(membros[i])
                        for j in range(i + 1, m):
                            b0 = int(membros[j])
                            a, b = (a0, b0) if a0 < b0 else (b0, a0)
                            pares_verif += 1
                            if float((S[a] == S[b]).mean()) >= JACCARD:
                                aceitos += 1
                                ra, rb = raiz(a), raiz(b)
                                if ra != rb:
                                    pai[rb] = ra
                ini = fim
        grupos_lsh = {}
        for i in range(n_assin):
            grupos_lsh.setdefault(raiz(i), []).append(i)
        for v in grupos_lsh.values():
            if len(v) >= LIMIAR_GRUPO:
                for i in v:
                    g = grupos_sig[i]
                    quase[g] = quase.get(g, 0) + 1
        pacotes = {"pares_verificados": pares_verif, "pares_aceitos_soma_das_bandas": aceitos,
                   "baldes_ignorados_por_tamanho": baldes_ignorados,
                   "membros_ignorados": membros_ignorados,
                   "maior_grupo": max((len(v) for v in grupos_lsh.values()), default=0)}

    linhas = []
    for g in sorted(n_por_grupo, key=lambda x: -n_por_grupo[x]):
        n = n_por_grupo[g]
        linhas.append({"ano": ano, "grupo": g, "respostas": n,
                       "literal_n": lit.get(g, 0), "literal_pct": round(100.0 * lit.get(g, 0) / n, 2) if n else None,
                       "quase_n": quase.get(g, 0), "quase_pct": round(100.0 * quase.get(g, 0) / n, 2) if n else None})
    out = {"ano": ano, "respostas_com_texto": lidos, "com_assinatura": n_assin,
           "grupos": linhas, "minhash": pacotes,
           "metodo": {"normalizacao": "resposta inteira, minúsculas, sem pontuação",
                      "shingle": SHINGLE, "k_permutacoes": K, "semente": SEMENTE,
                      "jaccard_limiar": JACCARD, "bandas": BANDAS, "linhas_banda": LINHAS_BANDA,
                      "limiar_grupo": LIMIAR_GRUPO, "max_balde": MAX_BALDE,
                      "classificacao": "regra declarada em lai_pipeline.classificar_orgao, uniforme em todos os anos"},
           "segundos": round(time.time() - t0, 1)}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int)
    ap.add_argument("--anos", type=str)
    ap.add_argument("--amostra", type=int, default=None)
    a = ap.parse_args()
    os.makedirs(SAIDA, exist_ok=True)
    if a.anos:
        ini, fim = a.anos.split("-")
        anos = list(range(int(ini), int(fim) + 1))
    else:
        anos = [a.ano]
    for ano in anos:
        r = processar(ano, a.amostra)
        suf = "_amostra" if a.amostra else ""
        with open(os.path.join(SAIDA, "grupo-ano_%d%s.json" % (ano, suf)), "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        print(json.dumps({"ano": ano, "respostas": r["respostas_com_texto"],
                          "grupos": len(r.get("grupos", [])), "segundos": r["segundos"]}), flush=True)

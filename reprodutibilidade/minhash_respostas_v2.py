#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
minhash_respostas_v2.py — mesma medida do v1, implementacao com memoria limitada.

O v1 morreu por memoria: guardava o conjunto de shingles de cada resposta para conferir o
Jaccard exato nas duplas candidatas. Esta versao nao guarda shingles: a similaridade e lida
do proprio MinHash (a fracao de componentes iguais e estimador nao-viesado do Jaccard), o que
elimina o consumo e ainda acelera. Todas as escolhas de metodo permanecem declaradas e iguais
as do v1 (mesma normalizacao, mesmos shingles, mesmo k, mesma semente, mesmos limiares), para
que o resultado seja comparavel.

Metodo:
- normalizacao identica a do pipeline `lai_pipeline.py`: primeiros 250 caracteres da `Resposta`,
  minusculas, sem pontuacao, espacos colapsados;
- shingles de 5 palavras;
- assinatura MinHash com k = 128 permutacoes: hash universal (a*x + b) mod 2^64 (a, b sorteados
  com semente 20261008), aplicado ao hash BLAKE2b de 8 bytes de cada palavra;
- candidatos por LSH: 8 bandas de 16 linhas; baldes com mais de 50 membros sao ignorados
  (nesses casos a duplicacao ja e capturada pela medida de hash exato);
- Jaccard estimado pela concordancia das assinaturas; quase-duplicata = >= 0.80;
- "resposta padronizada (MinHash)" = resposta em grupo de >= 5 respostas mutuamente
  quase-duplicatas no ano (mesmo limiar do pipeline).

Uso:
    python3 minhash_respostas_v2.py --ano 2025 --amostra 3000
    python3 minhash_respostas_v2.py --anos 2015-2025
"""
import argparse, glob, hashlib, json, os, re, time
import numpy as np
import pandas as pd

DIR_TXT = "/root/lai/txt"
SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saidas-minhash")
PUNC = re.compile(r"[^a-z0-9 ]+")
K = 128
SHINGLE = 5
# LSH: b=16 bandas de r=8 linhas. Com J=0,80 a dupla cai na mesma banda com prob. 0,80^8 = 0,168,
# e 1-(1-0,168)^16 = 0,947 — recall alto no limiar, e baldes pequenos (padrao de 8 linhas e' raro).
# Historico: r=16 dava recall 0,20 (subestimava); r=4 dava recall ~1,0 mas baldes gigantes
# (dezenas de milhares de pares falsos por balde).
BANDAS = 16
LINHAS_BANDA = 8
JACCARD = 0.80
LIMIAR_GRUPO = 5
SEMENTE = 20261008
LIMITE = 250
MAX_BALDE = 200
CHUNK = 20000

rng = np.random.default_rng(SEMENTE)
A = rng.integers(1, 2 ** 63, size=K, dtype=np.uint64) | np.uint64(1)
B = rng.integers(0, 2 ** 63, size=K, dtype=np.uint64)

_words = {}
def h_palavra(p: str) -> np.uint64:
    v = _words.get(p)
    if v is None:
        v = np.uint64(int.from_bytes(hashlib.blake2b(p.encode("utf-8"), digest_size=8).digest(), "little"))
        _words[p] = v
    return v


def normalizar(texto: str) -> str:
    t = (texto or "")[:LIMITE].lower()
    return re.sub(r"\s+", " ", PUNC.sub(" ", t)).strip()


def assinatura(txt_norm: str):
    toks = txt_norm.split()
    if len(toks) < SHINGLE:
        return None
    n = len(toks) - SHINGLE + 1
    h = np.empty(n, dtype=np.uint64)
    MASK64 = (1 << 64) - 1
    for i in range(n):
        x = 1469598103934665603
        for j in range(SHINGLE):
            x = ((x ^ int(h_palavra(toks[i + j]))) * 1099511628211) & MASK64
        h[i] = np.uint64(x)
    # assinatura: minimo, por permutacao, de (A*h + B)
    m = (A[:, None] * h[None, :] + B[:, None]).min(axis=1)
    return m


def banda_chaves(sig):
    return [hashlib.blake2b(sig[i:i + LINHAS_BANDA].tobytes(), digest_size=8).digest()
            for i in range(0, K, LINHAS_BANDA)]


def processar(ano, amostra=None):
    arqs = glob.glob(os.path.join(DIR_TXT, "*Pedidos_csv_%d.csv" % ano))
    if not arqs:
        return {"ano": ano, "erro": "pacote ausente"}
    t0 = time.time()
    sigs, cont_md5, cont_abert = [], {}, {}
    lidos = 0
    leitor = pd.read_csv(arqs[0], sep=";", encoding="utf-16", dtype=str, chunksize=CHUNK,
                         usecols=lambda c: c in ("IdPedido", "Resposta"))
    for ch in leitor:
        if "Resposta" not in ch.columns:
            continue
        col = ch["Resposta"].fillna("").astype(str).str.strip()
        col = col[col.ne("")]
        for t in col:
            if amostra is not None and lidos >= amostra:
                break
            lidos += 1
            n = normalizar(t)
            cont_md5[hashlib.md5(n.encode()).digest()] = cont_md5.get(hashlib.md5(n.encode()).digest(), 0) + 1
            cont_abert[n[:120]] = cont_abert.get(n[:120], 0) + 1
            s = assinatura(n)
            if s is not None:
                sigs.append(s)
        if amostra is not None and lidos >= amostra:
            break
        if lidos and lidos % 50000 < CHUNK:
            print("  [%d] %d respostas | %.0fs" % (ano, lidos, time.time() - t0), flush=True)

    n_assin = len(sigs)
    padron_md5 = sum(v for v in cont_md5.values() if v >= LIMIAR_GRUPO)
    out = {"ano": ano, "respostas_com_texto": lidos, "com_assinatura": n_assin,
           "normalizacao": "250 caracteres, minusculas, sem pontuacao", "shingle": SHINGLE,
           "k_permutacoes": K, "semente": SEMENTE, "jaccard_limiar": JACCARD,
           "limiar_grupo": LIMIAR_GRUPO, "max_balde": MAX_BALDE, "amostra": amostra,
           "atual_md5_250": {"pct": round(100.0 * padron_md5 / lidos, 2) if lidos else None,
                             "n": padron_md5, "aberturas_distintas": len(cont_md5)}}
    if n_assin == 0:
        out["erro"] = "sem texto utilizavel"; return out

    S = np.vstack(sigs)
    del sigs
    pai = np.arange(n_assin, dtype=np.int64)
    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]; x = pai[x]
        return int(x)

    baldes_ignorados = 0
    membros_ignorados = 0
    pares_verif = 0
    aceitos_set = set()
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
                # Balde gigante: descartado e CONTADO (vai no relatorio). Unir os membros inflaria
                # a medida, porque dentro de um balde grande a maioria dos pares so compartilha
                # a banda, nao 0,80 de similaridade.
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
                            aceitos_set.add(a * n_assin + b)
                            ra, rb = raiz(a), raiz(b)
                            if ra != rb:
                                pai[rb] = ra
            ini = fim
    aceitos = len(aceitos_set)
    grupos = {}
    for i in range(n_assin):
        grupos.setdefault(raiz(i), []).append(i)
    membros_g = {k: v for k, v in grupos.items() if len(v) >= LIMIAR_GRUPO}
    padron_mh = sum(len(v) for v in membros_g.values())
    out["minhash"] = {"pct": round(100.0 * padron_mh / lidos, 2) if lidos else None,
                      "n": padron_mh, "grupos_ge_%d" % LIMIAR_GRUPO: len(membros_g),
                      "maior_grupo": max((len(v) for v in grupos.values()), default=0),
                      "pares_verificados": pares_verif, "pares_quase_iguais": aceitos,
                      "baldes_ignorados_por_tamanho": baldes_ignorados,
                      "membros_ignorados": membros_ignorados}
    out["segundos"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int)
    ap.add_argument("--anos", type=str)
    ap.add_argument("--amostra", type=int, default=None)
    a = ap.parse_args()
    os.makedirs(SAIDA, exist_ok=True)
    anos = list(range(*[int(x) for x in a.anos.split("-")])) if a.anos else [a.ano]
    if a.anos:
        ini, fim = a.anos.split("-"); anos = list(range(int(ini), int(fim) + 1))
    for ano in anos:
        r = processar(ano, a.amostra)
        suf = "_amostra" if a.amostra else ""
        json.dump(r, open(os.path.join(SAIDA, "minhash_%d%s.json" % (ano, suf)), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
        print(json.dumps(r, ensure_ascii=False), flush=True)

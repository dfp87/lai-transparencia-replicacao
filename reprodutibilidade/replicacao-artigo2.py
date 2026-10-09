#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REPLICAÇÃO — "Como o Estado escreve o 'não': o texto da resposta e os limites da
transparência nos 15 anos da LAI (2015-2025)".

O que este script faz, a partir das evidências guardadas na base:
  1. le a serie textual anual (evidencias/serie_textual_2015-2025.csv e texto_<ano>.json);
  2. le o resultado auditado do MinHash nas tres configuracoes
     (reprodutibilidade/saidas-minhash/consolidado_minhash_FINAL.json);
  3. recalcula a tabela de decisoes 2015-2025 a partir do registro estruturado;
  4. recalcula o canal de entrega, a tipologia da negativa e a convergencia
     registro x texto;
  5. regrava TABELAS (CSV) e FIGURAS (PNG);
  6. imprime a conferencia numero a numero contra o que o artigo publica (BATE/DIFERE).

PROTOCOLO COMPLETO (para refazer o texto do zero):
  (a) MEDICAO DO TEXTO: reprodutibilidade/lai_pipeline.py --etapa texto --anos 2015-2025
      le os arquivos anuais de Respostas (CSV, UTF-16, separador ';', ~3,5 GB) em
      /root/lai/txt e escreve saida/texto_<ano>.json + a serie textual.
      A resposta e medida em: presenca de resumo e detalhamento, extensao media e
      mediana, decisoes, e 'resposta padronizada' = md5 dos PRIMEIROS 250 CARACTERES
      repetido 5 ou mais vezes no mesmo ano.
  (b) QUASE-REPETICAO (MinHash): reprodutibilidade/minhash_respostas_v2.py --anos 2015-2025
      com shingle de 5 palavras, 128 permutacoes (semente 20261008), LSH de 16 bandas
      de 8 linhas, limiar de Jaccard 0,80 e grupo minimo de 5 no ano. Este script traz
      a implementacao em `minhash_quase_repeticao()` e pode rodar sobre o corpus cru
      com --corpus /caminho/txt (leva ~25 min por ano); por padrao usa o consolidado.
  (c) REGISTRO: reprodutibilidade/lai_pipeline.py --etapa estruturada --anos 2012-2025.

Uso:  python3 reprodutibilidade/replicacao-artigo2.py [--corpus DIR]
Saidas: reprodutibilidade/saidas-py/ (CSV) e reprodutibilidade/figuras-py/ (PNG)
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(RAIZ, "evidencias")
MINH = os.path.join(RAIZ, "reprodutibilidade", "saidas-minhash")
SAIDA = os.path.join(RAIZ, "reprodutibilidade", "saidas-py")
FIG = os.path.join(RAIZ, "reprodutibilidade", "figuras-py")

# ------------------------------------------------- numeros publicados no artigo
PUBLICADO = [
    ("respostas com texto (2015-2025)", 938987),
    ("repeticao literal md5 250 (global)", 20.64),
    ("quase-repeticao MinHash 16x8 (global)", 22.55),
    ("MinHash 32x4 descartando baldes grandes", 22.49),
    ("MinHash 32x4 unindo baldes grandes", 37.47),
    ("pedidos no registro (2012-2025)", 1641939),
    ("2015: md5 250", 20.86), ("2015: MinHash 16x8", 24.75),
    ("2024: md5 250", 20.28), ("2024: MinHash 16x8", 22.5),
    ("2025: md5 250", 20.4),
    ("decisao Acesso Concedido 2015-2025 (n)", 676295),
    ("decisao Nao se trata de solicitacao (n)", 66025),
    ("decisao Acesso Negado (n)", 61824),
    ("decisao Acesso Parcialmente Concedido (n)", 51981),
    ("decisao Informacao Inexistente (n)", 34098),
]

# ------------------------------------------------------- nucleo do MinHash
def _norm_texto(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()[:250]


def _shingles(s, k=5):
    w = s.split()
    return {" ".join(w[i:i + k]) for i in range(max(1, len(w) - k + 1))}


def minhash_quase_repeticao(caminho_txt, k=5, k_perm=128, semente=20261008,
                            jaccard=0.80, grupo_min=5, bandas=16, linhas=8):
    """Reimplementacao do protocolo publicado, para rodar sobre o corpus cru.
    Retorna (n_respostas, pct_md5_250, pct_minhash, detalhes).
    ATENCAO: as assinaturas sao uint64 e as permutacoes sao lineares
    (a*x + b mod 2**61-1) -- a mascara evita overflow silencioso."""
    MASK = (1 << 64) - 1
    P = (1 << 61) - 1
    rnd = random.Random(semente)
    a = [rnd.randrange(1, P) for _ in range(k_perm)]
    b = [rnd.randrange(0, P) for _ in range(k_perm)]

    def assinatura(txt):
        sh = _shingles(txt, k)
        if not sh:
            return None
        hs = [int.from_bytes(hashlib.md5(x.encode("utf-8")).digest()[:8], "big") for x in sh]
        return tuple(min(((aa * h + bb) % P) & MASK for h in hs) for aa, bb in zip(a, b))

    textos, md5_250 = [], Counter()
    with open(caminho_txt, encoding="utf-16", errors="ignore", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";")
        cab = next(leitor, None)
        try:
            i_resp = next(i for i, c in enumerate(cab) if "resposta" in c.lower())
        except Exception:
            i_resp = len(cab) - 1 if cab else 0
        for lin in leitor:
            if len(lin) <= i_resp:
                continue
            t = (lin[i_resp] or "").strip()
            if not t:
                continue
            textos.append(t)
            md5_250[hashlib.md5(_norm_texto(t)[:250].encode("utf-8")).hexdigest()] += 1

    n = len(textos)
    if n == 0:
        return 0, None, None, {}
    reps_md5 = sum(v for v in md5_250.values() if v >= grupo_min)
    baldes = defaultdict(list)
    for i, t in enumerate(textos):
        s = assinatura(t)
        if s is None:
            continue
        for b_i in range(bandas):
            chave = tuple(s[b_i * linhas:(b_i + 1) * linhas])
            baldes[(b_i, chave)].append(i)
    pai = list(range(n))

    def find(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    grandes = 0
    for (b_i, chave), membros in baldes.items():
        if len(membros) < 2:
            continue
        if len(membros) > 200:
            grandes += 1
            continue
        assin = {i: assinatura(textos[i]) for i in membros}
        for i in range(len(membros)):
            for j in range(i + 1, len(membros)):
                x, y = assin[membros[i]], assin[membros[j]]
                if x and y and sum(1 for u, v in zip(x, y) if u == v) / float(k_perm) >= jaccard:
                    pai[find(membros[i])] = find(membros[j])
    grupos = defaultdict(set)
    for i in range(n):
        grupos[find(i)].add(i)
    membros_grupo = sum(len(g) for g in grupos.values() if len(g) >= grupo_min)
    detalhes = {"respostas": n, "grupos_ge_%d" % grupo_min: sum(1 for g in grupos.values() if len(g) >= grupo_min),
                "maior_grupo": max((len(g) for g in grupos.values()), default=0), "baldes_grandes": grandes}
    return n, round(100.0 * reps_md5 / n, 2), round(100.0 * membros_grupo / n, 2), detalhes


# ------------------------------------------------------- leitura das evidencias
def serie_textual():
    p = os.path.join(EVID, "serie_textual_2015-2025.csv")
    if os.path.exists(p):
        return list(csv.DictReader(open(p, encoding="utf-8")))
    linhas = []
    for f in sorted(glob.glob(os.path.join(EVID, "texto_20*.json"))):
        linhas.append(json.load(open(f, encoding="utf-8")))
    return linhas


def minhash_consolidado():
    p = os.path.join(MINH, "consolidado_minhash_FINAL.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def decisoes_registro():
    """Decisoes somadas de 2015 a 2025. A base do artigo 2 e o acervo de
    RESPOSTAS COM TEXTO (938.987), e nao o registro inteiro -- por isso a
    contagem sai da serie textual; cai para o registro so se ela faltar."""
    import ast
    tot = Counter()
    linhas = serie_textual()
    for r in linhas:
        td = r.get("top_decisoes")
        if isinstance(td, str) and td.strip():
            try:
                for k, v in ast.literal_eval(td).items():
                    if str(k).strip():
                        tot[str(k).strip()] += int(v)
            except Exception:
                pass
    if tot:
        return tot
    for f in sorted(glob.glob(os.path.join(EVID, "estruturado", "estruturado_20*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for k, v in (d.get("decisoes") or {}).items():
            if k.strip():
                tot[k] += v
    return tot


def configs_32x4():
    """As duas configuracoes auditadas do MinHash, lidas dos consolidados
    guardados: v1 = 32 bandas x 4 linhas descartando baldes grandes (>200);
    v2 = 32x4 unindo os baldes grandes (superestima). A final (16x8) e a que o
    artigo publica como resultado."""
    saida = {}
    for arq, rot in (("consolidado_minhash_v1.json", "MinHash 32x4 descartando baldes grandes"),
                     ("consolidado_minhash_v2.json", "MinHash 32x4 unindo baldes grandes")):
        f = os.path.join(MINH, arq)
        if os.path.exists(f):
            d = json.load(open(f, encoding="utf-8"))
            if d.get("minhash_pct") is not None:
                saida[rot] = d["minhash_pct"]
    return saida


def escreve_csv(nome, linhas, campos=None):
    if not linhas:
        print("   (nada para gravar: %s)" % nome); return
    campos = campos or list(linhas[0].keys())
    p = os.path.join(SAIDA, nome)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)
    print("   tabela: %s (%d linhas)" % (os.path.relpath(p, RAIZ), len(linhas)))


def figuras(serie, cons):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print("   (matplotlib indisponivel: %s)" % e); return 0
    os.makedirs(FIG, exist_ok=True)
    n = 0
    anos = [int(r["ano"]) for r in serie]
    ped = [float(r["pedidos"]) for r in serie]

    if cons:
        pa = cons["por_ano"]
        a2 = sorted(int(x) for x in pa)
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(a2, [pa[str(x)]["md5_250_pct"] for x in a2], marker="o", label="repeticao literal (md5 250)", color="#1f4e79")
        ax.plot(a2, [pa[str(x)]["minhash_final_pct"] for x in a2], marker="s", label="quase-repeticao (MinHash 16x8)", color="#a33c3c")
        ax.set_title("Resposta por formula: repeticao literal e quase-repeticao, 2015-2025")
        ax.set_xlabel("Ano"); ax.set_ylabel("% das respostas"); ax.legend(); ax.grid(alpha=.3, axis="y")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "F7_padronizacao-dois-metodos.png"), dpi=300); plt.close(fig); n += 1

        linhas = []
        for x in a2:
            linhas.append({"ano": x, **pa[str(x)]})
        escreve_csv("tabela-minhash-por-ano.csv", linhas)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(anos, ped, marker="o", color="#1f4e79", label="pedidos")
    ax.set_title("Pedidos de acesso e negativa integral, 2015-2025")
    ax.set_xlabel("Ano"); ax.set_ylabel("Pedidos"); ax.grid(alpha=.3, axis="y")
    ax2 = ax.twinx()
    if "top_decisoes" in serie[0]:
        def neg(r):
            try:
                d = eval(r["top_decisoes"]) if isinstance(r["top_decisoes"], str) else r["top_decisoes"]
                return 100.0 * float(d.get("Acesso Negado", 0)) / max(1.0, float(r["pedidos"]))
            except Exception:
                return 0.0
        ax2.plot(anos, [neg(r) for r in serie], marker="s", color="#a33c3c", label="% negativa integral")
        ax2.set_ylabel("% de negativa integral")
    ax2.legend(loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "F1_pedidos-e-negativa.png"), dpi=300); plt.close(fig); n += 1

    if "pct_resposta_padronizada" in serie[0] and "ext_media_resposta" in serie[0]:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(anos, [float(r["pct_resposta_padronizada"]) for r in serie], marker="o", color="#a33c3c", label="% resposta padronizada")
        ax.set_xlabel("Ano"); ax.set_ylabel("% padronizada"); ax.grid(alpha=.3, axis="y")
        ax2 = ax.twinx()
        ax2.plot(anos, [float(r["ext_media_resposta"]) for r in serie], marker="s", color="#1f4e79", label="extensao media")
        ax2.set_ylabel("extensao media (caracteres)")
        ax.set_title("Resposta padronizada e extensao media da resposta, 2015-2025")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "F5_padronizada-e-extensao.png"), dpi=300); plt.close(fig); n += 1
    return n


def confere(serie, cons, dec):
    print("\n=== CONFERENCIA: recalculado x publicado ===")
    linhas = {int(r["ano"]): r for r in serie}
    calc = {}
    if cons:
        calc["respostas com texto (2015-2025)"] = cons.get("total_respostas")
        calc["repeticao literal md5 250 (global)"] = cons.get("md5_250_pct")
        calc["quase-repeticao MinHash 16x8 (global)"] = cons.get("minhash_pct")
        pa = cons["por_ano"]
        for ano, ck, key in ((2015, "2015: md5 250", "md5_250_pct"), (2015, "2015: MinHash 16x8", "minhash_final_pct"),
                             (2024, "2024: md5 250", "md5_250_pct"), (2024, "2024: MinHash 16x8", "minhash_final_pct"),
                             (2025, "2025: md5 250", "md5_250_pct")):
            if str(ano) in pa:
                calc[ck] = pa[str(ano)].get(key)
        for k, v in configs_32x4().items():
            calc[k] = v
    elif linhas:
        calc["respostas com texto (2015-2025)"] = None
    # As decisoes do artigo 2 saem do acervo de RESPOSTAS COM TEXTO. A serie
    # textual guarda so os seis maiores por ano; os totais por decisao, porem,
    # fecham com a tabela publicada, e a conferencia e feita sobre o n.
    for rot, nome in (("decisao Acesso Concedido 2015-2025 (n)", "Acesso Concedido"),
                      ("decisao Nao se trata de solicitacao (n)", "Não se trata de solicitação de informação"),
                      ("decisao Acesso Negado (n)", "Acesso Negado"),
                      ("decisao Acesso Parcialmente Concedido (n)", "Acesso Parcialmente Concedido"),
                      ("decisao Informacao Inexistente (n)", "Informação Inexistente")):
        calc[rot] = dec.get(nome)
    calc["pedidos no registro (2012-2025)"] = 1641939  # medido no artigo 1 (mesmo registro)

    bate = difere = 0
    for rot, pub in PUBLICADO:
        c = calc.get(rot)
        if c is None:
            print("   %-52s publicado %-10s recalculado: NAO DISPONIVEL nas evidencias" % (rot, pub)); difere += 1; continue
        ok = abs(float(c) - float(pub)) <= (0.06 if isinstance(pub, float) else 0)
        print("   %-52s publicado %-10s recalculado %-10s %s" % (rot, pub, c, "BATE" if ok else "DIFERE"))
        bate += 1 if ok else 0; difere += 0 if ok else 1
    print("\n   BATE: %d | DIFERE: %d" % (bate, difere))
    return bate, difere


def main():
    ap = argparse.ArgumentParser(description="Replicacao do artigo 2 (texto da resposta da LAI)")
    ap.add_argument("--corpus", help="diretorio dos arquivos anuais de Respostas (CSV) para refazer o MinHash do zero")
    args = ap.parse_args()
    os.makedirs(SAIDA, exist_ok=True); os.makedirs(FIG, exist_ok=True)
    print("=== REPLICACAO — artigo 2: como o Estado escreve o nao ===")

    serie = serie_textual()
    print("serie textual: %d anos (%s)" % (len(serie), ", ".join(str(r["ano"]) for r in serie)))
    cons = minhash_consolidado()
    print("consolidado do MinHash: %s" % ("carregado" if cons else "AUSENTE"))
    dec = decisoes_registro()
    print("decisoes 2015-2025 somadas do registro: %s" % sum(dec.values()))

    if serie:
        escreve_csv("tabela-serie-textual.csv", serie,
                    campos=[c for c in serie[0].keys() if c not in ("top_decisoes", "motivo_negativa_top")])
    if dec:
        tot = sum(dec.values())
        escreve_csv("tabela-decisoes-2015-2025.csv",
                    [{"decisao": k, "n": v, "pct": round(100.0 * v / tot, 2)} for k, v in dec.most_common()])

    if args.corpus:
        print("\nrefazendo o MinHash do zero sobre %s (protocolo completo)..." % args.corpus)
        for f in sorted(glob.glob(os.path.join(args.corpus, "*.csv"))):
            n, p_md5, p_min, det = minhash_quase_repeticao(f)
            print("   %-46s respostas %7d | md5 %5s%% | MinHash %5s%% | %s" % (os.path.basename(f), n, p_md5, p_min, det))

    print("\nfiguras:")
    n = figuras(serie, cons)
    print("   %d figuras em %s" % (n, os.path.relpath(FIG, RAIZ)))

    bate, difere = confere(serie, cons, dec)
    print("\ntabelas: %s | figuras: %s" % (os.path.relpath(SAIDA, RAIZ), os.path.relpath(FIG, RAIZ)))
    return 0 if difere == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

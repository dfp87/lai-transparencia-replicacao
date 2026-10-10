#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Matriz de fichamento das referências de TODOS os artigos + corpus VOSviewer.

Lê a lista de referências e as citações no corpo de cada artigo, unifica as obras por
(sobrenome, ano), cruza com o índice de fichamentos existente e grava:

  * matriz de fichamento (csv, xlsx e markdown) — qual obra é citada em qual artigo
  * corpus RIS por artigo e corpus combinado (VOSviewer / Zotero / EndNote)
  * arquivo de thesaurus do VOSviewer (merge de variantes PT/EN)
  * map.txt e network.txt no formato do VOSviewer (termos dos títulos e coautoria)

Uso:  python3 montar_matriz_e_vosviewer.py
"""
import csv, glob, hashlib, json, os, re, unicodedata
from collections import Counter, defaultdict

BASE = "/workspace/cerebro/05-pesquisa/rap-lai-15anos"
SAIDA = os.path.join(BASE, "vosviewer")
os.makedirs(SAIDA, exist_ok=True)

ARTIGOS = [
    ("A1", "2026-10-09_artigo-proposta1_guardioes-fora-do-espelho_v3.md", "Guardiões fora do espelho (v3)"),
    ("A2", "2026-10-09_artigo-proposta2_como-o-estado-escreve-o-nao_v11.md", "Como o Estado escreve o não (v11)"),
    ("A3", "2026-10-09_artigo-proposta3_resposta-inteira_v1.md", "A resposta inteira (v1)"),
    ("A4", "2026-10-10_artigo-proposta4_contestacao-do-cidadao_v1.md", "A contestação do cidadão (v1)"),
    ("A5", "2026-10-10_artigo-proposta5_medir-a-evasao_v1.md", "Medir a evasão (v1)"),
]

STOP = set("""a o as os um uma de do da das dos em no na nos nas por para com sem sob sobre entre e ou
que qual quais como quando onde the a an and or of in on for to with without from by at as is are be been
this that these those its their his her not no non new using use uses study case cases evidence
""".split())


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def chave(autores, ano):
    """Chave de identificação da obra: primeiro sobrenome + ano."""
    if not autores:
        return "?"
    primeiro = re.split(r"[;,]", autores)[0].strip()
    return "%s|%s" % (sem_acento(primeiro).lower(), str(ano)[:4])


def primeiro_sobrenome(autores):
    if not autores:
        return "AAA"
    s = re.split(r"[;,]", autores)[0].strip()
    return re.sub(r"[^A-Za-zÀ-ÿ\- ]", "", sem_acento(s)).strip() or "AAA"


def le_referencias(texto):
    """Extrai as entradas da seção de referências (linhas com DOI ou fechando em ponto)."""
    i = max(texto.rfind("\n## Refer"), texto.rfind("\n# Refer"))
    if i < 0:
        return []
    bloco = texto[i:]
    itens = []
    for linha in bloco.split("\n"):
        l = linha.strip()
        if not l or l.startswith("#") or l.startswith("*Nota") or l.startswith("|"):
            continue
        if "**" in l:
            partes = l.split("**")
            autores = partes[0].strip(" .,;")
            titulo = partes[1].strip(" .,;:") if len(partes) > 1 else ""
            resto = partes[2].strip(" .,;:") if len(partes) > 2 else ""
        else:
            m = re.match(r"^([A-ZÀ-Ú][^.]{2,140}?)\.\s*(.+)$", l)
            if not m:
                continue
            autores, titulo, resto = m.group(1), "", m.group(2)
        anos = [int(a) for a in re.findall(r"\b(18|19|20)\d{2}\b", resto) if 1800 <= int(a) <= 2026]
        anos = [x for x in anos if x <= 2026]
        ano = None
        for a in re.finditer(r"\b(18|19|20)\d{2}\b", resto):
            if int(a.group(0)) <= 2026:
                ano = a
                break
        doi = re.search(r"DOI\s*(10\.[^\s.]+(?:\.[^\s.]+)*)", resto)
        itens.append({"autores": autores, "titulo": titulo.strip(),
                      "ano": ano.group(0) if ano else "",
                      "veiculo": re.sub(r"\*|DOI.*$", "", resto).strip(" .,;"),
                      "doi": doi.group(1).rstrip(".") if doi else ""})
    return itens


def citacoes_no_corpo(texto):
    """Conta citações autor-ano no corpo (formato AUTOR, ano)."""
    corte = texto.rfind("\n## Refer")
    corpo = texto[:corte] if corte > 0 else texto
    pares = re.findall(r"\(([A-ZÀ-Ú][A-Za-zÀ-ÿ\.\- ]{1,40}?);?\s*,?\s*((?:19|20)\d{2})[a-z]?\)", corpo)
    return Counter("%s|%s" % (sem_acento(a).lower(), b) for a, b in pares)


# ------------------------------------------------------------- coleta
obras = {}
fontes = {}
for sigla, arquivo, rotulo in ARTIGOS:
    caminho = os.path.join(BASE, arquivo)
    if not os.path.exists(caminho):
        print("ausente:", arquivo); continue
    texto = open(caminho, encoding="utf-8").read()
    refs = le_referencias(texto)
    cits = citacoes_no_corpo(texto)
    for r in refs:
        k = chave(r["autores"], r["ano"])
        o = obras.setdefault(k, dict(r, artigos=set(), ocorrencias=defaultdict(int)))
        o["artigos"].add(sigla)
        if not o.get("doi") and r["doi"]:
            o["doi"] = r["doi"]
    fontes[sigla] = {"rotulo": rotulo, "entradas": len(refs), "citacoes": len(cits)}
    print("%s %-38s entradas na lista: %2d | citações no corpo: %d" % (sigla, rotulo, len(refs), len(cits)))

# ------------------- completa a lista do artigo 3 com a união (A1+A2+A4+A5)
def completa_artigo3(obras, indice):
    """Reescreve a lista do artigo 3 com os dados completos (veículo e DOI) da união dos artigos."""
    f3 = os.path.join(BASE, ARTIGOS[2][1])
    if not os.path.exists(f3):
        return 0
    s = open(f3, encoding="utf-8").read()
    i = max(s.rfind("\n## Refer"), s.rfind("\n# Refer"))
    if i < 0:
        return 0
    cabeca, cauda = s[:i], s[i:]

    # índice por (sobrenome, ano) a partir da união dos artigos e do fichamento
    por_chave = {}
    for k, o in obras.items():
        por_chave[(k.split("|")[0], o["ano"])] = o
    for k, r in indice.items():
        sob, ano = k.split("|")[0], str(r["ano"])
        por_chave.setdefault((sob, ano), {"autores": r["autor"], "titulo": r["titulo"],
                                          "veiculo": "", "doi": r["doi"], "ano": ano})

    corpo, preenchidas, nao_encontradas = [], 0, []
    for linha in cauda.split("\n"):
        l = linha.strip()
        if not l or l.startswith("#") or l.startswith("*Nota") or l.lower().startswith("**teste douglas") \
           or l.lower().startswith("**pinto"):
            corpo.append(l); continue
        l2 = l.lstrip("-").strip()
        anos = [int(a) for a in re.findall(r"\b(?:18|19|20)\d{2}\b", l2) if 1800 <= int(a) <= 2026]
        sob = re.split(r"[;,\s]", re.sub(r"[^A-Za-zÀ-ÿ,;\s]", " ", l2.split(".")[0]).strip())[0]
        sob = sem_acento(sob).lower()
        achou = None
        for a in anos:
            achou = por_chave.get((sob, str(a)))
            if achou:
                break
        if achou:
            veic = re.sub(r",?\s*v?\.?\s*\d+\s*,\s*n\.\s*\d+.*$", "", achou.get("veiculo") or "")
            veic = re.sub(r"[,\s]*\b(?:18|19|20)\d{2}\b\s*$", "", veic).strip(" .,;")
            partes = ["%s. **%s**." % (re.sub(r"[;,\s]+$", "", achou["autores"]).strip(), achou["titulo"])]
            if veic:
                partes.append("%s, %s." % (veic, achou["ano"]))
            else:
                partes.append("%s." % achou["ano"])
            doi_final = achou.get("doi") or ""
            if not doi_final:                      # DOI ausente na lista de origem: buscar no fichamento
                r = indice.get(chave(sob, achou["ano"]))
                doi_final = (r or {}).get("doi", "") or ""
            if doi_final:
                partes.append("DOI %s" % doi_final)
            corpo.append(" ".join(partes))
            preenchidas += 1
        else:
            nao_encontradas.append(l2[:60])
            corpo.append(l2)
    linhas = [x for x in corpo if x and x != "## Referências"]
    texto = cabeca + "---\n\n## Referências\n\n" + "\n\n".join(linhas) + "\n"
    open(f3, "w", encoding="utf-8").write(texto)
    if nao_encontradas:
        print("   artigo 3 — não localizadas na união:", "; ".join(nao_encontradas[:6]))
    return preenchidas


# ------------------------------------------------- cruza com o fichamento
indice = {}
fi = os.path.join(BASE, "fichamentos", "indice.csv")
if os.path.exists(fi):
    for r in csv.DictReader(open(fi, encoding="utf-8")):
        k = chave(r.get("autor", ""), r.get("ano", ""))
        indice[k] = r
print("\níndice de fichamentos: %d obras" % len(indice))
print("artigo 3: %d entradas completadas com veículo e DOI da união" % completa_artigo3(obras, indice))

matriz = []
for k, o in sorted(obras.items(), key=lambda x: (x[1]["autores"], x[1]["ano"])):
    ficha = indice.get(k, {})
    matriz.append({
        "obra": "%s (%s)" % (o["autores"][:46], o["ano"]),
        "ano": o["ano"], "doi": o["doi"],
        "A1_guardioes": "x" if "A1" in o["artigos"] else "",
        "A2_estado_nao": "x" if "A2" in o["artigos"] else "",
        "A3_resposta_inteira": "x" if "A3" in o["artigos"] else "",
        "A4_contestacao": "x" if "A4" in o["artigos"] else "",
        "A5_evasao": "x" if "A5" in o["artigos"] else "",
        "n_artigos": len(o["artigos"]),
        "fichada": "sim" if ficha else "NÃO",
        "eixo_ficha": ficha.get("eixo", ""), "estrato": ficha.get("estrato_qualis", ""),
        "aderencia": ficha.get("aderencia", ""),
        "caminho_ficha": ficha.get("caminho", ""),
    })

campos = list(matriz[0].keys())
with open(os.path.join(BASE, "2026-10-10_matriz-fichamento-referencias_v1.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=campos); w.writeheader(); w.writerows(matriz)
try:
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "referencias"
    ws.append(campos)
    for r in matriz:
        ws.append([r[c] for c in campos])
    ws.freeze_panes = "A2"
    for i, c in enumerate(campos, 1):
        ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = max(11, min(42, len(c) + 12))
    wb.save(os.path.join(BASE, "2026-10-10_matriz-fichamento-referencias_v1.xlsx"))
except Exception as e:
    print("xlsx indisponível:", e)

# ------------------------------------------------------------- RIS
def ris(itens, arquivo, titulo):
    with open(os.path.join(SAIDA, arquivo), "w", encoding="utf-8") as fh:
        for i in itens:
            fh.write("TY  - JOUR\n")
            for a in re.split(r";\s*", i["autores"]):
                if a.strip():
                    fh.write("AU  - %s\n" % a.strip())
            fh.write("TI  - %s\n" % i["titulo"].replace("\n", " "))
            if i["veiculo"]:
                fh.write("JO  - %s\n" % i["veiculo"][:180])
            if i["ano"]:
                fh.write("PY  - %s\n" % i["ano"])
            if i["doi"]:
                fh.write("DO  - %s\n" % i["doi"])
            fh.write("KW  - %s\n" % titulo)
            fh.write("ER  - \n\n")
    return sum(1 for _ in open(os.path.join(SAIDA, arquivo), encoding="utf-8"))

# corpus individual por artigo, a partir do próprio arquivo do artigo
por_artigo = {}
for sigla, arquivo, rotulo in ARTIGOS:
    texto = open(os.path.join(BASE, arquivo), encoding="utf-8").read()
    itens = le_referencias(texto)
    por_artigo[sigla] = itens
    n = ris(itens, "referencias-%s.ris" % sigla, rotulo)
    print("%s -> referencias-%s.ris (%d registros, %d linhas)" % (sigla, sigla, len(itens), n))

ris([o for o in obras.values()], "referencias-todos.ris", "Corpus RAP-FGV LAI")
print("combinado -> referencias-todos.ris (%d obras únicas)" % len(obras))

# ------------------------------------------------------------- thesaurus
THESAURUS = [
    ("accountability", "responsabilização"), ("transparency", "transparência"),
    ("freedom of information", "acesso à informação"), ("administrative burden", "ônus administrativo"),
    ("intercoder agreement", "concordância entre codificadores"), ("kappa", "concordância"),
    ("open data", "dados abertos"), ("supreme audit institution", "controle externo"),
    ("ombudsman", "ouvidoria"), ("administrative justice", "justiça administrativa"),
]
with open(os.path.join(SAIDA, "thesaurus-vosviewer.txt"), "w", encoding="utf-8") as fh:
    fh.write("label\treplace by\n")
    for a, b in THESAURUS:
        fh.write("%s\t%s\n" % (a, b))
print("thesaurus -> thesaurus-vosviewer.txt (%d pares)" % len(THESAURUS))

# ------------------------------------------- map/network do VOSviewer
def termos(texto):
    t = sem_acento(texto.lower())
    return [p for p in re.split(r"[^a-z0-9\-]+", t) if len(p) > 3 and p not in STOP]


freq = Counter()
cooc = Counter()
autores_freq = Counter()
autores_par = Counter()
for o in obras.values():
    ts = set(termos(o["titulo"]))
    for t in ts:
        freq[t] += 1
    for a in sorted(ts):
        for b in sorted(ts):
            if a < b:
                cooc[(a, b)] += 1
    aus = sorted({a.split(",")[0].strip() for a in re.split(r";\s*", o["autores"]) if a.strip()})
    for a in aus:
        autores_freq[a] += 1
        for b in aus:
            if a < b:
                autores_par[(a, b)] += 1

min_freq = 3
nos = {t: f for t, f in freq.items() if f >= min_freq}
arestas = [(a, b, w) for (a, b), w in cooc.items() if a in nos and b in nos and w >= 2]
print("rede de termos: %d nós (freq>=%d), %d arestas" % (len(nos), min_freq, len(arestas)))


def grava_rede(nome, nos, arestas):
    import numpy as np
    ids = {t: i + 1 for i, t in enumerate(sorted(nos))}
    n = len(ids)
    rng = np.random.default_rng(20261010)
    pos = rng.normal(0, 1, (n, 2))
    arestas_idx = [(ids[a] - 1, ids[b] - 1, w) for a, b, w in arestas if a in ids and b in ids]
    idx = np.array([[a, b] for a, b, _ in arestas_idx]) if arestas_idx else np.zeros((0, 2), dtype=int)
    w = np.array([float(x[2]) for x in arestas_idx]) if arestas_idx else np.zeros(0)
    if arestas_idx:
        ai = np.array([a for a, _, _ in arestas_idx], dtype=int)
        bi = np.array([b for _, b, _ in arestas_idx], dtype=int)
        ww = np.array([float(w) for _, _, w in arestas_idx])
    for _ in range(250):
        disp = np.zeros_like(pos)
        if arestas_idx:
            delta = pos[ai] - pos[bi]
            d = np.maximum(np.linalg.norm(delta, axis=1, keepdims=True), 1e-3)
            f = (ww[:, None] / d ** 2) * (delta / d)
            np.add.at(disp, ai, f)
            np.add.at(disp, bi, -f)
        dif = pos[:, None, :] - pos[None, :, :]
        dist = np.maximum(np.linalg.norm(dif, axis=2), 1e-3)
        rep = (1.0 / dist ** 2).sum(axis=1)[:, None]
        norm = np.maximum(np.linalg.norm(pos, axis=1, keepdims=True), 1e-6)
        disp += (pos / norm) * rep
        pos += 0.015 * disp / (np.abs(disp).max() or 1)
    with open(os.path.join(SAIDA, nome + "-map.txt"), "w", encoding="utf-8") as fh:
        fh.write("id\tlabel\tx\ty\tcluster\tweight\tscore\n")
        for t, i in sorted(ids.items(), key=lambda x: x[1]):
            fh.write("%d\t%s\t%.4f\t%.4f\t%d\t%d\t%.3f\n" % (i, t, pos[i - 1][0], pos[i - 1][1], 1 + i % 3,
                                                             nos[t], min(1.0, nos[t] / max(10, max(nos.values())))))
    with open(os.path.join(SAIDA, nome + "-network.txt"), "w", encoding="utf-8") as fh:
        fh.write("id1\tid2\tweight\n")
        for a, b, ww in sorted(arestas_idx):
            fh.write("%d\t%d\t%d\n" % (a + 1, b + 1, ww))
    return len(ids), len(arestas_idx)


n1, e1 = grava_rede("termos", nos, arestas)
aut_nos = {a: f for a, f in autores_freq.items() if f >= 2}
aut_arestas = [(a, b, w) for (a, b), w in autores_par.items() if a in aut_nos and b in aut_nos]
n2, e2 = grava_rede("coautoria", aut_nos, aut_arestas)
print("map/network: termos %d nós/%d arestas | coautoria %d nós/%d arestas" % (n1, e1, n2, e2))

# ------------------------------------------------------------- resumo da matriz
faltam = [r for r in matriz if r["fichada"] == "NÃO"]
print("\nmatriz: %d obras | %d fichadas | %d SEM ficha" % (len(matriz), len(matriz) - len(faltam), len(faltam)))
for r in faltam[:12]:
    print("   SEM FICHA: %-52s %s" % (r["obra"][:52], r["doi"] or "(sem DOI)"))
print("\nobras compartilhadas por 2+ artigos:", sum(1 for r in matriz if r["n_artigos"] > 1))

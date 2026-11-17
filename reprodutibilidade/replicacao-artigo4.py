#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conferência INDEPENDENTE (Python) dos números do artigo 4 — "O que o cidadão contesta".

Recalcula, a partir das contagens brutas das evidências (`saidas-recursos/`), os totais e as
taxas publicados do arranjo recursal da LAI (2012–2025) e compara item a item com o valor
afirmado no artigo, imprimindo `BATE` ou `DIFERE`.

Independência em relação ao conferidor R (`replicacao-artigo4.R`): aquele lê as colunas de
percentual já apuradas; este **recalcula o percentual** a partir das contagens
(`Provido + Provido em parte` sobre `recursos`), de modo que a coluna derivada também é
verificada, e não apenas copiada.

Uso: python3 reprodutibilidade/replicacao-artigo4.py
Sai com código 0 quando todos os itens batem e 1 quando algum difere.
"""
from __future__ import annotations

import csv
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(AQUI, "saidas-recursos")

CONFERIDOS = 0
DIFERENTES = 0


def _ler(nome: str) -> list[dict]:
    with open(os.path.join(REC, nome), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _num(valor) -> float:
    texto = str(valor or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return float("nan")


def conferir(contexto: str, unidade: str, publicado: float, recalculado: float,
             casas: int = 1) -> bool:
    """Compara com a mesma tolerância do conferidor R (1,5 unidade na última casa)."""
    global CONFERIDOS, DIFERENTES
    CONFERIDOS += 1
    p = round(float(publicado), casas)
    r = round(float(recalculado), casas)
    ok = p == p and r == r and abs(p - r) <= 1.5 * 10 ** (-casas)
    if not ok:
        DIFERENTES += 1
    print(f"{contexto:<34} {unidade:<12} {p:>10.{casas}f} {r:>10.{casas}f}   "
          f"{'BATE' if ok else '*** DIFERE ***'}")
    return ok


def pct(parte: float, total: float) -> float:
    return 100.0 * parte / total if total else float("nan")


def _provido(row: dict) -> float:
    return _num(row.get("Provido")) + _num(row.get("Provido em parte"))


def _achar(linhas: list[dict], coluna: str, trecho: str, exato: bool = False) -> dict | None:
    """Primeira linha cuja coluna casa com o trecho — mesma busca do script R."""
    alvo = trecho.lower()
    for linha in linhas:
        valor = (linha.get(coluna) or "").strip()
        if (valor.lower() == alvo) if exato else (alvo in valor.lower()):
            return linha
    return None


def main() -> int:
    print("=== Artigo 4 — arranjo recursal da LAI (conferência em Python) ===")

    anos = _ler("por-ano.csv")
    por_ano = {int(_num(linha["ano"])): linha for linha in anos}

    conferir("Corpus", "recursos", 222242, sum(_num(l["recursos"]) for l in anos), 0)
    conferir("Série 2012", "recursos", 4606, _num(por_ano[2012]["recursos"]), 0)
    conferir("Série 2025", "recursos", 22278, _num(por_ano[2025]["recursos"]), 0)

    for ano, prov, nao_conh, sem_resp in ((2025, 39.5, 18.7, 5.2), (2021, None, 14.5, 3.1)):
        linha = por_ano[ano]
        total = _num(linha["recursos"])
        if prov is not None:
            conferir(f"Provimento {ano}", "%", prov, pct(_provido(linha), total))
        conferir(f"Não conhecido {ano}", "%", nao_conh,
                 pct(_num(linha["Não conhecido"]), total))
        conferir(f"Sem resposta {ano}", "%", sem_resp,
                 pct(_num(linha["Sem resposta registrada"]), total))

    instancias = _ler("instancia-x-desfecho.csv")
    for rotulo, trecho, publicado, campo in (
            ("1ª instância", "Primeira Inst", 47.9, "provido"),
            ("1ª instância", "Primeira Inst", 11.2, "nao_conhecido"),
            ("Controle interno", "CGU", 38.9, "nao_conhecido"),
            ("CMRI", "CMRI", 62.8, "nao_conhecido")):
        linha = _achar(instancias, "Instancia", trecho)
        if linha is None:
            conferir(f"{rotulo} — linha ausente", campo, publicado, float("nan"))
            continue
        total = _num(linha["recursos"])
        valor = pct(_provido(linha), total) if campo == "provido" \
            else pct(_num(linha["Não conhecido"]), total)
        unidade = "provido (%)" if campo == "provido" else "não conhecido (%)"
        conferir(rotulo, unidade, publicado, valor)

    motivos = _ler("motivo-x-desfecho.csv")
    for rotulo, trecho, publicado, campo in (
            ("Informação incompleta", "Informação incompleta", 49.4, "provido"),
            ("Ausência de justificativa", "Ausência de justificativa legal", 41.6, "nao_conhecido"),
            ("Sigilo", "Justificativa para o sigilo", 21.4, "provido")):
        linha = _achar(motivos, "TipoRecurso", trecho)
        if linha is None:
            conferir(f"{rotulo} — linha ausente", campo, publicado, float("nan"))
            continue
        total = _num(linha["recursos"])
        valor = pct(_provido(linha), total) if campo == "provido" \
            else pct(_num(linha["Não conhecido"]), total)
        unidade = "provido (%)" if campo == "provido" else "não conhecido (%)"
        conferir(rotulo, unidade, publicado, valor)

    guardioes = _ler("guardioes.csv")
    print("\n--- guardiões (por grupo) ---")
    for linha in guardioes:
        print(f"{linha['grupo']:<28} {linha['recursos']:>7}  {linha['pct']:>6}%")

    print(f"\nFIM — {CONFERIDOS} itens conferidos | {CONFERIDOS - DIFERENTES} BATE | {DIFERENTES} DIFERE")
    return 0 if DIFERENTES == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

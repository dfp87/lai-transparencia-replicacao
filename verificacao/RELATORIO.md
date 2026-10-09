# Relatório da verificação dos códigos

**Objeto:** execução integral dos quatro scripts de replicação, de dentro do repositório, conferindo
cada número publicado nos artigos contra o valor recalculado, nas duas linguagens.

**Data da execução:** 2026-10-09 16:53 UTC (UTC) · **Ambiente:** Python 3.11.15 · R version 4.5.0 (2025-04-11)

## Resultado

| Script | Itens conferidos | BATE | DIFERE |
|---|---|---|---|
| Python — artigo 1, `replicacao-artigo1.py` | 20 | **20** | 0 |
| Python — artigo 2, `replicacao-artigo2.py` | 16 | **16** | 0 |
| R — artigo 1, `replicacao-artigo1.R` | 88 | **88** | 0 |
| R — artigo 2, `replicacao-artigo2.R` | 158 | **158** | 0 |
| **Total** | **282** | **282** | **0** |

A saída completa de cada execução está nos arquivos `saida-*.txt` desta pasta — inclusive a
tabela item a item, com o valor publicado, o valor recalculado e o veredito.

## O que cada conferência cobre

- **Python — artigo 1 (20 itens):** série anual de pedidos (2012–2025), os 14 grupos de órgãos em
  2025, os percentuais acima de 20 dias por grupo, o núcleo do perímetro (Ministério Público,
  Congresso, Justiça do Trabalho e TCU com zero pedidos; Judiciário, Legislativo e controle
  externo estadual) e a parcela dos guardiões.
- **Python — artigo 2 (16 itens):** série textual de 2015 a 2025 (resumo, detalhamento, extensão
  média), respostas e negativas por ano, decisões e os totais de resposta padronizada — literal e
  por quase-repetição.
- **R — artigo 1 (88 itens):** tudo o que o Python confere, recalculado por implementação
  independente, **mais** a reconferência direta dos microdados originais (arquivos anuais de
  Pedidos), ano a ano — camada que não passa pelas evidências derivadas.
- **R — artigo 2 (158 itens):** a série textual e as tabelas de decisão, canal de entrega,
  tipologia do fundamento da negativa, convergência entre o registro e o texto e a medição de
  quase-repetição.

## Correções que a própria verificação provocou

A conferência não foi decorativa — ela mudou os artigos, sempre na direção do dado:

1. **Quadro 1 do artigo 1** trazia 6,6% de negativa no total; o recalculado é **7,6%**
   (11.404 de 150.189). O 6,6% era do outro corpus (61.824 de 938.987). Corrigido no texto.
2. **Parcela dos guardiões:** 0,95% → **0,96%** (1.486 de 154.079). Corrigido no texto.
3. **Frase do artigo 2:** a afirmação de que a quase-repetição supera a literal em todos os anos é
   **falsa** — 2020 inverte (24,7% literal × 20,6% quase) e a distância chega a 5,2 p.p. em 2019.
   A frase foi substituída pela série medida.

## Sanitização antes da publicação

A varredura por dados pessoais encontrou **trechos literais de pedidos de cidadãos** usados como
exemplos nas evidências das camadas 1 e 3. Foram **1546 trechos** substituídos por marcador de
supressão, em 13 arquivos de evidência. Depois da substituição, os quatro scripts foram
reexecutados: os totais **não mudaram** (282 itens conferidos, 0 divergências) — prova de que
nenhum número medido dependia dos trechos suprimidos.

O corpus bruto (pedidos, respostas, recursos) **não** é redistribuído aqui: o repositório publica
apenas agregados. Ver `NOTICE.md`.

## Limites declarados

- A camada de microdados dos scripts R exige os arquivos anuais originais de Pedidos; sem eles, o
  script segue pelas evidências derivadas e a ponte com o microdado é pulada (variável `LAI_MICRO`).
- As **figuras 4 e 6 do artigo 2** (fundamento da negativa no texto; o que no pedido prediz a
  negativa) **não** estão ligadas ao script Python — dependem dos arquivos de medição das camadas
  1 e 3. É o único ponto em que a replicação ainda é parcial.
- A conferência é de **números**, não de prosa: o script verifica se o valor afirmado confere, não
  se a frase que o afirma é boa.

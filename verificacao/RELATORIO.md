# Relatório da verificação dos códigos

**Objeto:** execução integral dos conferidores de replicação, de dentro do repositório, conferindo
cada número publicado nos artigos contra o valor recalculado — em duas linguagens onde há par, e
com reconferência direta nos microdados no R.

**Data da execução:** 2026-10-09 16:53 UTC (UTC) · **Ambiente:** Python 3.11.15 · R version 4.5.0 (2025-04-11)
**Acréscimo de 2026-11-17:** conferidor Python do artigo 4 (`replicacao-artigo4.py`), executado em
Python 3.12 na VPS; saída em `saida-python-artigo4.txt`.

## Resultado

| Script | Artigo | Itens conferidos | BATE | DIFERE |
|---|---|---|---|---|
| Python — `replicacao-artigo1.py` | 1 | 20 | **20** | 0 |
| Python — `replicacao-artigo2.py` | 2 | 16 | **16** | 0 |
| Python — `replicacao-artigo4.py` | 4 | 15 | **15** | 0 |
| R — `replicacao-artigo1.R` | 1 | 88 | **88** | 0 |
| R — `replicacao-artigo2.R` | 2 | 158 | **158** | 0 |
| R — `verificacao-artigo3.R` | 3 | 88 | **88** | 0 |
| R — `replicacao-artigo4.R` | 4 | 15 | **15** | 0 |
| R — `replicacao-artigo5.R` | 5 | 10 | **10** | 0 |
| **Total** | | **410** | **410** | **0** |

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
- **R — artigo 3 (88 itens):** a padronização medida sobre a resposta **inteira** (11 anos,
  938.987 respostas) e os coeficientes de robustez — inclusive os que controlam a tendência do
  tempo (quase × plataforma e literal × plataforma).
- **Python — artigo 4 (15 itens):** corpus de 222.242 recursos, a série nas pontas (2012 e 2025),
  provimento, não conhecido e sem resposta em 2025 e 2021, as taxas por instância (primeira
  instância, CGU e CMRI) e por motivo declarado (informação incompleta, ausência de justificativa
  legal, sigilo). Diferente do conferidor R, **recalcula o percentual a partir das contagens** em
  vez de ler a coluna derivada.
- **R — artigo 4 (15 itens):** os mesmos 15 números, por implementação independente, lendo as
  colunas de percentual já apuradas.
- **R — artigo 5 (10 itens):** a precisão da amostra rotulada, o erro-padrão e o intervalo para os
  cenários de tamanho de amostra e de kappa declarados no artigo.

## Correções que a própria verificação provocou

A conferência não foi decorativa — ela mudou os artigos, sempre na direção do dado:

1. **Quadro 1 do artigo 1** trazia 6,6% de negativa no total; o recalculado é **7,6%**
   (11.404 de 150.189). O 6,6% era do outro corpus (61.824 de 938.987). Corrigido no texto.
2. **Parcela dos guardiões:** 0,95% → **0,96%** (1.486 de 154.079). Corrigido no texto.
3. **Frase do artigo 2:** a afirmação de que a quase-repetição supera a literal em todos os anos é
   **falsa** — 2020 inverte (24,7% literal × 20,6% quase) e a distância chega a 5,2 p.p. em 2019.
   A frase foi substituída pela série medida.

## Divergências de arredondamento encontradas pelo conferidor Python do artigo 4

Como ele **recalcula** o percentual a partir das contagens, dois itens ficaram a 0,1 p.p. da coluna
derivada publicada, dentro da tolerância declarada (1,5 unidade na última casa):

- **2021, sem resposta registrada:** publicado 3,1% · recalculado 3,2%
- **CMRI, não conhecido:** publicado 62,8% · recalculado 62,7%

Não são erros de conta do artigo: a coluna derivada trunca em vez de arredondar. Ficam registrados
para que quem replicar veja o mesmo 0,1 e não o trate como divergência nova.

## Sanitização antes da publicação

A varredura por dados pessoais encontrou **trechos literais de pedidos de cidadãos** usados como
exemplos nas evidências das camadas 1 e 3. Foram **1546 trechos** substituídos por marcador de
supressão, em 13 arquivos de evidência. Depois da substituição, os quatro conferidores então existentes foram
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

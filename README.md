# Replicação — cinco análises da LAI (dados abertos do Fala.BR/CGU)

Este repositório contém o **código e os dados derivados** que sustentam **cinco análises** dos
dados abertos da Lei de Acesso à Informação brasileira (Lei nº 12.527/2011), no âmbito do
Programa de Pós-Graduação em Governança e Transformação Digital (PPGGTD/UFT).

> **Atenção ao número do artigo:** o nome dos scripts segue a ordem interna desta série, que
> **não é** a ordem de publicação. A tabela abaixo é a correspondência oficial entre título,
> número e script.

| # | Artigo | Scripts de replicação | Conferência |
|---|---|---|---|
| 1 | **Os guardiões fora do espelho** — perímetro institucional (2012–2025) | `replicacao-artigo1.py`, `replicacao-artigo1.R`, `lai_pipeline.py`/`.R` | 20 (Python) + 88 (R) |
| 2 | **Como o Estado escreve o "não"** — o texto da resposta (2015–2025) | `replicacao-artigo2.py`, `replicacao-artigo2.R`, `minhash_respostas_v2.py`, `lai_pipeline.py`/`.R` | 16 (Python) + 158 (R) |
| 3 | **A resposta inteira** — padronização sobre a resposta completa | `minhash_resposta_inteira.py`, `padronizacao_por_grupo_ano.py`, `consolidar_resposta_inteira.py`, `montar_artigo3.py` | 88 (R) |
| 4 | **O que o cidadão contesta** — 222.242 recursos da LAI (2012–2025) | `recursos_estudo_A.py`, `replicacao-artigo4.py`, `replicacao-artigo4.R`, `figuras-e-precisao.py` | 15 (Python) + 15 (R) |
| 5 | **Medir a evasão** — precisão da amostra e intervalo | `figuras-e-precisao.py`, `montar_artigos_4e5.py`, `replicacao-artigo5.R` | 10 (R) |

Em uma frase cada:

1. **Perímetro institucional** — quem está dentro do acervo e como cada grupo de órgãos responde,
   de 2012 a 2025: volume, prazo e negativa por grupo, e a ausência de parte dos órgãos de
   controle e de justiça no acervo publicado.
2. **O texto da resposta** — o que o Estado escreve quando responde (ou nega), de 2015 a 2025:
   presença de resumo e detalhamento, extensão, decisão, fundamento normativo da negativa e
   **repetição de resposta** (padronização por repetição literal e por quase-repetição).
3. **A resposta inteira** — a mesma medição de padronização aplicada à resposta completa, e não à
   janela de 250 caracteres, como teste de robustez do achado.
4. **O que o cidadão contesta** — o arranjo recursal: 222.242 recursos, motivo declarado,
   instância de julgamento e desfecho, de 2012 a 2025.
5. **Medir a evasão** — a precisão da amostra rotulada e o efeito do tamanho da amostra sobre o
   intervalo, com o intervalo de confiança declarado.

O objetivo do repositório é permitir **clonar, inspecionar e reproduzir** cada número publicado
nos dois artigos, sem depender de memória de execução: cada script recalcula os indicadores a
partir das evidências versionadas e, ao final, **compara o resultado recalculado com o número
publicado**, imprimindo `BATE` ou `DIFERE` para cada item.

## O que está aqui — e o que não está

**Está:** os scripts de replicação (Python e R), o pipeline que gera as evidências, as
evidências derivadas (indicadores anuais, tabelas de grupo, séries, resultados da medição de
quase-repetição) e as duas bases de referências conferidas por DOI.

**Não está, de propósito:**

- os **manuscritos** dos artigos (em avaliação editorial; não são pré-publicados aqui);
- o **corpus textual bruto** (~3,5 GB de arquivos anuais de Respostas e o CSV de Pedidos,
  Recursos e Solicitantes): são dados abertos da CGU, e o script aponta a origem em vez de
  redistribuir cópia;
- qualquer **dado institucional** que não seja dos conjuntos abertos citados abaixo.

## Como replicar

### Python

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# artigo 1 — perímetro institucional e desempenho (2012–2025)
python3 reprodutibilidade/replicacao-artigo1.py

# artigo 2 — o texto da resposta (2015–2025)
python3 reprodutibilidade/replicacao-artigo2.py

# artigo 2, refazendo a medição de quase-repetição do zero sobre o corpus bruto
# (opcional: ~25 min por ano; exige os arquivos anuais de Respostas em <dir>)
python3 reprodutibilidade/replicacao-artigo2.py --corpus /caminho/para/respostas

# artigo 4 — o arranjo recursal (conferência dos 15 números publicados)
python3 reprodutibilidade/replicacao-artigo4.py
```

### R (RStudio ou linha de comando)

```r
# na raiz do repositório
source("reprodutibilidade/replicacao-artigo1.R")
source("reprodutibilidade/replicacao-artigo2.R")
source("reprodutibilidade/verificacao-artigo3.R")
source("reprodutibilidade/replicacao-artigo4.R")
source("reprodutibilidade/replicacao-artigo5.R")
```

Ou, em terminal: `Rscript reprodutibilidade/replicacao-artigo1.R` (execução completa em ~70 s).

Ambos os scripts escrevem as tabelas em `saidas/` (CSV) e as figuras em `saidas/figuras/`
(PNG, 300 dpi) — diretórios criados na execução e ignorados pelo Git.

### Dependências

- **Python:** `matplotlib` (figuras) e biblioteca padrão. Opcional: `pypdf` (conferência de
  páginas dos documentos).
- **R:** R 4.5.0, com `jsonlite`; base R para o restante. O arquivo `sessionInfo.txt` registra
  a sessão exata usada na verificação.

## O que cada script faz

| Script | Artigo | Entrada | Saída |
|---|---|---|---|
| `replicacao-artigo1.py` / `.R` | 1 | 14 JSON anuais + tabela de grupos auditada (2025) | série anual; tabela por grupo; série por grupo; 7 figuras |
| `replicacao-artigo2.py` / `.R` | 2 | série textual anual, decisões, canal de entrega, tipologia da negativa, convergência registro×texto, resultados do MinHash | tabelas de decisão, de texto e de padronização; figuras |
| `verificacao-artigo3.R` | 3 | saídas de `saidas-minhash/` e `saidas-grupo-ano/` | conferência da padronização sobre a resposta inteira e das correlações de robustez |
| `recursos_estudo_A.py` | 4 | arquivos anuais de Recursos e Reclamações (Fala.BR/CGU) | `saidas-recursos/`: base analítica, por ano, motivo × desfecho, instância × desfecho, guardiões, `resumo.json` |
| `replicacao-artigo4.py` / `.R` | 4 | `saidas-recursos/*.csv` | conferência item a item dos 15 números publicados |
| `replicacao-artigo5.R` | 5 | `saidas-recursos/precisao-kappa.csv` | conferência da precisão, do erro-padrão e do intervalo |
| `lai_pipeline.py` / `.R` | 1 e 2 | corpus bruto (CSV anuais) | evidências anuais (`estruturado_<ano>.json`, `texto_<ano>.json`) |
| `minhash_respostas_v2.py` | 2 | corpus textual bruto | quase-repetição por ano (MinHash) nas três configurações auditadas |
| `minhash_resposta_inteira.py` | 3 | corpus textual bruto | padronização sobre a resposta inteira (11 anos, 938.987 respostas) |

## Método, em três frases

A **resposta padronizada** é medida de dois modos sobre a abertura normalizada da resposta
(250 caracteres, minúsculas, sem pontuação): repetição **literal** (hash md5 idêntico) e
**quase-repetição** (MinHash: shingles de 5 palavras, 128 permutações, semente 20261008,
LSH de 16 bandas × 8 linhas, limiar de Jaccard 0,80, grupo mínimo de 5 no ano). O perímetro é
medido sobre o registro estruturado (pedidos, decisão, prazo e órgão) com classificação de
órgãos em 14 grupos, auditada para 2025. O MinHash é um **piso** de medição: a variante que
descarta baldes grandes perde grupos extensos e a que os une os superestima — as três
configurações são publicadas lado a lado em `reprodutibilidade/saidas-minhash/consolidado_minhash_*.json`.

## Procedência dos dados

- **Fala.BR / CGU — dados abertos da LAI:** arquivos anuais de Pedidos, Recursos, Solicitantes
  e Respostas, disponíveis no portal de dados abertos do Governo Federal.
  <https://dados.gov.br/dados/conjuntos-dados/pedidos-de-acesso-a-informacao>
- **Referências bibliográficas:** metadados conferidos um a um na API do Crossref e no
  OpenAlex (DOI, título, ano, veículo), em `evidencias/`.

Os dados derivados aqui publicados são **agregados**: não contêm pedido, resposta ou
solicitante individual. Nenhum dado pessoal é redistribuído.

## Como citar

Ver `CITATION.cff`. Citação sugerida:

> PINTO, Douglas Ferreira. **Replicação — texto da resposta e perímetro da LAI (dados abertos
> do Fala.BR/CGU)**. Versão 1.0.0. 2026. Código-fonte e dados derivados.
> <https://github.com/dfp87/lai-transparencia-replicacao>

## Licenças

- **Código** (`reprodutibilidade/`): MIT — ver `LICENSE`.
- **Dados derivados e documentação** (`evidencias/`, `verificacao/`, este README): CC BY 4.0.
- Ver `NOTICE.md` para a declaração de procedência e o que a licença não cobre.

## Verificação

`verificacao/` guarda o relatório da conferência número a número: cada valor publicado nos cinco
artigos foi comparado com o valor recalculado, e a saída de cada execução está versionada.

| Conferidor | Artigo | Itens | Resultado |
|---|---|---|---|
| `replicacao-artigo1.py` | 1 | 20 | 20 BATE |
| `replicacao-artigo2.py` | 2 | 16 | 16 BATE |
| `replicacao-artigo4.py` | 4 | 15 | 15 BATE |
| `replicacao-artigo1.R` | 1 | 88 | 88 BATE |
| `replicacao-artigo2.R` | 2 | 158 | 158 BATE |
| `verificacao-artigo3.R` | 3 | 88 | 88 BATE |
| `replicacao-artigo4.R` | 4 | 15 | 15 BATE |
| `replicacao-artigo5.R` | 5 | 10 | 10 BATE |
| **Total** | | **410** | **410 BATE, 0 DIFERE** |

Duas independências diferentes convivem aqui, e o README declara qual é qual:

- **entre linguagens** — o mesmo número é recalculado em Python e em R por implementações
  separadas (`artigos 1, 2 e 4`);
- **entre camadas** — o R reconfere direto nos **microdados originais** de Pedidos, sem passar
  pelas evidências derivadas (`LAI_MICRO`).

No artigo 4, o conferidor Python é mais estrito que o R em um ponto: ele **recalcula o percentual**
a partir das contagens (`Provido + Provido em parte` sobre `recursos`), em vez de ler a coluna de
percentual já apurada. Isso expôs duas diferenças de arredondamento de 0,1 p.p. (2021 sem resposta
e CMRI), registradas em `verificacao/saida-python-artigo4.txt`.

## Sanitização e limites

- **Dados pessoais:** as evidências das camadas 1 e 3 guardavam trechos literais de pedidos de
  cidadãos como exemplo; os **1.546 trechos** foram substituídos por marcador de supressão antes da
  publicação, e os scripts foram reexecutados depois — os totais não mudaram. Ver `NOTICE.md`.
- **Microdados:** a camada que reconfere tudo direto nos microdados originais (só nos scripts R)
  exige os arquivos anuais de Pedidos; sem eles o script segue pelas evidências e pula essa ponte
  (variável de ambiente `LAI_MICRO`).
- **Replicação parcial declarada:** as figuras 4 e 6 do artigo 2 ainda não estão ligadas ao script
  Python (dependem dos arquivos de medição das camadas 1 e 3).
- **Conferência é de número, não de prosa:** os scripts conferem se o valor afirmado confere.

## Medições acrescentadas na versão 1.1

- `reprodutibilidade/minhash_resposta_inteira.py` — a medição de padronização sobre a **resposta
  inteira** (11 anos, **938.987 respostas**), com os mesmos parâmetros do módulo da janela de 250
  caracteres, para comparação direta.
- `reprodutibilidade/padronizacao_por_grupo_ano.py` — a mesma medição **por grupo de órgão e por
  ano**, com a regra de classificação declarada em `lai_pipeline.py`.
- `reprodutibilidade/consolidar_resposta_inteira.py` — tabelas A–D, `resumo.json` e as figuras F1–F3
  (comparação das duas medidas, série por grupo, dispersão com a plataformização).
- `reprodutibilidade/recursos_estudo_A.py` — base analítica dos **222.242 recursos e reclamações**.
  Atenção: o dado aberto traz esses registros **codificados**; não há texto livre do cidadão
  (o campo de detalhamento está preenchido em 0,6% dos casos).
- `reprodutibilidade/montar_artigo3.py` — monta as tabelas do artigo 3 a partir dos CSV consolidados.

**Resultado medido (938.987 respostas, 2015–2025):** repetição **literal** cai de **20,64%** (janela de
250 caracteres) para **14,86%** (resposta inteira); **quase-repetição** sobe de **22,55%** para
**24,21%**. A correlação com a plataformização do atendimento é **negativa** (r = −0,672 na
quase-repetição; −0,712 na literal, 11 anos) e, retirada a tendência do tempo, sobrevive apenas na
repetição literal (r = −0,699; a da quase-repetição cai para −0,377).

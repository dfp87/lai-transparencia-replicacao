# Replicação — texto da resposta e perímetro da LAI (dados abertos do Fala.BR/CGU)

Este repositório contém o **código e os dados derivados** que sustentam duas análises dos
dados abertos da Lei de Acesso à Informação brasileira (Lei nº 12.527/2011), no âmbito do
Programa de Pós-Graduação em Governança e Transformação Digital (PPGGTD/UFT):

1. **O texto da resposta** — o que o Estado escreve quando responde (ou nega), de 2015 a 2025:
   presença de resumo e detalhamento, extensão, decisão, fundamento normativo da negativa e
   **repetição de resposta** (resposta padronizada por repetição literal e por quase-repetição).
2. **O perímetro institucional** — quem está dentro do acervo e como cada grupo de órgãos
   responde, de 2012 a 2025: volume, prazo e negativa por grupo, e a ausência de parte dos
   órgãos de controle e de justiça no acervo publicado.

O objetivo do repositório é permitir **clonar, inspecionar e reproduzir** cada número publicado
nos dois artigos, sem depender de memória de execução: cada script recalcula os indicadores a
partir das evidências versionadas e, ao final, **compara o resultado recalculado com o número
publicado**, imprimindo `BATE` ou `DIFERE` para cada item.

## O que está aqui — e o que não está

**Está:** os scripts de replicação (Python e R), o pipeline que gera as evidências, as
evidências derivadas (indicadores anuais, tabelas de grupo, séries, resultados da medição de
quase-repetição) e as duas bases de referências conferidas por DOI.

**Não está, de propósito:**

- os **manuscritos** das duas análises (em avaliação editorial; não são pré-publicados aqui);
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
```

### R (RStudio ou linha de comando)

```r
# na raiz do repositório
source("reprodutibilidade/replicacao-artigo1.R")
source("reprodutibilidade/replicacao-artigo2.R")
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

| Script | Entrada | Saída |
|---|---|---|
| `replicacao-artigo1.py` / `.R` | 14 JSON anuais + tabela de grupos auditada (2025) | série anual; tabela por grupo; série por grupo; 7 figuras |
| `replicacao-artigo2.py` / `.R` | série textual anual, decisões, canal de entrega, tipologia da negativa, convergência registro×texto, resultados do MinHash | tabelas de decisão, de texto e de padronização; figuras |
| `lai_pipeline.py` / `.R` | corpus bruto (CSV anuais) | evidências anuais (`estruturado_<ano>.json`, `texto_<ano>.json`) |
| `minhash_respostas_v2.py` | corpus textual bruto | quase-repetição por ano (MinHash) nas três configurações auditadas |

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

`verificacao/` guarda o relatório da conferência número a número: os quatro scripts foram
executados e cada valor publicado nos dois artigos foi comparado com o valor recalculado, nas
duas linguagens, incluindo a conferência do R contra os **microdados originais** — camada
independente das evidências derivadas.

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

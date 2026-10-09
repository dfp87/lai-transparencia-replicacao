# NOTICE — procedência, licenças e limites de uso

## 1. Origem dos dados

Os dados brutos analisados são **dados abertos** publicados pela Controladoria-Geral da União
no âmbito da Lei de Acesso à Informação (Lei nº 12.527/2011), no portal de dados abertos do
Governo Federal:

- Pedidos de acesso à informação: <https://dados.gov.br/dados/conjuntos-dados/pedidos-de-acesso-a-informacao>

Este repositório **não redistribui** o corpus bruto. O que está versionado em `dados/` são
**agregados e indicadores derivados** — contagens, séries, medianas, percentuais e resultados da
medição de similaridade —, além de uma tabela de classificação de órgãos por grupo. Nenhum
registro individual de pedido, resposta ou solicitante é publicados aqui, e nenhum dado pessoal
é tratado ou redistribuído.

## 2. Licenças, por parte do repositório

| Parte | Licença |
|---|---|
| `codigo/` (scripts Python e R) | MIT — ver `LICENSE` |
| `dados/` (agregados, séries, bases de referências) | CC BY 4.0 |
| `verificacao/`, `README.md`, este NOTICE | CC BY 4.0 |

A licença deste repositório **não se estende** aos dados originais da CGU, que seguem as
condições do portal de dados abertos, nem aos textos dos artigos, que não estão aqui.

## 3. O que este repositório não é

- **Não é pré-publicação de artigo.** Os manuscritos correspondentes estão em avaliação
  editorial e não são depositados aqui nem em servidor de preprints, por decisão dos autores.
- **Não é o dado oficial.** Os indicadores são derivados por tratamento próprio e não
  substituem as estatísticas publicadas pela CGU.
- **Não é indicador institucional.** As medidas são resultado de pesquisa acadêmica
  independente; a publicação não implica endosso de qualquer órgão.

## 4. Como as referências foram conferidas

As duas bases em `dados/referencias/` trazem, para cada obra, o DOI e o resultado da
conferência independente feita na API do Crossref (título, ano, veículo, volume, número e
páginas) e, quando havia resumo indexado, a verificação de que o excerto citado consta do
registro. Uma linha ficou marcada como divergente de edição e outra como resumo não acessível —
as duas declaradas no campo próprio, não corrigidas por suposição.

## 5. Contato

Douglas Ferreira Pinto — PPGGTD/UFT. Use as *issues* do repositório para erros de replicação.

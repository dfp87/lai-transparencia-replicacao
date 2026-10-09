#!/usr/bin/env Rscript
# ==========================================================================================
#  LAI 15 ANOS — PIPELINE COMPLETO EM R  (versão para RStudio)
#  Da coleta automatizada à geração das análises discorridas
# ==========================================================================================
#
#  Uso no RStudio (ou no terminal):
#      source("lai_pipeline.R")                 # carrega as funções e a configuração
#      etapa_diagnostico()                      # inventário de colunas reais
#      etapa_coleta()                           # baixa tudo (estruturados + textos)
#      etapa_estruturada(2025)                  # análise de um ano da base estruturada
#      etapa_textual(2024, limiar = 5)          # análise de um ano do pacote de textos
#      etapa_verificacao()                      # compara com as medições de referência
#      etapa_relatorio()                        # gera o markdown das análises discorridas
#      etapa_tudo()
#
#  Pacotes usados: data.table, jsonlite, digest  (todos presentes no ambiente padrão do RStudio)
#
#  ------------------------------------------------------------------------------------------
#  LIÇÕES DE CAMPO INCORPORADAS (medidas, não supostas) — valem igual para o script em Python
#  ------------------------------------------------------------------------------------------
#  1. O download EXIGE cabeçalho de navegador (User-Agent + Referer). Sem isso o WAF da CGU
#     devolve página de erro em vez do arquivo. Por isso a coleta usa curl pelo sistema.
#  2. O WAF ESTRANGULA EM RAJADA: vários arquivos seguidos derrubam as últimas tentativas
#     (o arquivo volta com ~2 KB). Daí a pausa entre arquivos, as 3 tentativas e a checagem
#     da assinatura ZIP antes de aceitar o arquivo.
#  3. O ESQUEMA PUBLICADO NA PÁGINA OFICIAL ESTÁ DESATUALIZADO: o CSV real de Pedidos tem
#     23 colunas (a página lista 20) e o de Recursos tem 21 (a página lista 17). Este script
#     SEMPRE lê o cabeçalho do arquivo, nunca uma lista fixa.
#  4. Os CSVs são UTF-16 com separador ';'.
#  5. Os campos de texto têm quebras de linha dentro de aspas: conte linhas com cuidado.
#  6. O pacote de textos é SUBCONJUNTO ESTRITO da base estruturada (100% dos identificadores
#     existem na base; a fatia publicada vai de 74,3% a 55,8% dos pedidos por ano).
#  7. Lematização foi testada e NÃO muda a medida de padronização (12,7% com e sem, em amostra
#     de 12 mil respostas de 2024). Por isso este script não a usa na medida central.
# ==========================================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(jsonlite)
  library(digest)
  library(readr)
})

# ============================== CONFIGURAÇÃO ==============================

CONF <- list(
  raiz = Sys.getenv("LAI_RAIZ", unset = "/root/lai"),
  pagina_oficial = paste0("https://www.gov.br/acessoainformacao/pt-br/falabr/visao-geral/",
                          "busca-de-pedidos-e-respostas-download-de-dados"),
  base_download = "https://dadosabertos-download.cgu.gov.br/FalaBR",
  user_agent = paste0("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ",
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
  sep = ";", encoding = "UTF-16LE",
  pausa_entre_arquivos_s = 20, tentativas = 3L, pausa_retentativa_s = 75,
  limiar_padronizacao = 5L, limiar_caracteres_abertura = 250L, semente = 20261006L,
  anos_estruturado = 2012:2025, anos_texto = 2015:2025
)

.dirs <- function() {
  d <- list(
    raiz = CONF$raiz, zips = file.path(CONF$raiz, "zips"), csv = file.path(CONF$raiz, "csv"),
    txt = file.path(CONF$raiz, "txt"), saida = file.path(CONF$raiz, "saida"),
    figuras = file.path(CONF$raiz, "figuras"), serie_textual = file.path(CONF$raiz, "serie_textual")
  )
  invisible(lapply(d, dir.create, showWarnings = FALSE, recursive = TRUE))
  d
}

.log <- function(...) cat(sprintf("[%s] %s\n", format(Sys.time(), "%H:%M:%S"), paste0(...)))
.salvar_json <- function(obj, caminho) write_json(obj, caminho, auto_unbox = TRUE,
                                                  pretty = TRUE, null = "null")

# ============================== 1. COLETA ==============================

.padroes_estruturados <- function(ano) list(
  list(local = sprintf("Pedidos_%d.zip", ano),
       url = sprintf("%s/FalaBR/Arquivos_csv_%d.zip", CONF$base_download, ano),
       tipo = "Pedidos"),
  list(local = sprintf("Recursos_Reclamacoes_%d.zip", ano),
       url = sprintf("%s/FalaBR/Recursos_Reclamacoes_csv_%d.zip", CONF$base_download, ano),
       tipo = "Recursos"),
  list(local = sprintf("SolicitantesPedidos_%d.zip", ano),
       url = sprintf("%s/FalaBR/SolicitantesPedidos_csv_%d.zip", CONF$base_download, ano),
       tipo = "Solicitantes")
)

.baixar <- function(url, destino, verificar_apenas = FALSE) {
  if (verificar_apenas) {
    saida <- system2("curl", c("-sS", "-I", "--max-time", "60",
                               "-A", shQuote(CONF$user_agent),
                               "-H", shQuote(paste0("Referer: ", CONF$pagina_oficial)),
                               shQuote(url)), stdout = TRUE, stderr = TRUE)
    return(any(grepl("200", saida)))
  }
  if (file.exists(destino) && file.info(destino)$size > 1e6) {
    con <- file(destino, "rb"); assinatura <- readBin(con, "raw", 2); close(con)
    if (identical(assinatura, charToRaw("PK"))) {
      .log("já existe e é válido: ", basename(destino)); return(TRUE)
    }
  }
  for (tentativa in seq_len(CONF$tentativas)) {
    system2("curl", c("-sS", "--max-time", "900", "-o", shQuote(destino),
                      "-A", shQuote(CONF$user_agent),
                      "-H", shQuote(paste0("Referer: ", CONF$pagina_oficial)),
                      shQuote(url)), stdout = TRUE, stderr = TRUE)
    if (file.exists(destino)) {
      tamanho <- file.info(destino)$size
      con <- file(destino, "rb"); assinatura <- readBin(con, "raw", 2); close(con)
      if (tamanho > 1e6 && identical(assinatura, charToRaw("PK"))) {
        .log(sprintf("baixado: %s (%.1f MB)", basename(destino), tamanho / 1048576)); return(TRUE)
      }
      .log(sprintf("tentativa %d falhou (%s, %d bytes) — pausa %ds",
                   tentativa, basename(destino), tamanho, CONF$pausa_retentativa_s))
    }
    Sys.sleep(CONF$pausa_retentativa_s)
  }
  .log("FALHOU definitivamente: ", url); FALSE
}

etapa_coleta <- function(anos = CONF$anos_estruturado, textos = CONF$anos_texto,
                         verificar_apenas = FALSE) {
  d <- .dirs(); res <- list(estruturado = list(), textos = list())
  for (ano in anos) for (p in .padroes_estruturados(ano)) {
    destino <- file.path(d$zips, p$local)
    res$estruturado[[p$local]] <- .baixar(p$url, destino, verificar_apenas)
    if (!verificar_apenas) Sys.sleep(2)
  }
  for (ano in textos) {
    local <- sprintf("textos_%d.zip", ano)
    url <- sprintf("%s/Arquivos_FalaBR_Filtrado/Arquivos_csv_%d.zip", CONF$base_download, ano)
    res$textos[[local]] <- .baixar(url, file.path(d$zips, local), verificar_apenas)
    if (!verificar_apenas) Sys.sleep(CONF$pausa_entre_arquivos_s)
  }
  .salvar_json(res, file.path(d$saida, "coleta_r.json"))
  .log("coleta: ", length(res$estruturado), " estruturados, ", length(res$textos), " textos")
  invisible(res)
}

# ============================== 2. PREPARAÇÃO ==============================

.extrair <- function(zip_path, destino_dir, contem = "") {
  if (!file.exists(zip_path)) return(character(0))
  conteudo <- unzip(zip_path, list = TRUE)$Name
  conteudo <- conteudo[grepl("\\.csv$", conteudo, ignore.case = TRUE)]
  if (nzchar(contem)) conteudo <- conteudo[grepl(contem, conteudo, ignore.case = TRUE)]
  if (!length(conteudo)) return(character(0))
  utils::unzip(zip_path, files = conteudo, exdir = destino_dir, junkpaths = TRUE)
  file.path(destino_dir, basename(conteudo))
}

.arquivo_estruturado <- function(ano, tipo = "Pedidos") {
  d <- .dirs()
  for (p in .padroes_estruturados(ano)) {
    if (!grepl(tipo, p$tipo, ignore.case = TRUE)) next
    achados <- .extrair(file.path(d$zips, p$local), d$csv)
    if (!length(achados)) next
    b <- tolower(basename(achados))
    if (tolower(tipo) == "pedidos") {
      achados <- achados[!grepl("solicitante|recurso", b)]
    } else if (tolower(tipo) == "recursos") {
      achados <- achados[grepl("recurso|reclamac", b)]
    }
    if (length(achados)) return(achados[1])
  }
  NULL
}

.para_utf8 <- function(caminho) {
  # LIÇÃO MEDIDA: ler UTF-16 direto (readr ou fread) DESALINHA as colunas deste arquivo —
  # os campos saíam trocados (o "órgão" virava "Internet", "Sim", datas). A solução é
  # converter uma vez para UTF-8 e ler o arquivo convertido (com fread, que é rápido).
  destino <- file.path(.dirs()$csv, paste0("utf8_", tools::file_path_sans_ext(basename(caminho)), ".csv"))
  if (!file.exists(destino) || file.info(destino)$size < 1000) {
    status <- system(paste("iconv -f UTF-16LE -t UTF-8", shQuote(caminho), ">", shQuote(destino)))
    if (status != 0 || !file.exists(destino))
      stop("falha ao converter para UTF-8: ", caminho)
  }
  destino
}

.ler_csv <- function(caminho, colunas = NULL) {
  arquivo <- .para_utf8(caminho)
  if (is.null(colunas)) {
    d <- data.table::fread(arquivo, sep = CONF$sep, colClasses = "character",
                           showProgress = FALSE, encoding = "UTF-8")
  } else {
    d <- data.table::fread(arquivo, sep = CONF$sep, select = colunas, colClasses = "character",
                           showProgress = FALSE, encoding = "UTF-8")
  }
  data.table::as.data.table(d)
}

.cabecalho <- function(caminho) {
  names(data.table::fread(.para_utf8(caminho), sep = CONF$sep, nrows = 0, showProgress = FALSE))
}

.para_data <- function(x) {
  # tenta vários formatos, sempre COM formato explícito (as.Date sem formato estoura em texto livre)
  x <- trimws(as.character(x))
  y <- ifelse(nchar(x) >= 10, substr(x, 1, 10), NA_character_)
  out <- as.Date(rep(NA_character_, length(y)))
  for (f in c("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d")) {
    faltam <- which(is.na(out) & !is.na(y))
    if (!length(faltam)) break
    out[faltam] <- suppressWarnings(as.Date(y[faltam], format = f))
  }
  out
}

.resolver <- function(colunas, candidatos) {
  norm <- function(s) gsub("[^a-z0-9]", "", iconv(tolower(s), to = "ASCII//TRANSLIT", sub = ""))
  nc <- setNames(colunas, norm(colunas))
  for (cand in candidatos) {
    if (norm(cand) %in% names(nc)) return(unname(nc[[norm(cand)]]))
  }
  for (cand in candidatos) {
    achou <- names(nc)[grepl(norm(cand), names(nc), fixed = TRUE)]
    if (length(achou)) return(unname(nc[[achou[1]]]))
  }
  NULL
}

etapa_diagnostico <- function(anos = CONF$anos_estruturado, textos = CONF$anos_texto) {
  d <- .dirs(); inv <- list(estruturado = list(), textos = list())
  for (ano in anos) for (p in .padroes_estruturados(ano)) {
    for (cam in .extrair(file.path(d$zips, p$local), d$csv)) {
      inv$estruturado[[basename(cam)]] <- list(ano = ano, bytes = file.info(cam)$size,
                                               colunas = .cabecalho(cam))
    }
  }
  for (ano in textos) {
    for (cam in .extrair(file.path(d$zips, sprintf("textos_%d.zip", ano)), d$txt)) {
      inv$textos[[basename(cam)]] <- list(ano = ano, bytes = file.info(cam)$size,
                                          colunas = .cabecalho(cam))
    }
  }
  .salvar_json(inv, file.path(d$saida, "inventario_colunas_r.json"))
  .log("diagnóstico: ", length(inv$estruturado), " arquivos estruturados, ",
       length(inv$textos), " de texto")
  invisible(inv)
}

# ============================== 3. CLASSIFICAÇÃO DE ÓRGÃOS ==============================
# Regra DECLARADA e auditável. A ORDEM importa: o primeiro padrão que casa define o grupo.

REGRAS <- list(
  "Ministério Público" = "ministerio publico|procuradoria-geral de justica|\\bmpf\\b|\\bmpt\\b|\\bmprj\\b|\\bmpsp\\b",
  "Defensoria" = "defensoria",
  "Judiciário" = "\\bstf\\b|supremo tribunal|tribunal de justica|\\btj[/ -]|\\btrf\\b|justica federal|justica do trabalho|\\btrt\\b|\\btst\\b|\\btse\\b|\\bstj\\b|\\bstm\\b|tribunal superior|tribunal regional eleitoral|\\btre\\b",
  "Legislativo" = "camara dos deputados|senado|congresso nacional|assembleia legislativa|camara municipal|camara legislativa",
  "Controle externo (tribunais de contas)" = "tribunal de contas|\\btce\\b|\\btcm\\b",
  "Controle interno" = "controladoria|^cgu\\b|cgu\\s*-|corregedoria|ouvidoria-geral da uniao",
  "Conselhos profissionais" = "conselho (regional|federal) de|conselho de fiscalizacao",
  "Estatais, bancos e empresas públicas" = "banco do brasil|caixa economica|petrobras|correios|bndes|embrapa|dataprev|serpro|conab|hemobras|finep|eletronuclear|infraero|infra s\\.a|codevasf|embratur|casa da moeda|\\bcmb\\b|cprm|companhia de pesquisa|cbtu|trensurb|amazul|imbel|\\bebc\\b|empresa brasil de comunicacao|telebras|pre-sal|\\bcdp\\b|cdrj|nuclep|\\bs\\.?a\\.?\\b|companhia|empresa publica|sociedade de economia mista|ebserh|hospital das clinicas",
  "Universidades e institutos federais" = "universidade|instituto federal|colegio pedro ii|escola tecnica|cefet",
  "Autarquias, fundações e agências" = "autarquia|fundacao|agencia nacional|instituto nacional|consulado|superintendencia|delegacia",
  "Executivo federal (ministérios e Presidência)" = "^ministerio|ministerio d|presidencia da republica|casa civil|advocacia-geral|secretaria-geral|gabinete de seguranca",
  "Esfera estadual" = "^estado d|governo do estado|secretaria de estado|procuradoria-geral do estado|policia militar",
  "Esfera municipal" = "^municipio|prefeitura|camara municipal de"
)
ORDEM_R <- c("Ministério Público", "Defensoria", "Judiciário", "Legislativo",
             "Controle externo (tribunais de contas)", "Controle interno", "Conselhos profissionais",
             "Estatais, bancos e empresas públicas", "Universidades e institutos federais",
             "Autarquias, fundações e agências", "Executivo federal (ministérios e Presidência)",
             "Esfera estadual", "Esfera municipal")

classificar_orgao <- function(nome, esfera = "") {
  if (length(nome) == 0 || is.na(nome) || !nzchar(nome)) return("não classificado")
  t <- gsub("[^a-z0-9 ]", " ", iconv(tolower(nome), to = "ASCII//TRANSLIT"))
  t <- gsub("\\s+", " ", t)
  if (grepl("agencia brasileira de apoio|agsus", t, perl = TRUE)) return("Autarquias, fundações e agências")
  if (grepl("ebserh", t, perl = TRUE) || (grepl("hospital das clinicas", t, perl = TRUE) && grepl("universidade", t, perl = TRUE)))
    return("Estatais, bancos e empresas públicas")
  if (grepl("(^|[^a-z])ministerio([^a-z]|$)", t, perl = TRUE)) return("Executivo federal (ministérios e Presidência)")
  for (g in ORDEM_R) if (grepl(REGRAS[[g]], t, perl = TRUE)) return(g)
  e <- gsub("[^a-z ]", " ", iconv(tolower(esfera), to = "ASCII//TRANSLIT"))
  if (grepl("municipal", e, perl = TRUE)) return("Esfera municipal")
  if (grepl("estadual|distrital", e, perl = TRUE)) return("Esfera estadual")
  if (grepl("federal", e, perl = TRUE)) return("Autarquias, fundações e agências")
  "não classificado"
}

# ============================== 4. ANÁLISE ESTRUTURADA ==============================

analisar_ano_estruturado <- function(ano) {
  d <- .dirs()
  caminho <- .arquivo_estruturado(ano, "Pedidos")
  if (is.null(caminho)) return(list(ano = ano, erro = "arquivo de pedidos não encontrado"))
  cols <- .cabecalho(caminho)
  c_org <- .resolver(cols, c("OrgaoDestinatario", "Órgão Destinatário"))
  c_esf <- .resolver(cols, "Esfera")
  c_dec <- .resolver(cols, c("Decisao", "Decisão"))
  c_mot <- .resolver(cols, "MotivoNegativaAcesso")
  c_pror <- .resolver(cols, "DataProrrogacao")
  c_reg <- .resolver(cols, "DataRegistro"); c_rsp <- .resolver(cols, "DataResposta")
  c_prorrog <- .resolver(cols, "FoiProrrogado")
  usar <- unique(na.omit(c(c_org, c_esf, c_dec, c_mot, c_pror, c_reg, c_rsp, c_prorrog)))

  D <- .ler_csv(caminho, usar)
  n <- nrow(D)
  decisoes <- if (!is.null(c_dec)) sort(table(D[[c_dec]]), decreasing = TRUE) else NULL
  motivos <- if (!is.null(c_mot)) sort(table(D[[c_mot]][nzchar(D[[c_mot]])]), decreasing = TRUE) else NULL
  grupos <- list()
  if (!is.null(c_org)) {
    esf <- if (!is.null(c_esf)) D[[c_esf]] else rep("", n)
    # classifica apenas os pares (órgão, esfera) DISTINTOS e mapeia de volta: acelera ~100x
    chave <- paste(D[[c_org]], esf, sep = "\u0001")
    unicas <- unique(chave)
    partes <- strsplit(unicas, "\u0001", fixed = TRUE)
    mapa <- setNames(vapply(partes, function(p) classificar_orgao(p[1], p[2]), character(1)), unicas)
    D[, grupo := mapa[chave]]
    .log(sprintf("  %s pares (órgão, esfera) distintos classificados", format(length(unicas), big.mark = ".")))
    agreg <- D[, .(pedidos = .N), by = grupo]
    if (!is.null(c_dec)) {
      D[, negado := as.integer(D[[c_dec]] == "Acesso Negado")]
      D[, concedido := as.integer(D[[c_dec]] == "Acesso Concedido")]
      D[, parcial := as.integer(D[[c_dec]] == "Acesso Parcialmente Concedido")]
      pror <- if (!is.null(c_pror)) as.integer(nzchar(D[[c_pror]])) else rep(0L, n)
      D[, prorrogado := pror]
      extra <- D[, .(negado = sum(negado), concedido = sum(concedido),
                     parcial = sum(parcial), prorrogado = sum(prorrogado)), by = grupo]
      agreg <- merge(agreg, extra, by = "grupo", all.x = TRUE)
    }
    # PRAZO: dias entre DataRegistro e DataResposta (0 a 3650 dias válidos)
    prazos <- NULL
    if (!is.null(c_reg) && !is.null(c_rsp)) {
      D[, dias := as.numeric(.para_data(D[[c_rsp]]) - .para_data(D[[c_reg]]))]
      D[dias < 0 | dias > 3650, dias := NA_real_]
      pz <- D[!is.na(dias), .(dias_mediana = as.numeric(median(dias)),
                              dias_p90 = as.numeric(quantile(dias, 0.9)),
                              pct_acima_20 = round(100 * mean(dias > 20), 1),
                              dias_n = .N), by = grupo]
      agreg <- merge(agreg, pz, by = "grupo", all.x = TRUE)
      v <- D$dias[!is.na(D$dias)]
      if (length(v)) prazos <- list(n = length(v), mediana = as.numeric(median(v)),
                                    p90 = as.numeric(quantile(v, 0.9)),
                                    pct_acima_20 = round(100 * mean(v > 20), 1))
    }
    for (i in seq_len(nrow(agreg))) {
      linha <- as.list(agreg[i])
      grupos[[linha$grupo]] <- linha[names(linha) != "grupo"]
    }
  }
  res <- list(ano = ano, arquivo = basename(caminho), pedidos = n, colunas_lidas = usar,
              prazos = prazos, decisoes = as.list(head(decisoes, 10)),
              motivos_negativa = as.list(head(motivos, 10)), grupos = grupos)
  .salvar_json(res, file.path(d$saida, sprintf("estruturado_%d_r.json", ano)))
  .log(sprintf("%d: %s pedidos | %d grupos", ano, format(n, big.mark = "."), length(grupos)))
  res
}

analisar_recursos <- function(ano) {
  caminho <- .arquivo_estruturado(ano, "Recursos")
  if (is.null(caminho)) return(list(ano = ano, erro = "arquivo de recursos não encontrado"))
  n <- nrow(.ler_csv(caminho, .cabecalho(caminho)[1]))
  list(ano = ano, recursos = n)
}

etapa_estruturada <- function(anos = CONF$anos_estruturado) {
  d <- .dirs(); res <- list()
  for (ano in anos) {
    if (is.null(.arquivo_estruturado(ano, "Pedidos"))) next
    a <- analisar_ano_estruturado(ano)
    r <- analisar_recursos(ano)
    if (!is.null(r$recursos)) {
      a$recursos <- r$recursos
      a$taxa_recurso_pct <- round(100 * r$recursos / max(a$pedidos, 1), 1)
    }
    res[[as.character(ano)]] <- a
  }
  .salvar_json(res, file.path(d$saida, "estruturado_serie_r.json"))
  invisible(res)
}

# ============================== 5. ANÁLISE TEXTUAL ==============================

normalizar_abertura <- function(texto, limite = CONF$limiar_caracteres_abertura) {
  t <- tolower(substr(ifelse(is.na(texto), "", texto), 1, limite))
  t <- gsub("[^a-z0-9 ]+", " ", t)
  trimws(gsub("\\s+", " ", t))
}

analisar_texto_ano <- function(ano, limiar = CONF$limiar_padronizacao) {
  d <- .dirs()
  alvos <- list.files(d$txt, pattern = sprintf("Pedidos_csv_%d\\.csv$", ano), full.names = TRUE)
  if (!length(alvos)) {
    .extrair(file.path(d$zips, sprintf("textos_%d.zip", ano)), d$txt, "Pedidos_csv")
    alvos <- list.files(d$txt, pattern = sprintf("Pedidos_csv_%d\\.csv$", ano), full.names = TRUE)
  }
  if (!length(alvos)) return(list(ano = ano, erro = "pacote de texto não disponível"))
  caminho <- alvos[1]
  cols <- .cabecalho(caminho)
  c_res <- .resolver(cols, "ResumoSolicitacao"); c_det <- .resolver(cols, "DetalhamentoSolicitacao")
  c_rsp <- .resolver(cols, "Resposta");          c_dec <- .resolver(cols, c("Decisao", "Decisão"))
  D <- .ler_csv(caminho, na.omit(c(c_res, c_det, c_rsp, c_dec)))
  n <- nrow(D)
  pct <- function(v) round(100 * sum(nzchar(v)) / max(n, 1), 1)
  r <- if (!is.null(c_res)) trimws(D[[c_res]]) else rep("", n)
  dd <- if (!is.null(c_det)) trimws(D[[c_det]]) else rep("", n)
  p <- if (!is.null(c_rsp)) trimws(D[[c_rsp]]) else rep("", n)
  nao_vazias <- p[nzchar(p)]
  aberturas <- normalizar_abertura(nao_vazias)
  tab <- table(aberturas)
  padronizadas <- sum(tab[tab >= limiar])
  res <- list(
    ano = ano, pedidos = n, pct_resumo = pct(r), pct_detalhamento = pct(dd), pct_resposta = pct(p),
    extensao_media_resumo = round(mean(nchar(r)), 0),
    extensao_media_resposta = round(mean(nchar(nao_vazias)), 0),
    extensao_mediana_resposta = as.numeric(median(nchar(nao_vazias))),
    aberturas_distintas = length(tab),
    pct_padronizada = round(100 * padronizadas / max(length(nao_vazias), 1), 1),
    limiar = limiar,
    maiores_aberturas = lapply(seq_len(min(3, length(tab))), function(i) {
      idx <- order(tab, decreasing = TRUE)[i]
      list(n = as.integer(tab[idx]), inicio = substr(names(tab)[idx], 1, 90))
    }),
    decisoes = if (!is.null(c_dec)) as.list(head(sort(table(D[[c_dec]]), decreasing = TRUE), 8)) else NULL
  )
  .salvar_json(res, file.path(d$serie_textual, sprintf("texto_%d_r.json", ano)))
  .log(sprintf("%d: %s pedidos | resposta %.0f car. | %.1f%% padronizada",
               ano, format(n, big.mark = "."), res$extensao_media_resposta, res$pct_padronizada))
  res
}

etapa_textual <- function(anos = CONF$anos_texto, limiar = CONF$limiar_padronizacao) {
  d <- .dirs(); res <- list()
  for (ano in anos) res[[as.character(ano)]] <- analisar_texto_ano(ano, limiar)
  .salvar_json(res, file.path(d$saida, "textual_serie_r.json"))
  invisible(res)
}

# --- contraste de robustez: TF-IDF + kmeans contra a decisão formal ---------------------
# ARI implementado à mão para não depender de pacote externo.
.indice_rand_ajustado <- function(a, b) {
  tb <- table(a, b)
  comb2 <- function(x) x * (x - 1) / 2
  soma_ij <- sum(comb2(tb)); soma_i <- sum(comb2(rowSums(tb))); soma_j <- sum(comb2(colSums(tb)))
  n <- sum(tb); total <- comb2(n)
  esperado <- soma_i * soma_j / total
  maximo <- (soma_i + soma_j) / 2
  (soma_ij - esperado) / (maximo - esperado)
}

contraste_agrupamento <- function(ano, k = 5, n_amostra = 12000) {
  d <- .dirs()
  alvos <- list.files(d$txt, pattern = sprintf("Pedidos_csv_%d\\.csv$", ano), full.names = TRUE)
  if (!length(alvos)) return(list(ano = ano, erro = "pacote não disponível"))
  cols <- .cabecalho(alvos[1])
  c_rsp <- .resolver(cols, "Resposta"); c_dec <- .resolver(cols, c("Decisao", "Decisão"))
  D <- .ler_csv(alvos[1], na.omit(c(c_rsp, c_dec)))
  D <- D[nzchar(trimws(D[[c_rsp]]))]
  set.seed(CONF$semente)
  D <- D[sample(.N, min(n_amostra, .N))]
  textos <- normalizar_abertura(D[[c_rsp]], limite = 400)
  # matriz de termos (TF-IDF simples, sem pacote de NLP)
  tokens <- strsplit(textos, " ")
  vocab <- sort(unique(unlist(tokens)))
  vocab <- vocab[nchar(vocab) > 2]
  m <- matrix(0L, nrow = length(tokens), ncol = length(vocab), dimnames = list(NULL, vocab))
  for (i in seq_along(tokens)) {
    idx <- match(tokens[[i]], vocab, nomatch = 0)
    idx <- idx[idx > 0]
    if (length(idx)) m[i, idx] <- 1L
  }
  tf <- sweep(m, 1, pmax(rowSums(m), 1), "/")
  idf <- log(nrow(m) / pmax(colSums(m > 0), 1))
  X <- tf * matrix(idf, nrow = nrow(tf), ncol = ncol(tf), byrow = TRUE)
  set.seed(CONF$semente)
  km <- kmeans(X, centers = k, nstart = 10, iter.max = 50)
  res <- list(ano = ano, n = nrow(D), k = k,
              ari_contra_decisao = round(.indice_rand_ajustado(D[[c_dec]], km$cluster), 3),
              tamanho_maior_cluster = max(km$size),
              observacao = "contraste de robustez; NÃO é instrumento de medida")
  .log(sprintf("contraste %d (k=%d): ARI contra decisão = %.3f", ano, k, res$ari_contra_decisao))
  res
}

# ============================== 6. VERIFICAÇÃO ==============================

ESPERADO_2025 <- list(
  "Executivo federal (ministérios e Presidência)" = 45296,
  "Autarquias, fundações e agências" = 43339,
  "Universidades e institutos federais" = 20703,
  "Estatais, bancos e empresas públicas" = 19262,
  "Esfera municipal" = 10246, "Esfera estadual" = 7134, "Controle interno" = 1852,
  "Conselhos profissionais" = 759, "Controle externo (tribunais de contas)" = 500,
  "Judiciário" = 378, "Legislativo" = 173, "Defensoria" = 34
)

etapa_verificacao <- function() {
  d <- .dirs()
  f <- file.path(d$saida, "estruturado_2025_r.json")
  est <- if (file.exists(f)) fromJSON(f, simplifyVector = FALSE) else analisar_ano_estruturado(2025)
  linhas <- lapply(names(ESPERADO_2025), function(g) {
    obtido <- if (!is.null(est$grupos[[g]]$pedidos)) as.integer(est$grupos[[g]]$pedidos) else 0L
    list(grupo = g, esperado = ESPERADO_2025[[g]], obtido = obtido,
         diferenca = obtido - ESPERADO_2025[[g]], bate = obtido == ESPERADO_2025[[g]])
  })
  divergentes <- sum(!vapply(linhas, function(l) l$bate, logical(1)))
  .salvar_json(list(divergentes = divergentes, linhas = linhas), file.path(d$saida, "verificacao_r.json"))
  .log(sprintf("verificação: %d de %d grupos divergem", divergentes, length(ESPERADO_2025)))
  invisible(linhas)
}

# ============================== 7. RELATÓRIO DISCORRIDO ==============================

etapa_relatorio <- function() {
  d <- .dirs(); saida <- file.path(d$saida, "ANALISES-DISCORRIDAS_r.md")
  L <- c("# LAI 15 anos — análises discorridas (R)", "",
         "*Gerado pelo pipeline em R. Todos os números vêm dos arquivos de `saida/` e `serie_textual/`.*",
         "", paste0("Gerado em: ", format(Sys.time(), "%d/%m/%Y %H:%M")), "")
  f_est <- file.path(d$saida, "estruturado_serie_r.json")
  if (file.exists(f_est)) {
    est <- fromJSON(f_est, simplifyVector = FALSE)
    L <- c(L, "## 1. Base estruturada", "")
    tot_ped <- sum(vapply(est, function(v) as.numeric(v$pedidos %||% 0), numeric(1)))
    L <- c(L, sprintf("A base reúne **%s pedidos** entre %s e %s.", format(tot_ped, big.mark = "."),
                      names(est)[1], names(est)[length(est)]), "")
    ult <- est[[length(est)]]
    if (!is.null(ult$grupos)) {
      L <- c(L, sprintf("### 1.1 Grupos de órgãos (%s)", names(est)[length(est)]), "",
             "| Grupo | Pedidos | Negado (%) | Concedido (%) |", "|---|---|---|---|")
      g <- ult$grupos
      ord <- order(-vapply(g, function(x) as.numeric(x$pedidos %||% 0), numeric(1)))
      for (nm in names(g)[ord]) {
        n <- max(as.numeric(g[[nm]]$pedidos %||% 1), 1)
        L <- c(L, sprintf("| %s | %s | %.1f | %.1f |", nm, format(as.numeric(g[[nm]]$pedidos), big.mark = "."),
                          100 * as.numeric(g[[nm]]$negado %||% 0) / n,
                          100 * as.numeric(g[[nm]]$concedido %||% 0) / n))
      }
      L <- c(L, "")
    }
  }
  f_txt <- file.path(d$saida, "textual_serie_r.json")
  if (file.exists(f_txt)) {
    txt <- fromJSON(f_txt, simplifyVector = FALSE)
    L <- c(L, "## 2. Base textual", "",
           "| Ano | Pedidos com texto | Resposta preenchida (%) | Extensão média | Padronizadas (%) |",
           "|---|---|---|---|---|")
    for (a in names(txt)) {
      v <- txt[[a]]
      L <- c(L, sprintf("| %s | %s | %s | %s | %s |", a, format(as.numeric(v$pedidos), big.mark = "."),
                        v$pct_resposta, v$extensao_media_resposta, v$pct_padronizada))
    }
    L <- c(L, "")
  }
  L <- c(L, "## 3. Limites declarados", "",
         "1. O pacote de textos é subconjunto publicado da base estruturada (cobertura medida, não suposta).",
         "2. O esquema de colunas é lido do arquivo: a página oficial está desatualizada.",
         "3. A medida de padronização depende do limiar declarado e do tamanho do conjunto.",
         "4. A taxonomia léxica é proxy; a versão anotada, com kappa, é etapa separada.", "")
  writeLines(L, saida)
  .log("relatório gravado: ", saida)
  invisible(saida)
}

`%||%` <- function(a, b) if (is.null(a)) b else a

# ============================== ATALHO ==============================

etapa_tudo <- function() {
  etapa_diagnostico(); etapa_estruturada(2025); etapa_verificacao()
  etapa_textual(c(2024), limiar = CONF$limiar_padronizacao)
  etapa_relatorio()
}

.log("pipeline LAI carregado. Raiz de trabalho: ", CONF$raiz)
.log("Funções: etapa_diagnostico, etapa_coleta, etapa_estruturada(ano), etapa_textual(ano), ",
     "contraste_agrupamento(ano), etapa_verificacao, etapa_relatorio, etapa_tudo")

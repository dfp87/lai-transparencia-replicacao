#!/usr/bin/env Rscript
# =============================================================================
# replicacao-artigo1.R
#
# Replicação da análise do artigo:
#   "Os guardiões fora do espelho: perímetro institucional e desempenho da
#    Lei de Acesso à Informação no Brasil (2012-2025)"
#
# O que este script faz:
#   (1) lê os 14 JSON anuais (evidencias/estruturado/estruturado_<ano>.json)
#       e o JSON da classificação AUDITADA de grupos (evidencias/p6_grupos_v3_2025.json);
#   (2) recalcula os indicadores: volume por ano, decisões, prazos (mediana, p90,
#       % acima de 20 dias) e a tabela por grupo de órgão (4 indicadores);
#   (3) escreve as tabelas em reprodutibilidade/saidas-R/ (CSV);
#   (4) gera as 5 figuras equivalentes em reprodutibilidade/figuras-R/ (PNG, 300 dpi);
#   (5) imprime um relatório de conferência em que cada número recalculado é
#       comparado com o que o artigo publica, marcado BATE ou DIFERE.
#
# SEGUNDA CAMADA (opcional): se os microdados brutos do Fala.BR/CGU estiverem
# em /root/lai/csv (CSVs UTF-16, um por ano), o script RECALCULA volume,
# decisões e prazos diretamente do microdado, como verificação independente dos
# JSON. Sem os microdados, o script roda só com os JSON (e avisa). As duas
# leituras são da MESMA base; a segunda serve para provar que os JSON não
# escondem erro de leitura.
#
# Requisitos: R + pacote jsonlite (install.packages("jsonlite")).
#             data.table e o utilitário de sistema `iconv` são usados apenas na
#             segunda camada (microdados); se faltarem, o script segue com JSON.
#
# Uso:  Rscript replicacao-artigo1.R
# =============================================================================

# ------------------------- 0. Configuração e utilidades ----------------------

# Diretório-raiz do projeto. Pode ser sobrescrito pela variável de ambiente LAI_RAIZ.
# Raiz do projeto: por padrao, a pasta que contem este script (o repositorio);
# pode ser sobrescrita pela variavel de ambiente LAI_RAIZ.
.args <- commandArgs(trailingOnly = FALSE)
.fica <- grep("^--file=", .args, value = TRUE)
.dir_script <- if (length(.fica)) dirname(normalizePath(sub("^--file=", "", .fica[1]))) else getwd()
BASE <- Sys.getenv("LAI_RAIZ", unset = dirname(.dir_script))
DIR_EV   <- file.path(BASE, "evidencias")
DIR_EST  <- file.path(DIR_EV, "estruturado")
ARQ_GRUPOS <- file.path(DIR_EV, "p6_grupos_v3_2025.json")   # classificação auditada (v3), 2025
DIR_MICRO  <- Sys.getenv("LAI_MICRO", unset = "/root/lai/csv")                               # microdados brutos (opcional)

DIR_SAIDAS <- file.path(BASE, "reprodutibilidade", "saidas-R")
DIR_FIGS   <- file.path(BASE, "reprodutibilidade", "figuras-R")
dir.create(DIR_SAIDAS, showWarnings = FALSE, recursive = TRUE)
dir.create(DIR_FIGS,   showWarnings = FALSE, recursive = TRUE)

ANOS <- 2012:2025

# --- Leitura de JSON tolerante: o arquivo de grupos traz o literal NaN, que o
#     parser estrito do jsonlite recusa; trocamos por null (=> NA no R).
ler_json <- function(caminho) {
  txt <- readLines(caminho, warn = FALSE, encoding = "UTF-8")
  txt <- gsub("NaN", "null", txt, fixed = TRUE)
  jsonlite::fromJSON(paste(txt, collapse = "\n"))
}

# --- Impressão e conferência -----------------------------------------------
CONF <- list()   # acumula as linhas do relatório de conferência

check <- function(bloco, item, indicador, artigo, calc, dec = 1, exato = FALSE) {
  ausente_art <- is.null(artigo) || length(artigo) == 0 || is.na(artigo)
  ausente_cal <- is.null(calc)   || length(calc)   == 0 || is.na(calc)
  if (ausente_art && ausente_cal) {
    ver <- "BATE"; most_cal <- NA_real_
  } else if (ausente_art || ausente_cal) {
    ver <- "DIFERE"; most_cal <- if (ausente_cal) NA_real_ else round(calc, dec)
  } else if (exato) {
    ver <- ifelse(as.integer(round(calc)) == as.integer(round(artigo)), "BATE", "DIFERE")
    most_cal <- as.integer(round(calc))
  } else {
    ver <- ifelse(round(calc, dec) == round(artigo, dec), "BATE", "DIFERE")
    most_cal <- round(calc, dec)
  }
  CONF[[length(CONF) + 1]] <<- data.frame(
    bloco = bloco, item = item, indicador = indicador,
    artigo = artigo, recalculado = most_cal, veredito = ver, stringsAsFactors = FALSE)
  invisible(ver)
}

n_br <- function(x, dec = 0) {                 # número no padrão brasileiro
  formatC(x, format = "f", digits = dec, decimal.mark = ",", big.mark = ".")
}

cat("========================================================================\n")
cat(" Replicação — 'Os guardiões fora do espelho' (LAI, 2012-2025)\n")
cat(" Base:", BASE, "\n")
cat(" Data/hora:", format(Sys.time(), "%d/%m/%Y %H:%M:%S"), "\n")
cat("========================================================================\n\n")

# =============================================================================
# 1. Leitura dos 14 JSON anuais + do JSON de grupos
# =============================================================================
cat("[1] Lendo os 14 JSON anuais e o de grupos auditados...\n")

EST <- list()                       # EST[["2012"]] = lista do JSON do ano
for (a in ANOS) {
  arq <- file.path(DIR_EST, sprintf("estruturado_%d.json", a))
  if (!file.exists(arq)) stop("JSON anual ausente: ", arq)
  EST[[as.character(a)]] <- ler_json(arq)
}
cat("    JSON lidos:", length(EST), "anos (",
    min(ANOS), "-", max(ANOS), ")\n")

GRUPOS <- ler_json(ARQ_GRUPOS)      # data.frame: grupo, pedidos, med, p20, neg, con, pro, pct
stopifnot(is.data.frame(GRUPOS), nrow(GRUPOS) == 14)
cat("    Grupos auditados (v3, 2025) lidos:", nrow(GRUPOS), "grupos;",
    "soma de pedidos =", n_br(sum(GRUPOS$pedidos)), "\n\n")

# =============================================================================
# 2. Recalculo dos indicadores a partir dos JSON
# =============================================================================

# --- 2a. Volume, decisões e prazos, ano a ano -------------------------------
serie <- data.frame(
  ano             = ANOS,
  pedidos         = NA_integer_,
  n_prazo         = NA_integer_,
  mediana_dias    = NA_real_,
  p90_dias        = NA_real_,
  pct_acima_20    = NA_real_,
  n_decisoes      = NA_integer_,
  acesso_negado   = NA_integer_,
  stringsAsFactors = FALSE)

decisoes_longa <- list()   # decisões por ano, em formato longo (para CSV)
for (i in seq_along(ANOS)) {
  a  <- ANOS[i]
  j  <- EST[[as.character(a)]]
  pr <- j$prazos
  serie$pedidos[i]      <- as.integer(j$pedidos)
  serie$n_prazo[i]      <- as.integer(pr$n)
  serie$mediana_dias[i] <- as.numeric(pr$mediana)
  serie$p90_dias[i]     <- as.numeric(pr$p90)
  serie$pct_acima_20[i] <- as.numeric(pr$pct_acima_20)

  dec <- j$decisoes
  if (length(dec) > 0) {
    df <- data.frame(ano = a, decisao = names(dec),
                     n = as.integer(unlist(dec)), stringsAsFactors = FALSE)
    # a decisão " " (vazia) marca registros sem data válida
    df$decisao[trimws(df$decisao) == ""] <- "(sem data válida)"
    decisoes_longa[[length(decisoes_longa) + 1]] <- df
    serie$n_decisoes[i]    <- sum(df$n)
    serie$acesso_negado[i] <- sum(df$n[df$decisao == "Acesso Negado"])
  }
}
decisoes_longa <- do.call(rbind, decisoes_longa)
rownames(decisoes_longa) <- NULL

cat("[2a] Volume, decisões e prazos recalculados dos JSON anuais.\n")
print(serie, row.names = FALSE)
cat("\n")

# --- 2b. Soma dos catorze anos ----------------------------------------------
soma_14 <- sum(serie$pedidos)
cat("[2b] Soma dos catorze anos:", n_br(soma_14), "pedidos\n\n")

# --- 2c. Tabela por grupo (classificação auditada v3, 2025) ------------------
total_grupos <- sum(GRUPOS$pedidos)
tab_grupos <- data.frame(
  grupo            = GRUPOS$grupo,
  pedidos          = as.integer(GRUPOS$pedidos),
  pct_do_acervo    = 100 * GRUPOS$pedidos / total_grupos,   # % recalculada
  mediana_dias     = as.numeric(GRUPOS$med),
  pct_acima_20     = as.numeric(GRUPOS$p20),
  pct_negativa     = as.numeric(GRUPOS$neg),
  stringsAsFactors = FALSE)

# Linha de total: pedidos somados; prazos globais de 2025; negativa agregada
# ponderada pelo volume de cada grupo (é a soma de negados / soma de pedidos).
prazo_2025 <- EST[["2025"]]$prazos
neg_ponderada <- sum(GRUPOS$neg * GRUPOS$pedidos) / total_grupos
tab_total <- data.frame(
  grupo = "Total", pedidos = total_grupos, pct_do_acervo = 100,
  mediana_dias = as.numeric(prazo_2025$mediana),
  pct_acima_20 = as.numeric(prazo_2025$pct_acima_20),
  pct_negativa = neg_ponderada, stringsAsFactors = FALSE)

cat("[2c] Tabela por grupo (v3) recalculada. Total negativo (ponderado) =",
    n_br(neg_ponderada, 1), "%\n\n")

# --- 2d. Parcela dos órgãos de controle/justiça por ano (série G4/G5) --------
# Mesma definição da figura do artigo: soma de (Controle interno, Controle
# externo, Judiciário, Legislativo, Defensoria) / total de pedidos do ano,
# usando a classificação POR ANO embutida nos JSON estruturados.
CHAVES_GUARDIOES <- c("Controle interno", "Controle externo",
                      "Judiciário", "Legislativo", "Defensoria")
parcela <- data.frame(ano = ANOS, guardioes = NA_integer_,
                      total = NA_integer_, parcela_pct = NA_real_,
                      stringsAsFactors = FALSE)
for (i in seq_along(ANOS)) {
  g <- EST[[as.character(ANOS[i])]]$grupos
  tot <- sum(sapply(g, function(x) as.numeric(x$pedidos)))
  gd  <- sum(sapply(CHAVES_GUARDIOES, function(k) {
    v <- g[[k]]; if (is.null(v)) 0 else as.numeric(v$pedidos) }))
  parcela$guardioes[i]    <- as.integer(gd)
  parcela$total[i]        <- as.integer(tot)
  parcela$parcela_pct[i]  <- 100 * gd / tot
}
cat("[2d] Parcela dos guardiões recalculada (",
    sprintf("%.2f%%", min(parcela$parcela_pct)), "a",
    sprintf("%.2f%%", max(parcela$parcela_pct)), ").\n\n")

# =============================================================================
# 3. Segunda camada (opcional): recalculo direto do MICRODADO
# =============================================================================
micro <- NULL
tem_micro <- dir.exists(DIR_MICRO) &&
  any(file.exists(file.path(DIR_MICRO, sprintf("20260915_Pedidos_csv_%d.csv", ANOS))))
if (tem_micro && requireNamespace("data.table", quietly = TRUE)) {
  cat("[3] Microdados encontrados:", DIR_MICRO, "- recalculando do microdado...\n")
  micro <- data.frame(ano = ANOS, pedidos_micro = NA_integer_,
                      n_prazo_micro = NA_integer_, mediana_micro = NA_real_,
                      p90_micro = NA_real_, pct_acima_20_micro = NA_real_,
                      negado_micro = NA_integer_, pct_federal_micro = NA_real_,
                      stringsAsFactors = FALSE)
  for (i in seq_along(ANOS)) {
    a <- ANOS[i]
    arq16 <- file.path(DIR_MICRO, sprintf("20260915_Pedidos_csv_%d.csv", a))
    arq8  <- file.path(DIR_MICRO, sprintf("utf8_20260915_Pedidos_csv_%d.csv", a))
    tmp <- NULL
    if (file.exists(arq8)) {
      alvo <- arq8
    } else if (file.exists(arq16)) {
      tmp <- tempfile(fileext = ".csv")
      system2("iconv", c("-f", "UTF-16", "-t", "UTF-8",
                          shQuote(arq16), "-o", shQuote(tmp)))
      alvo <- tmp
    } else next
    d <- tryCatch(data.table::fread(alvo, sep = ";", encoding = "UTF-8",
                                    quote = "\"", showProgress = FALSE),
                  error = function(e) NULL)
    if (!is.null(tmp)) unlink(tmp)
    if (is.null(d) || nrow(d) == 0) next
    dias <- as.numeric(as.Date(d$DataResposta, format = "%d/%m/%Y") -
                         as.Date(d$DataRegistro, format = "%d/%m/%Y"))
    ok <- dias[!is.na(dias)]
    micro$pedidos_micro[i]      <- nrow(d)
    micro$n_prazo_micro[i]      <- length(ok)
    micro$mediana_micro[i]      <- if (length(ok)) median(ok) else NA_real_
    micro$p90_micro[i]          <- if (length(ok)) unname(quantile(ok, 0.9)) else NA_real_
    micro$pct_acima_20_micro[i] <- if (length(ok)) 100 * mean(ok > 20) else NA_real_
    micro$negado_micro[i]       <- sum(d$Decisao == "Acesso Negado", na.rm = TRUE)
    micro$pct_federal_micro[i]  <- 100 * mean(d$Esfera == "Federal", na.rm = TRUE)
  }
  # conferência microdado x JSON
  micro$bate_pedidos <- as.integer(micro$pedidos_micro == serie$pedidos)
  micro$bate_pct20   <- as.integer(round(micro$pct_acima_20_micro, 1) == round(serie$pct_acima_20, 1))
  cat("    Microdado x JSON — pedidos iguais em", sum(micro$bate_pedidos, na.rm = TRUE),
      "de", length(ANOS), "anos; %acima20 iguais em",
      sum(micro$bate_pct20, na.rm = TRUE), "anos.\n")
  print(micro[, c("ano","pedidos_micro","mediana_micro","p90_micro","pct_acima_20_micro","negado_micro")],
        row.names = FALSE)
  cat("\n")
} else {
  cat("[3] Microdados ausentes em", DIR_MICRO,
      "ou pacote data.table indisponível — segunda camada ignorada.\n",
      "    (Os indicadores seguem recalculados dos JSON anuais.)\n\n")
}

# =============================================================================
# 4. Escrita das tabelas em CSV (reprodutibilidade/saidas-R/)
# =============================================================================
cat("[4] Escrevendo tabelas em", DIR_SAIDAS, "...\n")
write.csv(serie,          file.path(DIR_SAIDAS, "serie-anual_R.csv"),        row.names = FALSE)
write.csv(decisoes_longa, file.path(DIR_SAIDAS, "decisoes-por-ano_R.csv"),   row.names = FALSE)
write.csv(rbind(tab_grupos, tab_total),
          file.path(DIR_SAIDAS, "tabela-grupos-2025_R.csv"),                 row.names = FALSE)
write.csv(parcela,        file.path(DIR_SAIDAS, "parcela-guardioes_R.csv"),  row.names = FALSE)
if (!is.null(micro)) {
  write.csv(micro,        file.path(DIR_SAIDAS, "microdados-conferencia_R.csv"), row.names = FALSE)
}
cat("    OK.\n\n")

# =============================================================================
# 5. Figuras (base R, PNG 300 dpi) em reprodutibilidade/figuras-R/
# =============================================================================
cat("[5] Gerando as 5 figuras em", DIR_FIGS, "...\n")

abrir_png <- function(caminho, w, h) {
  if (isTRUE(capabilities("cairo"))) {
    png(caminho, width = w, height = h, units = "in", res = 300, type = "cairo")
  } else {
    png(caminho, width = w, height = h, units = "in", res = 300)
  }
}

# rótulos curtos para o eixo, como nas figuras do artigo
rotulo <- function(g) {
  mapa <- c("Executivo federal (ministérios e presidência)" = "Executivo federal",
            "Autarquias, fundações e agências"             = "Autarquias, fund. e agências",
            "Universidades e institutos federais"           = "Universidades e institutos",
            "Estatais, bancos e empresas públicas"          = "Estatais e bancos",
            "Esfera municipal"                              = "Municipal",
            "Esfera estadual"                               = "Estadual",
            "Controle interno (CGU/CGE/CGM)"                = "Controle interno",
            "Conselhos profissionais"                        = "Conselhos profissionais",
            "Controle externo (TCU/TCE/TCM)"                = "Controle externo (estaduais)",
            "Judiciário"                                     = "Judiciário",
            "Serviços autônomos e sociais"                   = "Serviços autônomos",
            "Legislativo"                                    = "Legislativo",
            "Outros federais"                                = "Outros federais",
            "Defensoria"                                     = "Defensoria")
  ifelse(g %in% names(mapa), mapa[g], g)
}

# barras horizontais ordenadas a partir de um campo da tabela de grupos
barras_h <- function(campo, titulo, xlabel, arquivo, cor, dec = 1, sinal = "%") {
  d <- tab_grupos[!is.na(tab_grupos[[campo]]), ]
  d <- d[order(d[[campo]]), ]                       # crescente: menor embaixo, maior no topo
  abrir_png(arquivo, 7.2, 5.0)
  op <- par(mar = c(4.2, 8.5, 3.0, 1.2))
  bp <- as.vector(barplot(d[[campo]], names.arg = rotulo(d$grupo), horiz = TRUE, las = 1,
                col = cor, border = "#333333", xlim = c(0, max(d[[campo]]) * 1.18),
                xlab = xlabel, main = titulo, cex.names = 0.8, cex.axis = 0.85))
  text(x = d[[campo]], y = bp, labels = paste0(n_br(d[[campo]], dec), sinal),
       pos = 4, cex = 0.8, xpd = NA)
  par(op); dev.off()
  cat("    ->", basename(arquivo), "\n")
}

# G1 — % de respostas acima de 20 dias por grupo (2025)
barras_h("pct_acima_20",
         "% de respostas acima de 20 dias, por grupo de órgão (2025)",
         "Respostas acima de 20 dias (%)",
         file.path(DIR_FIGS, "G1_grupos-acima-de-20-dias_R.png"), "#a4262c")

# G2 — % de negativa integral por grupo (2025)
barras_h("pct_negativa",
         "Negativa integral por grupo de órgão (2025)",
         "Negativa integral (%)",
         file.path(DIR_FIGS, "G2_grupos-negativa_R.png"), "#c55a11")

# G3 — volume por grupo (2025), ordem decrescente
{
  d <- tab_grupos[order(tab_grupos$pedidos, decreasing = TRUE), ]
  abrir_png(file.path(DIR_FIGS, "G3_grupos-volume_R.png"), 7.2, 5.0)
  op <- par(mar = c(6.2, 4.4, 3.0, 1.2))
  bp <- as.vector(barplot(d$pedidos, names.arg = rotulo(d$grupo), las = 2,
                col = "#1f4e79", border = "#333333", ylim = c(0, max(d$pedidos) * 1.15),
                ylab = paste0("Pedidos no ano (n = ", n_br(sum(d$pedidos)), ")"),
                main = "Onde está o acervo da LAI: pedidos por grupo de órgão (2025)",
                cex.names = 0.72, cex.axis = 0.85))
  text(bp, d$pedidos, labels = n_br(d$pedidos), pos = 3, cex = 0.66, xpd = NA)
  par(op); dev.off()
  cat("    -> G3_grupos-volume_R.png\n")
}

# G4 — série anual de pedidos (2012-2025)
{
  abrir_png(file.path(DIR_FIGS, "G4_serie-de-pedidos_R.png"), 7.2, 4.4)
  op <- par(mar = c(4.2, 4.6, 3.0, 1.2))
  bp <- barplot(serie$pedidos, names.arg = serie$ano, las = 1,
                col = "#c9d6e4", border = "#5b7fa6", ylim = c(0, max(serie$pedidos) * 1.15),
                xlab = "Ano de registro do pedido", ylab = "Pedidos de acesso",
                main = "Pedidos de acesso à informação no Brasil, 2012-2025",
                cex.axis = 0.85)
  destaques <- c(1, which(serie$pedidos == max(serie$pedidos)), length(serie$pedidos))
  text(bp[destaques], serie$pedidos[destaques], labels = n_br(serie$pedidos[destaques]),
       pos = 3, cex = 0.78, xpd = NA)
  par(op); dev.off()
  cat("    -> G4_serie-de-pedidos_R.png\n")
}

# G5 — parcela dos órgãos de controle/justiça por ano
{
  abrir_png(file.path(DIR_FIGS, "G5_parcela-guardioes_R.png"), 7.2, 4.4)
  op <- par(mar = c(4.2, 4.6, 3.0, 1.2))
  plot(parcela$ano, parcela$parcela_pct, type = "b", pch = 19, lwd = 1.9,
       col = "#5b2d8e", ylim = c(0, max(parcela$parcela_pct) * 1.6),
       xlab = "Ano de registro do pedido", ylab = "Parcela dos pedidos (%)",
       main = "A parcela dos órgãos de controle e de justiça no acervo da LAI")
  text(parcela$ano[1], parcela$parcela_pct[1],
       sprintf("%.2f%%", parcela$parcela_pct[1]), pos = 3, cex = 0.75, col = "#5b2d8e")
  i_fim <- nrow(parcela)
  text(parcela$ano[i_fim], parcela$parcela_pct[i_fim],
       sprintf("%.2f%%", parcela$parcela_pct[i_fim]), pos = 3, cex = 0.75, col = "#5b2d8e")
  legend("topleft", bty = "n", cex = 0.8,
         legend = "Controle interno e externo, Judiciário, Legislativo e Defensoria")
  par(op); dev.off()
  cat("    -> G5_parcela-guardioes_R.png\n")
}
cat("\n")

# =============================================================================
# 6. Relatório de conferência: recalculado x publicado (BATE/DIFERE)
# =============================================================================
cat("[6] Conferência contra os números publicados no artigo...\n\n")

# --- 6a. Indicadores globais de 2025 ----------------------------------------
check("Globais 2025", "Total de pedidos",        "pedidos",      150189, serie$pedidos[serie$ano == 2025], exato = TRUE)
check("Globais 2025", "Respostas com data válida","n prazo",     148681, serie$n_prazo[serie$ano == 2025], exato = TRUE)
check("Globais 2025", "Mediana de resposta",     "dias",         13,     serie$mediana_dias[serie$ano == 2025], dec = 1)
check("Globais 2025", "p90 de resposta",         "dias",         30,     serie$p90_dias[serie$ano == 2025], dec = 1)
check("Globais 2025", "Respostas acima de 20 dias","%",          26.2,   serie$pct_acima_20[serie$ano == 2025], dec = 1)

# --- 6b. Série anual (âncoras publicadas) e soma dos catorze anos -----------
ancoras <- c("2012" = 55212, "2015" = 102423, "2020" = 154079, "2025" = 150189)
for (a in names(ancoras)) {
  check("Série anual", paste("Pedidos em", a), "pedidos", ancoras[[a]],
        serie$pedidos[serie$ano == as.integer(a)], exato = TRUE)
}
check("Série anual", "Soma 2012-2025", "pedidos", 1641939, soma_14, exato = TRUE)

# --- 6c. Quadro 1 — tabela por grupo (v3, 2025) -----------------------------
# valores publicados: pedidos, % do acervo, mediana, % acima de 20, % negativa
pub <- data.frame(
  grupo = c("Executivo federal (ministérios e presidência)",
            "Autarquias, fundações e agências",
            "Universidades e institutos federais",
            "Estatais, bancos e empresas públicas",
            "Esfera municipal", "Esfera estadual",
            "Controle interno (CGU/CGE/CGM)", "Conselhos profissionais",
            "Controle externo (TCU/TCE/TCM)", "Judiciário",
            "Serviços autônomos e sociais", "Legislativo",
            "Outros federais", "Defensoria"),
  pedidos = c(45296, 43339, 20703, 19262, 10246, 7134, 1852, 759, 500, 378, 377, 173, 136, 34),
  pct     = c(30.2, 28.9, 13.8, 12.8, 6.8, 4.8, 1.2, 0.5, 0.3, 0.3, 0.3, 0.1, 0.1, 0.0),
  med     = c(16, 10, 13, 8, 14, 15, 21, 6, 1, 15, 10, NA, 14, 104.5),
  p20     = c(31.5, 19.8, 28.2, 15.4, 35.4, 38.4, 58.8, 11.7, 1.6, 33.1, 23.9, NA, 28.7, 73.5),
  neg     = c(8.4, 6.8, 4.1, 14.8, 3.0, 4.0, 9.7, 7.5, 0.6, 14.0, 6.9, 0.0, 3.7, 2.9),
  stringsAsFactors = FALSE)

for (k in seq_len(nrow(pub))) {
  g  <- pub$grupo[k]
  rc <- tab_grupos[tab_grupos$grupo == g, ]
  if (nrow(rc) == 0) { check("Quadro 1", g, "presente", NA, NA); next }
  check("Quadro 1", g, "pedidos",     pub$pedidos[k], rc$pedidos,       exato = TRUE)
  check("Quadro 1", g, "% do acervo", pub$pct[k],     rc$pct_do_acervo, dec = 1)
  check("Quadro 1", g, "mediana",     pub$med[k],     rc$mediana_dias,  dec = 1)
  check("Quadro 1", g, "% acima20",   pub$p20[k],     rc$pct_acima_20,  dec = 1)
  check("Quadro 1", g, "% negativa",  pub$neg[k],     rc$pct_negativa,  dec = 1)
}
# linha de total do Quadro 1
check("Quadro 1 (total)", "Total", "pedidos",   150189, tab_total$pedidos,       exato = TRUE)
check("Quadro 1 (total)", "Total", "% do acervo", 100.0, tab_total$pct_do_acervo,  dec = 1)
check("Quadro 1 (total)", "Total", "mediana",   13,     tab_total$mediana_dias,   dec = 1)
check("Quadro 1 (total)", "Total", "% acima20", 26.2,   tab_total$pct_acima_20,   dec = 1)
check("Quadro 1 (total)", "Total", "% negativa", 7.6,   tab_total$pct_negativa,   dec = 1)

# --- 6d. Parcela dos guardiões (extremos publicados) ------------------------
ano_min <- parcela$ano[which.min(parcela$parcela_pct)]
ano_max <- parcela$ano[which.max(parcela$parcela_pct)]
check("Parcela guardiões", paste0("Mínimo (", ano_min, ")"), "%", 0.96,
      min(parcela$parcela_pct), dec = 2)
check("Parcela guardiões", paste0("Máximo (", ano_max, ")"), "%", 2.25,
      max(parcela$parcela_pct), dec = 2)

# --- 6e. Esfera federal em 2025 (publicado: 86,8%) --------------------------
if (!is.null(micro)) {
  check("Perímetro 2025", "% de esfera federal", "%", 86.8,
        micro$pct_federal_micro[micro$ano == 2025], dec = 1)
}

# --- 6f. Impressão do relatório --------------------------------------------
conf_df <- do.call(rbind, CONF)
rownames(conf_df) <- NULL
n_bate <- sum(conf_df$veredito == "BATE")
n_dif  <- sum(conf_df$veredito == "DIFERE")
conf_df$artigo[is.na(conf_df$artigo)] <- "—"
conf_df$recalculado[is.na(conf_df$recalculado)] <- "—"

cat(sprintf("%-18s %-44s %-12s %10s %11s %8s\n",
            "BLOCO", "ITEM", "INDICADOR", "ARTIGO", "RECALC.", "VEREDITO"))
cat(strrep("-", 110), "\n")
for (i in seq_len(nrow(conf_df))) {
  cat(sprintf("%-18s %-44s %-12s %10s %11s %8s\n",
              conf_df$bloco[i], substr(conf_df$item[i], 1, 44),
              conf_df$indicador[i], conf_df$artigo[i],
              conf_df$recalculado[i], conf_df$veredito[i]))
}
cat(strrep("-", 110), "\n\n")

cat("RESUMO DA CONFERÊNCIA\n")
cat("  Comparações:", nrow(conf_df), "\n")
cat("  BATE   :", n_bate, "\n")
cat("  DIFERE :", n_dif, "\n\n")

if (n_dif > 0) {
  cat("DIVERGÊNCIAS (não ajustadas — o dado manda):\n")
  dif <- conf_df[conf_df$veredito == "DIFERE", ]
  for (i in seq_len(nrow(dif))) {
    cat(sprintf("  - [%s] %s / %s : artigo = %s, recalculado = %s\n",
                dif$bloco[i], dif$item[i], dif$indicador[i],
                dif$artigo[i], dif$recalculado[i]))
  }
  cat("\n")
}

# grava o relatório
write.csv(conf_df, file.path(DIR_SAIDAS, "conferencia_R.csv"), row.names = FALSE)

cat("Saídas: ", DIR_SAIDAS, "\n")
cat("Figuras:", DIR_FIGS, "\n")
cat("========================================================================\n")
cat(" FIM — ", n_bate, " BATE / ", n_dif, " DIFERE\n", sep = "")
cat("========================================================================\n")

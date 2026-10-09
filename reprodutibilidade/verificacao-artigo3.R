# =============================================================================
# Conferência INDEPENDENTE (R) dos números publicados no artigo 3
# "A resposta inteira" (v1, 09/10/2026)
#
# Roda só com o pacote jsonlite. Recalcula, de outra linguagem, tudo o que o
# artigo afirma: as duas unidades de medida, os grupos de órgãos, a série de
# plataformização e as correlações. Compara item a item com o valor publicado e
# imprime BATE ou DIFERE. Nenhuma dependência do código Python.
#
# Uso:  Rscript verificacao-artigo3.R
# =============================================================================
suppressMessages(library(jsonlite))
options(stringsAsFactors = FALSE)

AQUI <- tryCatch(dirname(normalizePath(sub("^--file=", "",
          grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1]))), error = function(e) getwd())
RAIZ <- dirname(AQUI)
ANOS <- 2015:2025

comparacoes <- 0; difere <- 0; notas <- character(0)
check <- function(ctx, item, unidade, publicado, recalc, dec = 2) {
  comparacoes <<- comparacoes + 1
  p <- round(as.numeric(publicado), dec); r <- round(as.numeric(recalc), dec)
  ok <- isTRUE(all.equal(p, r, tolerance = 10 ^ (-dec) * 2))
  if (!ok) difere <<- difere + 1
  cat(sprintf("%-42s %-26s %-4s %10s %10s   %s\n", ctx, item, unidade,
              format(p, nsmall = dec), format(r, nsmall = dec), if (ok) "BATE" else "*** DIFERE ***"))
  invisible(ok)
}

# --------------------------------------------------------------- 1. LEITURA
cat("\n", strrep("=", 108), "\n 1. LEITURA DAS EVIDÊNCIAS\n", strrep("=", 108), "\n", sep = "")
inteira <- list()
for (a in ANOS) {
  f <- file.path(RAIZ, "reprodutibilidade", "saidas-minhash", sprintf("minhash_inteira_%d.json", a))
  if (file.exists(f)) inteira[[as.character(a)]] <- fromJSON(f, simplifyVector = FALSE)
}
cons_jan <- fromJSON(file.path(RAIZ, "reprodutibilidade", "saidas-minhash", "consolidado_minhash_FINAL.json"),
                     simplifyVector = FALSE)
grupo <- list()
for (a in ANOS) {
  f <- file.path(RAIZ, "reprodutibilidade", "saidas-grupo-ano", sprintf("grupo-ano_%d.json", a))
  if (file.exists(f)) grupo[[as.character(a)]] <- fromJSON(f, simplifyVector = FALSE)
}
canal <- fromJSON(file.path(RAIZ, "evidencias", "canal_entrega.json"), simplifyVector = FALSE)

cat("anos com medição da resposta inteira:", length(inteira), "|",
    "anos com medição por grupo:", length(grupo), "|",
    "anos de canal de entrega:", length(canal), "\n")

# helper: média ponderada de um campo por ano
pond <- function(lst, campo) {
  num <- 0; den <- 0
  for (k in names(lst)) {
    n <- lst[[k]]$respostas_com_texto
    v <- lst[[k]][[campo]]
    if (!is.null(v) && !is.null(n) && n > 0) { num <- num + v * n; den <- den + n }
  }
  if (den == 0) NA else num / den
}
por_ano_g <- function(campo) sapply(names(inteira), function(k) inteira[[k]][[campo]])
jan <- function(a, campo) cons_jan$por_ano[[as.character(a)]][[campo]]

# ------------------------------------------------- 2. TOTAIS E AS DUAS MEDIDAS
cat("\n", strrep("=", 108), "\n 2. TOTAIS E AS DUAS UNIDADES DE MEDIDA\n", strrep("=", 108), "\n", sep = "")
total <- sum(sapply(inteira, function(x) x$respostas_com_texto))
check("Corpus", "respostas com texto (2015-2025)", "n", 938987, total, 0)

lit_jan <- sapply(ANOS, function(a) jan(a, "md5_250_pct"))
qse_jan <- sapply(ANOS, function(a) jan(a, "minhash_final_pct"))
lit_int <- sapply(ANOS, function(a) inteira[[as.character(a)]]$literal_inteira_md5$pct)
qse_int <- sapply(ANOS, function(a) inteira[[as.character(a)]]$minhash$pct)
pesos   <- sapply(ANOS, function(a) inteira[[as.character(a)]]$respostas_com_texto)

wp <- function(v) round(sum(v * pesos) / sum(pesos), 2)
check("Repetição literal", "média ponderada — janela 250", "%", 20.64, wp(lit_jan))
check("Repetição literal", "média ponderada — resposta inteira", "%", 14.86, wp(lit_int))
check("Quase-repetição", "média ponderada — janela 250", "%", 22.55, wp(qse_jan))
check("Quase-repetição", "média ponderada — resposta inteira", "%", 24.21, wp(qse_int))

# série ano a ano, como publicada na Tabela A
pub_lit_jan <- c(20.86, 21.21, 19.98, 18.95, 14.93, 24.69, 21.50, 21.25, 22.74, 20.28, 20.42)
pub_lit_int <- c(16.66, 16.71, 17.20, 14.42,  9.43, 20.20, 14.92, 13.27, 13.58, 12.64, 13.41)
pub_qse_jan <- c(24.75, 25.24, 20.85, 22.84, 20.13, 20.60, 21.33, 25.64, 24.42, 22.46, 21.57)
pub_qse_int <- c(30.56, 29.57, 22.82, 23.76, 21.71, 23.13, 24.84, 28.91, 23.76, 19.78, 20.09)
for (i in seq_along(ANOS)) {
  check(sprintf("Ano %d", ANOS[i]), "literal — janela 250", "%", pub_lit_jan[i], lit_jan[i])
  check(sprintf("Ano %d", ANOS[i]), "literal — resposta inteira", "%", pub_lit_int[i], lit_int[i])
  check(sprintf("Ano %d", ANOS[i]), "quase — janela 250", "%", pub_qse_jan[i], qse_jan[i])
  check(sprintf("Ano %d", ANOS[i]), "quase — resposta inteira", "%", pub_qse_int[i], qse_int[i])
}

# diferenças citadas no texto
d <- round(lit_int - lit_jan, 2)
check("Viés da janela (literal)", "2015", "p.p.", -4.20, d[1])
check("Viés da janela (literal)", "2023", "p.p.", -9.16, d[which(ANOS == 2023)])
check("Viés da janela (literal)", "2025", "p.p.", -7.01, d[which(ANOS == 2025)])

# cauda dos baldes
maior <- sapply(ANOS, function(a) inteira[[as.character(a)]]$minhash$maior_grupo)
check("Cauda dos baldes", "maior grupo de repetição — 2015", "n", 454, maior[1], 0)
check("Cauda dos baldes", "maior grupo de repetição — 2022", "n", 870, maior[which(ANOS == 2022)], 0)
check("Cauda dos baldes", "maior grupo de repetição — 2025", "n", 565, maior[which(ANOS == 2025)], 0)

# -------------------------------------------------- 3. SÉRIE POR GRUPO DE ÓRGÃO
cat("\n", strrep("=", 108), "\n 3. PADRONIZAÇÃO POR GRUPO DE ÓRGÃO\n", strrep("=", 108), "\n", sep = "")
gval <- function(ano, grupo_busca, campo) {
  for (g in grupo[[as.character(ano)]]$grupos)
    if (identical(g$grupo, grupo_busca)) return(g[[campo]])
  NA
}
gvol <- function(grupo_busca) sum(sapply(ANOS, function(a) {
  v <- gval(a, grupo_busca, "respostas"); if (is.na(v)) 0 else v }))
grupos <- c("Autarquias, fundações e agências",
            "Executivo federal (ministérios e Presidência)",
            "Universidades e institutos federais",
            "Estatais, bancos e empresas públicas",
            "Controle interno")
pub_vol <- c(323921, 307219, 177768, 117716, 11449)
for (i in seq_along(grupos)) check(grupos[i], "respostas no período (federal)", "n", pub_vol[i], gvol(grupos[i]), 0)
check("Grupos", "respostas somadas = corpus", "n", 938987, sum(sapply(grupos, gvol)), 0)

check("Executivo federal", "quase — 2015", "%", 25.25, gval(2015, grupos[2], "quase_pct"))
check("Executivo federal", "quase — 2025", "%", 11.07, gval(2025, grupos[2], "quase_pct"))
check("Universidades", "quase — 2015", "%", 7.37, gval(2015, grupos[3], "quase_pct"))
check("Universidades", "quase — 2025", "%", 13.12, gval(2025, grupos[3], "quase_pct"))
check("Autarquias", "quase — 2015", "%", 39.40, gval(2015, grupos[1], "quase_pct"))
check("Autarquias", "quase — 2025", "%", 31.28, gval(2025, grupos[1], "quase_pct"))
check("Estatais", "quase — 2015", "%", 31.48, gval(2015, grupos[4], "quase_pct"))
check("Estatais", "quase — 2025", "%", 21.87, gval(2025, grupos[4], "quase_pct"))
check("Controle interno", "quase — 2015", "%", 95.30, gval(2015, grupos[5], "quase_pct"))
check("Controle interno", "quase — 2025", "%", 12.37, gval(2025, grupos[5], "quase_pct"))
check("Controle interno", "literal — 2015", "%", 95.16, gval(2015, grupos[5], "literal_pct"))
check("Controle interno", "literal — 2020 (zero)", "%", 0.00, gval(2020, grupos[5], "literal_pct"))
check("Controle interno", "literal — 2025", "%", 7.58, gval(2025, grupos[5], "literal_pct"))
check("Controle interno", "respostas em 2015", "n", 723, gval(2015, grupos[5], "respostas"), 0)
check("Defensoria", "respostas no período", "n", 914, gvol("Defensoria"), 0)

# ------------------------------------------------ 4. PLATAFORMIZAÇÃO E CORRELAÇÃO
cat("\n", strrep("=", 108), "\n 4. PLATAFORMIZAÇÃO E CORRELAÇÃO (11 ANOS)\n", strrep("=", 108), "\n", sep = "")
plata_todos <- sapply(canal, function(r) r$canal$plataforma$pct)
names(plata_todos) <- sapply(canal, function(r) as.character(r$ano))
plata <- plata_todos[as.character(ANOS)]   # a correlação é sobre os mesmos 11 anos das respostas
check("Plataformização", "2015", "%", 47.86, plata["2015"])
check("Plataformização", "2025", "%", 58.92, plata["2025"])
check("Quase-repetição (resposta inteira)", "2015", "%", 30.56, qse_int[1])
check("Quase-repetição (resposta inteira)", "2025", "%", 20.09, qse_int[length(qse_int)])
check("Repetição literal (resposta inteira)", "2015", "%", 16.66, lit_int[1])
check("Repetição literal (resposta inteira)", "2025", "%", 13.41, lit_int[length(lit_int)])

pearson <- function(x, y) {
  n <- length(x); mx <- mean(x); my <- mean(y)
  sum((x - mx) * (y - my)) / sqrt(sum((x - mx)^2) * sum((y - my)^2))
}
spearman <- function(x, y) pearson(rank(x), rank(y))
resid <- function(v, xs) { b <- sum((xs - mean(xs)) * (v - mean(v))) / sum((xs - mean(xs))^2); v - (mean(v) - b * mean(xs) + b * xs) }

check("Correlação quase × plataforma", "Pearson", "r", -0.672, pearson(plata, qse_int), 3)
check("Correlação quase × plataforma", "Spearman", "rho", -0.647, spearman(plata, qse_int), 3)
check("Correlação literal × plataforma", "Pearson", "r", -0.712, pearson(plata, lit_int), 3)
check("Correlação literal × plataforma", "Spearman", "rho", -0.745, spearman(plata, lit_int), 3)

anos <- as.numeric(names(inteira))
check("Robustez (sem tendência do tempo)", "quase × plataforma — Pearson", "r", -0.377,
      pearson(resid(plata, anos), resid(qse_int, anos)), 3)
check("Robustez (sem tendência do tempo)", "literal × plataforma — Pearson", "r", -0.699,
      pearson(resid(plata, anos), resid(lit_int, anos)), 3)

# ------------------------------------------------------------------- SÍNTESE
cat("\n", strrep("=", 108), "\n", sep = "")
cat(sprintf(" FIM — %d itens conferidos | %d BATE | %d DIFERE\n", comparacoes, comparacoes - difere, difere))
if (difere > 0) cat(" DIVERGE — ver as linhas marcadas acima.\n")
cat(strrep("=", 108), "\n", sep = "")

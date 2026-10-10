# =============================================================================
# Conferência INDEPENDENTE (R) dos números do artigo 5 — "Medir a evasão"
# Recalcula a população-alvo, o desenho da amostra e a precisão do kappa.
# Uso: Rscript replicacao-artigo5.R
# =============================================================================
suppressMessages(library(jsonlite))
AQUI <- tryCatch(dirname(normalizePath(sub("^--file=", "",
        grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1]))), error = function(e) getwd())
RAIZ <- dirname(AQUI)
MIN <- file.path(RAIZ, "reprodutibilidade", "saidas-minhash")

comp <- 0; dif <- 0
check <- function(ctx, unidade, publicado, recalc, dec = 2) {
  comp <<- comp + 1
  p <- round(as.numeric(publicado), dec); r <- round(as.numeric(recalc), dec)
  ok <- !is.na(p) && !is.na(r) && abs(p - r) <= 10^(-dec) * 1.5
  if (!ok) dif <<- dif + 1
  cat(sprintf("%-32s %-14s %11s %11s   %s\n", ctx, unidade,
              format(p, nsmall = dec), format(r, nsmall = dec), if (ok) "BATE" else "*** DIFERE ***"))
  invisible(ok)
}
fs <- list.files(MIN, pattern = "^minhash_inteira_20[0-9]{2}\\.json$", full.names = TRUE)
d <- lapply(fs, function(f) fromJSON(f, simplifyVector = FALSE))
tot <- sum(sapply(d, function(x) x$respostas_com_texto))
pad <- sum(sapply(d, function(x) x$minhash$n))
gru <- sum(sapply(d, function(x) x$minhash$grupos_ge_5))
mx  <- max(sapply(d, function(x) x$minhash$maior_grupo))
cat("=== Artigo 5 — população-alvo e desenho ===\n")
check("Corpus", "respostas", "938987", tot, 0)
check("População-alvo", "padronizadas", "227332", pad, 0)
check("População-alvo", "% do corpus", "24.21", 100 * pad / tot)
check("Grupos de repetição", "grupos", "9865", gru, 0)
check("Tamanho médio", "respostas", "23.04", pad / gru)
check("Maior grupo", "respostas", "870", mx, 0)

# alocação proporcional com maior resto
N <- 630
ns <- sapply(d, function(x) x$respostas_com_texto)
aloc <- floor(N * ns / tot)
resto <- N - sum(aloc)
ord <- order(-(N * ns / tot - aloc))
aloc[ord[seq_len(resto)]] <- aloc[ord[seq_len(resto)]] + 1
check("Amostra", "unidades alocadas", "630", sum(aloc), 0)

# precisão do kappa (fórmula de Fleiss et al. para duas categorias)
var_k <- function(k, n, p1) {
  pe <- p1^2 + (1 - p1)^2; po <- k * (1 - pe) + pe
  (p1 * (po + p1 - 1) * (1 - p1) + (1 - p1) * (po + 1 - 2 * p1) * p1) / (n * (1 - pe)^2)
}
for (n in c(400, 630, 1000)) {
  check(sprintf("Precisão (n=%d, κ=0,70)", n), "erro-padrão", c("400" = 0.062, "630" = 0.049, "1000" = 0.039)[as.character(n)],
        sqrt(var_k(0.70, n, 0.35)), 3)
}
cat(sprintf("\nFIM — %d itens conferidos | %d BATE | %d DIFERE\n", comp, comp - dif, dif))

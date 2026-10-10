# =============================================================================
# Conferência INDEPENDENTE (R) dos números do artigo 4 — "O que o cidadão contesta"
# Recalcula, de outra linguagem, os totais e as taxas publicadas do arranjo recursal
# da LAI (2012-2025) e compara item a item com o valor afirmado no artigo.
# Uso: Rscript replicacao-artigo4.R
# =============================================================================
AQUI <- tryCatch(dirname(normalizePath(sub("^--file=", "",
        grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1]))), error = function(e) getwd())
RAIZ <- dirname(AQUI)
REC <- file.path(RAIZ, "reprodutibilidade", "saidas-recursos")

comp <- 0; dif <- 0
check <- function(ctx, unidade, publicado, recalc, dec = 1) {
  comp <<- comp + 1
  p <- round(as.numeric(publicado), dec); r <- round(as.numeric(recalc), dec)
  ok <- !is.na(p) && !is.na(r) && abs(p - r) <= 10^(-dec) * 1.5
  if (!ok) dif <<- dif + 1
  cat(sprintf("%-34s %-12s %10s %10s   %s\n", ctx, unidade,
              format(p, nsmall = dec), format(r, nsmall = dec), if (ok) "BATE" else "*** DIFERE ***"))
  invisible(ok)
}
pct <- function(a, b) 100 * a / b

pa <- read.csv(file.path(REC, "por-ano.csv"), check.names = FALSE)
cat("=== Artigo 4 — arranjo recursal da LAI ===\n")
check("Corpus", "recursos", "222242", sum(pa$recursos), 0)
check("Série 2012", "recursos", "4606", pa$recursos[pa$ano == 2012], 0)
check("Série 2025", "recursos", "22278", pa$recursos[pa$ano == 2025], 0)
check("Provimento 2025", "%", "39.5", pa$provido_ou_parcial_pct[pa$ano == 2025])
check("Não conhecido 2025", "%", "18.7", pa$nao_conhecido_pct[pa$ano == 2025])
check("Sem resposta 2025", "%", "5.2", pa$sem_resposta_pct[pa$ano == 2025])
check("Não conhecido 2021", "%", "14.5", pa$nao_conhecido_pct[pa$ano == 2021])
check("Sem resposta 2021", "%", "3.1", pa$sem_resposta_pct[pa$ano == 2021])

pi <- read.csv(file.path(REC, "instancia-x-desfecho.csv"), check.names = FALSE)
rot <- names(pi)[1]
pr <- function(nome, campo) {
  v <- pi[grepl(nome, pi[[rot]], ignore.case = TRUE), ]
  if (!nrow(v)) return(NA)
  x <- v[[campo]][1]
  if (grepl("pct$", campo)) as.numeric(x) else pct(as.numeric(x), as.numeric(v$recursos[1]))
}
check("1ª instância", "provido (%)", "47.9", pr("^Primeira Inst", "provido_ou_parcial_pct"))
check("1ª instância", "não conhecido (%)", "11.2", pr("^Primeira Inst", "nao_conhecido_pct"))
check("Controle interno", "não conhecido (%)", "38.9", pr("^CGU$", "nao_conhecido_pct"))
check("CMRI", "não conhecido (%)", "62.8", pr("^CMRI$", "nao_conhecido_pct"))

mo <- read.csv(file.path(REC, "motivo-x-desfecho.csv"), check.names = FALSE)
rmot <- names(mo)[1]
mr <- function(trecho, campo) {
  v <- mo[grepl(trecho, mo[[rmot]], ignore.case = TRUE), ]
  if (!nrow(v)) return(NA)
  x <- v[[campo]][1]
  if (grepl("pct$", campo)) as.numeric(x) else as.numeric(x)
}
check("Informação incompleta", "provido (%)", "49.4", mr("^Informação incompleta$", "provido_ou_parcial_pct"))
check("Ausência de justificativa", "não conhecido (%)", "41.6", mr("^Ausência de justificativa legal", "nao_conhecido_pct"))
check("Sigilo", "provido (%)", "21.4", mr("^Justificativa para o sigilo", "provido_ou_parcial_pct"))

g <- read.csv(file.path(REC, "guardioes.csv"), check.names = FALSE)
cat("\n--- guardiões (por grupo) ---\n"); print(g)
cat(sprintf("\nFIM — %d itens conferidos | %d BATE | %d DIFERE\n", comp, comp - dif, dif))

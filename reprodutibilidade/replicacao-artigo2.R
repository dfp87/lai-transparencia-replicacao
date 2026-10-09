#!/usr/bin/env Rscript
# =============================================================================
# replicacao-artigo2.R
#
# Réplica, em R, da análise quantitativa do artigo
#   "Como o Estado escreve o 'não': resistência por resposta na LAI brasileira
#    (2015-2025)"  (proposta 2 / versão v10)
#
# O que o script faz (autocontido, executado com `Rscript replicacao-artigo2.R`):
#   (1) lê os arquivos de evidência em 04-pesquisa/rap-lai-15anos/ (JSON e CSV);
#   (2) recalcula os indicadores do artigo:
#         - volume e decisões por ano (registro estruturado);
#         - padronização da resposta pelos DOIS métodos (hash exato dos 250
#           primeiros caracteres e quase-repetição por MinHash) e pelas TRÊS
#           configurações auditadas do MinHash (final 16x8, v2 baldes
#           descartados, v3 baldes unidos);
#         - tipologia da negativa no registro (2012-2025);
#         - canal de entrega da resposta (2012-2025);
#         - extensão média da resposta por ano;
#         - convergência entre fundamento registrado e fundamento escrito, com
#           kappa de Cohen agrupado (matriz de confusão somada dos onze anos);
#         - composição do pedido e cruzamento pedido x decisão;
#   (3) grava as tabelas em reprodutibilidade/saidas-R/ (CSV);
#   (4) gera as figuras equivalentes em reprodutibilidade/figuras-R/ (PNG 300 dpi);
#   (5) imprime um relatório de conferência NÚMERO A NÚMERO contra o artigo,
#       com veredito BATE / DIFERE por número conferido.
#
# Regra de ouro: NENHUM número do artigo é digitado para gerar as tabelas ou as
# figuras — todos vêm das evidências. Os valores publicados só aparecem no bloco
# de conferência (para comparação), nunca no cálculo.
#
# Requisitos: R >= 4.0 e o pacote jsonlite. Usa apenas gráficos de BASE R, de
# modo que a réplica não depende de ggplot2 nem de pacotes gráficos externos.
# Ambiente testado: R 4.5.0.
# =============================================================================

## ---------------------------------------------------------------------------
## 0. Caminhos de entrada e de saída
## ---------------------------------------------------------------------------
# Raiz do projeto: por padrao, a pasta que contem este script (o repositorio);
# pode ser sobrescrita pela variavel de ambiente LAI_RAIZ.
.args <- commandArgs(trailingOnly = FALSE)
.fica <- grep("^--file=", .args, value = TRUE)
.dir_script <- if (length(.fica)) dirname(normalizePath(sub("^--file=", "", .fica[1]))) else getwd()
BASE <- Sys.getenv("LAI_RAIZ", unset = dirname(.dir_script))
base_proj <- BASE
dir_ev    <- file.path(base_proj, "evidencias")
dir_rep   <- file.path(base_proj, "reprodutibilidade")
dir_minh  <- file.path(dir_rep, "saidas-minhash")
dir_tab   <- file.path(dir_rep, "saidas-R")     # saída das tabelas
dir_fig   <- file.path(dir_rep, "figuras-R")    # saída das figuras

dir.create(dir_tab, showWarnings = FALSE, recursive = TRUE)
dir.create(dir_fig, showWarnings = FALSE, recursive = TRUE)

op <- options(stringsAsFactors = FALSE)

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("O pacote 'jsonlite' é necessário para ler as evidências JSON.")
}
library(jsonlite)

## ---------------------------------------------------------------------------
## 0.1 Utilidades
## ---------------------------------------------------------------------------
# Arredondamento "meio para cima" (0,5 -> 1), que é a convenção do artigo
# (p.ex. 21,25% -> 21,3% e 29,65% -> 29,7%). A função round() do R arredonda
# para o par mais próximo nesses casos-limite, por isso não é usada aqui.
meia <- function(x, d = 0) {
  z <- 10^d
  positivo <- x >= 0
  y <- abs(x) * z
  y <- floor(y + 0.5)
  y <- y / z
  ifelse(positivo, y, -y)
}

# % seguro (evita divisão por zero)
pct <- function(num, den) 100 * num / den

# Formata inteiro com separador de milhar "." (sem disparar o aviso de
# big.mark == decimal.mark do format()).
milhar <- function(x) gsub(",", ".", formatC(as.integer(x), format = "d", big.mark = ","))

sep <- function(titulo) cat("\n", strrep("=", 78), "\n", titulo, "\n", strrep("=", 78), "\n", sep = "")

## ---------------------------------------------------------------------------
## 1. Leitura das evidências
## ---------------------------------------------------------------------------
sep("1. LEITURA DAS EVIDÊNCIAS")

# (a) Série textual anual (volume, extensão, decisões): CSV
arq_serie <- file.path(dir_ev, "serie_textual_2015-2025.csv")
serie <- read.csv(arq_serie, header = TRUE, fileEncoding = "UTF-8", check.names = FALSE)
cat("serie_textual_2015-2025.csv :", nrow(serie), "anos | colunas:",
    paste(names(serie), collapse = ", "), "\n")

# (b) Consolidado do MinHash (as três configurações auditadas)
arq_cons <- file.path(dir_minh, "consolidado_minhash_FINAL.json")
cons <- fromJSON(arq_cons, simplifyVector = FALSE)
anos_mh <- sort(as.integer(names(cons$por_ano)))

# (c) Canal de entrega (2012-2025)
canal <- fromJSON(file.path(dir_ev, "canal_entrega.json"), simplifyVector = FALSE)

# (d) Tipologia da negativa no registro (2012-2025)
tipologia <- fromJSON(file.path(dir_ev, "tipologia_negativa.json"), simplifyVector = FALSE)

# (e) Convergência entre fundamento registrado e escrito (2015-2025)
conv <- fromJSON(file.path(dir_ev, "convergencia_negativa.json"), simplifyVector = FALSE)

# (f) Agregado da camada 1+3 do registro estruturado (decisão, pedido, cruzamentos)
agreg <- fromJSON(file.path(dir_ev, "camada13_v2", "AGREGADO.json"), simplifyVector = FALSE)

# (g) Série estruturada 2012-2025 (total de pedidos)
arq_est <- list.files(file.path(dir_ev, "estruturado"), pattern = "^estruturado_20[0-9]{2}\\.json$", full.names = TRUE)
estrut <- lapply(sort(arq_est), function(f) fromJSON(f, simplifyVector = FALSE))
pedidos_total_2012_2025 <- sum(vapply(estrut, function(x) as.numeric(x$pedidos), numeric(1)))
cat("Total de pedidos no registro estruturado, 2012-2025 :", milhar(pedidos_total_2012_2025), "\n")

# (h) Contagens de decisão por ano (camada 1+3, arquivos anuais)
arq_c13 <- list.files(file.path(dir_ev, "camada13_v2"), pattern = "^camada13_20[0-9]{2}\\.json$", full.names = TRUE)
c13 <- lapply(sort(arq_c13), function(f) fromJSON(f, simplifyVector = FALSE))
cat("Evidências lidas: consolidado MinHash (", length(anos_mh), " anos), canal (",
    length(canal), "), tipologia (", length(tipologia), "), convergência (", length(conv), ").\n", sep = "")

## ---------------------------------------------------------------------------
## 2. RECÁLCULO DOS INDICADORES
## ---------------------------------------------------------------------------

## 2.1 Composição da decisão no corpus (Quadro 1) ----------------------------
decisao <- unlist(agreg$decisao)
decisao <- setNames(as.numeric(decisao), names(decisao))
n_corpus <- as.numeric(agreg$total_pedidos)
df_decisao <- data.frame(
  decisao = names(decisao),
  n = as.integer(decisao),
  pct = meia(pct(decisao, n_corpus), 1),
  row.names = NULL
)
df_decisao <- df_decisao[order(-df_decisao$n), ]

## 2.2 Decisões por ano (registro) -------------------------------------------
cats_dec <- names(decisao)
dec_ano <- matrix(0L, nrow = length(c13), ncol = length(cats_dec),
                  dimnames = list(NULL, cats_dec))
ano_c13 <- integer(length(c13))
for (i in seq_along(c13)) {
  ano_c13[i] <- as.integer(c13[[i]]$ano)
  d <- unlist(c13[[i]]$contagens$decisao)
  dec_ano[i, names(d)] <- as.integer(d)
}
df_dec_ano <- data.frame(ano = ano_c13, dec_ano, check.names = FALSE)
df_dec_ano$total <- rowSums(dec_ano)

## 2.3 Série textual anual: volume, extensão média, padronização (Quadro 1/Fig 5)
serie <- serie[order(serie$ano), ]
df_serie <- data.frame(
  ano = serie$ano,
  pedidos = serie$pedidos,
  ext_media_resposta = serie$ext_media_resposta,
  ext_mediana_resposta = serie$ext_mediana_resposta,
  respostas_distintas_inicio = serie$respostas_distintas_inicio,
  pct_exato_csv = serie$pct_resposta_padronizada
)

## 2.4 Padronização da resposta: dois métodos x três configurações -----------
#  - exato_md5_250 : hash dos 250 primeiros caracteres normalizados (medida antiga)
#  - minhash_final : 16 bandas x 8 linhas, descartando e contando baldes grandes
#  - minhash_v2    : 32x4, descartando baldes grandes
#  - minhash_v3    : 32x4, unindo os baldes grandes (teto sob regra permissiva)
pad <- data.frame(
  ano = anos_mh,
  respostas_com_texto = vapply(anos_mh, function(a) as.numeric(cons$por_ano[[as.character(a)]]$respostas), numeric(1)),
  exato_md5_250_pct = vapply(anos_mh, function(a) as.numeric(cons$por_ano[[as.character(a)]]$md5_250_pct), numeric(1)),
  minhash_final_pct = vapply(anos_mh, function(a) as.numeric(cons$por_ano[[as.character(a)]]$minhash_final_pct), numeric(1)),
  minhash_v2_descartando_pct = vapply(anos_mh, function(a) as.numeric(cons$por_ano[[as.character(a)]]$minhash_32x4_descartando_pct), numeric(1)),
  minhash_v3_unindo_pct = vapply(anos_mh, function(a) as.numeric(cons$por_ano[[as.character(a)]]$minhash_32x4_unindo_pct), numeric(1)),
  grupos_ge_5 = vapply(anos_mh, function(a) as.numeric(cons$por_ano[[as.character(a)]]$grupos_ge_5), numeric(1))
)
# Totais ponderados pelo número de respostas com texto de cada ano.
tot_resp <- sum(pad$respostas_com_texto)
pond <- function(v) sum(v * pad$respostas_com_texto) / tot_resp
totais_pad <- c(
  respostas_com_texto        = tot_resp,
  exato_md5_250_pct          = pond(pad$exato_md5_250_pct),
  minhash_final_pct          = pond(pad$minhash_final_pct),
  minhash_v2_descartando_pct = pond(pad$minhash_v2_descartando_pct),
  minhash_v3_unindo_pct      = pond(pad$minhash_v3_unindo_pct)
)

## 2.5 Composição do pedido (Quadro 2) ---------------------------------------
rot_tipo <- c(indefinido = "indefinido", contrato = "contrato", pessoal = "pessoal",
              gasto = "gasto", ato = "ato", dado_bruto = "dado bruto",
              politica_publica = "politica publica")
rot_esp  <- c(generico = "generico", delimitado = "delimitado", especifico = "especifico")
rot_art  <- c(desproporcional = "desproporcional", trabalho_adicional = "trabalho adicional",
              generico = "generico")

faz_quadro2 <- function(lst, rotulo_dim, rot_map) {
  v <- unlist(lst)
  v <- setNames(as.numeric(v), names(v))
  data.frame(dimensao = rotulo_dim, categoria = unname(rot_map[names(v)]),
             n = as.integer(v), pct = meia(pct(v, n_corpus), 1), row.names = NULL)
}
df_quadro2 <- rbind(
  faz_quadro2(agreg$tipo_primario, "Tipo (primario)", rot_tipo),
  faz_quadro2(agreg$especificidade, "Especificidade", rot_esp),
  faz_quadro2(agreg$art13, "Marca do art. 13", rot_art)
)
df_quadro2 <- df_quadro2[order(df_quadro2$dimensao, -df_quadro2$n), ]

## 2.6 Cruzamento pedido x decisão (Quadro 3) ---------------------------------
# Monta, a partir de um cross-tab "categoria | Decisao" -> n, a taxa de negativa
# integral e as duas leituras de concessão.
cruz <- function(x) {
  x <- unlist(x)
  n <- as.numeric(x); nms <- names(x)
  partes <- strsplit(nms, " | ", fixed = TRUE)
  cat_ <- vapply(partes, `[`, character(1), 1)
  dec_ <- vapply(partes, `[`, character(1), 2)
  cats <- unique(cat_)
  out <- data.frame(categoria = cats, n = NA_integer_,
                    neg_integral_pct = NA_real_,
                    conc_integral_pct = NA_real_,
                    conc_total_pct = NA_real_, row.names = NULL)
  for (i in seq_along(cats)) {
    cc <- cats[i]
    total <- sum(n[cat_ == cc])
    neg   <- sum(n[cat_ == cc & dec_ == "Acesso Negado"])
    conc  <- sum(n[cat_ == cc & dec_ == "Acesso Concedido"])
    parc  <- sum(n[cat_ == cc & dec_ == "Acesso Parcialmente Concedido"])
    out$n[i]                 <- as.integer(total)
    out$neg_integral_pct[i]  <- meia(pct(neg, total), 1)
    out$conc_integral_pct[i] <- meia(pct(conc, total), 1)              # concedido
    out$conc_total_pct[i]    <- meia(pct(conc + parc, total), 1)      # concedido + parcial
  }
  out
}
q3_espec <- cruz(agreg$esp_x_decisao);      q3_espec$dimensao <- "Especificidade"
q3_art13 <- cruz(agreg$art13_x_decisao);    q3_art13$dimensao <- "Marca do art. 13"
q3_tipo  <- cruz(agreg$tipo_x_decisao);     q3_tipo$dimensao  <- "Tipo"
df_quadro3 <- rbind(q3_espec, q3_art13, q3_tipo)
names(df_quadro3)[1] <- "categoria"

## 2.7 Convergência registro x texto (Quadro 4) + kappa agrupado --------------
df_quadro4 <- data.frame(
  ano = vapply(conv, function(r) as.integer(r$ano), integer(1)),
  negativas_com_texto = vapply(conv, function(r) as.integer(r$negados_com_texto), integer(1)),
  citam_lai_pct = vapply(conv, function(r) meia(as.numeric(r$citam_lai_pct), 1), numeric(1)),
  kappa = vapply(conv, function(r) meia(as.numeric(r$kappa$kappa), 3), numeric(1)),
  stringsAsFactors = FALSE
)
# "Sem fundamento (%)" no Quadro 4 é o complemento de "Cita norma da LAI (%)".
df_quadro4$sem_fundamento_pct <- meia(100 - df_quadro4$citam_lai_pct, 1)
df_quadro4 <- df_quadro4[, c("ano", "negativas_com_texto", "citam_lai_pct",
                             "sem_fundamento_pct", "kappa")]

# Kappa AGRUPADO: soma a matriz de confusão (registro x texto) dos onze anos e
# calcula um único kappa sobre a matriz somada — é o "0,306" do artigo.
cats_txt <- c("dados_pessoais", "sigilo", "processo_em_curso", "generico",
              "desproporcional", "sem_norma", "competencia_outro", "inexistente")
mat_pool <- matrix(0, nrow = length(cats_txt), ncol = length(cats_txt),
                   dimnames = list(cats_txt, cats_txt))
for (r in conv) {
  for (linha in names(r$matriz)) {
    for (col in names(r$matriz[[linha]])) {
      if (linha %in% cats_txt && col %in% cats_txt) {
        mat_pool[linha, col] <- mat_pool[linha, col] + as.numeric(r$matriz[[linha]][[col]])
      }
    }
  }
}
N_pool <- sum(mat_pool)
po <- sum(diag(mat_pool)) / N_pool
pe <- sum(rowSums(mat_pool) * colSums(mat_pool)) / N_pool^2
kappa_agrupado <- (po - pe) / (1 - pe)
concordancia_agrupada_pct <- meia(100 * po, 1)
# frações globais (ponderadas) de "sem norma" no texto e no registro
tot_neg_texto <- sum(df_quadro4$negativas_com_texto)
sem_norma_texto_pct <- meia(sum(vapply(conv, function(r) as.numeric(r$citado_sem_norma_pct) * as.numeric(r$negados_com_texto), numeric(1))) / tot_neg_texto, 1)
sem_norma_registro_pct <- meia(sum(vapply(conv, function(r) as.numeric(r$declarado_sem_norma_pct) * as.numeric(r$negados_com_texto), numeric(1))) / tot_neg_texto, 1)
# "processo decisório em curso" no registro vs no texto
proc_registro_pct <- meia(pct(sum(mat_pool["processo_em_curso", ]), N_pool), 1)
proc_texto_pct    <- meia(pct(sum(mat_pool[, "processo_em_curso"]), N_pool), 1)

## 2.8 Canal de entrega (Figura 2) -------------------------------------------
canais <- c("email", "plataforma", "outras", "orientacao", "nao_especificado")
rot_canal <- c(email = "e-mail", plataforma = "plataforma", outras = "outras",
               orientacao = "orientacao", nao_especificado = "nao especificado")
anos_canal <- vapply(canal, function(r) as.integer(r$ano), integer(1))
m_canal <- matrix(NA_real_, nrow = length(anos_canal), ncol = length(canais),
                  dimnames = list(NULL, canais))
for (i in seq_along(canal)) {
  cd <- canal[[i]]$canal
  for (ch in names(cd)) {
    chave <- ch
    if (identical(ch, "não especificado")) chave <- "nao_especificado"
    if (chave %in% canais) m_canal[i, chave] <- as.numeric(cd[[ch]]$pct)
  }
}
df_canal <- data.frame(ano = anos_canal, m_canal, check.names = FALSE)

## 2.9 Tipologia da negativa (Figura 3) --------------------------------------
anos_tip <- sort(as.integer(names(tipologia)))
fam_keys <- c("dados pessoais (art. 31)", "sigilo legal", "processo decisório em curso",
              "pedido genérico", "desproporcional / desarrazoado", "outros / forma de entrega")
fam_rot  <- c("dados pessoais (art. 31)", "sigilo legal", "processo decisorio em curso",
              "pedido generico", "desproporcional / desarrazoado", "outros / forma de entrega")
m_tip <- matrix(NA_real_, nrow = length(anos_tip), ncol = length(fam_keys),
                dimnames = list(NULL, fam_rot))
negados_tip <- integer(length(anos_tip))
for (i in seq_along(anos_tip)) {
  rec <- tipologia[[as.character(anos_tip[i])]]
  negados_tip[i] <- as.integer(rec$negados)
  fam <- unlist(rec$familias)
  for (j in seq_along(fam_keys)) {
    m_tip[i, j] <- meia(pct(as.numeric(fam[fam_keys[j]]), negados_tip[i]), 1)
  }
}
df_tipologia <- data.frame(ano = anos_tip, negados = negados_tip, m_tip, check.names = FALSE)

## ---------------------------------------------------------------------------
## 3. GRAVAÇÃO DAS TABELAS EM saidas-R/
## ---------------------------------------------------------------------------
sep("3. TABELAS GRAVADAS EM saidas-R/")
grava_csv <- function(df, nome) {
  p <- file.path(dir_tab, nome)
  write.csv(df, p, row.names = FALSE, fileEncoding = "UTF-8")
  cat(sprintf("  %-40s %d linhas\n", nome, nrow(df)))
  invisible(p)
}
grava_csv(df_decisao,  "T1_composicao-decisao.csv")
grava_csv(df_serie,    "T2_serie-textual-por-ano.csv")
grava_csv(pad,         "T3_padronizacao-2metodos-3configs.csv")
grava_csv(df_dec_ano,  "T4_decisoes-por-ano.csv")
grava_csv(df_quadro2,  "T5_composicao-do-pedido.csv")
grava_csv(df_quadro3,  "T6_pedido-x-negativa.csv")
grava_csv(df_quadro4,  "T7_convergencia-registro-texto.csv")
grava_csv(df_canal,    "T8_canal-de-entrega.csv")
grava_csv(df_tipologia,"T9_tipologia-da-negativa.csv")

## ---------------------------------------------------------------------------
## 4. FIGURAS EM figuras-R/ (PNG 300 dpi)
## ---------------------------------------------------------------------------
sep("4. FIGURAS GERADAS EM figuras-R/")
AZUL  <- "#1f4e79"; VERM <- "#a4262c"; CINZA <- "#7f7f7f"
VERDE <- "#2e7d32"; LARANJA <- "#c55a11"; ROXO <- "#5b2d8e"
salva_png <- function(nome, largura, altura, expr) {
  p <- file.path(dir_fig, nome)
  png(p, width = largura, height = altura, units = "in", res = 300)
  expr
  dev.off()  # fecha o dispositivo ANTES de medir o arquivo
  cat(sprintf("  %-42s %s\n", nome, if (file.exists(p)) sprintf("(%d bytes)", file.size(p)) else "FALHOU"))
}

## F7 — Resposta por fórmula: repetição literal e quase-repetição (2015-2025)
salva_png("F7_padronizacao-dois-metodos.png", 7.2, 4.0, {
  par(mar = c(4.2, 4.4, 3.2, 1.2))
  plot(pad$ano, pad$exato_md5_250_pct, type = "b", pch = 19, col = AZUL, lwd = 2,
       ylim = c(0, max(pad$minhash_final_pct) * 1.35), xaxt = "n",
       xlab = "Ano do pedido", ylab = "Respostas padronizadas (%)",
       main = "Resposta por fórmula: repetição literal e quase-repetição, 2015–2025")
  axis(1, at = pad$ano)
  grid(nx = NA, ny = NULL, col = "#dddddd", lty = 1)
  lines(pad$ano, pad$minhash_final_pct, type = "b", pch = 15, col = VERM, lwd = 2)
  text(pad$ano[1], pad$exato_md5_250_pct[1], sprintf("%.1f%%", pad$exato_md5_250_pct[1]),
       pos = 1, cex = 0.72, col = AZUL)
  text(pad$ano[length(pad$ano)], pad$exato_md5_250_pct[nrow(pad)],
       sprintf("%.1f%%", pad$exato_md5_250_pct[nrow(pad)]), pos = 1, cex = 0.72, col = AZUL)
  text(pad$ano[1], pad$minhash_final_pct[1], sprintf("%.1f%%", pad$minhash_final_pct[1]),
       pos = 3, cex = 0.72, col = VERM)
  text(pad$ano[nrow(pad)], pad$minhash_final_pct[nrow(pad)],
       sprintf("%.1f%%", pad$minhash_final_pct[nrow(pad)]), pos = 3, cex = 0.72, col = VERM)
  legend("bottomleft", bty = "n", cex = 0.85,
         legend = c("Repetição literal (abertura idêntica)",
                    "Quase-repetição (MinHash, J ≥ 0,80)"),
         col = c(AZUL, VERM), pch = c(19, 15), lwd = 2)
})

## F5 — Resposta padronizada (literal) e extensão média da resposta
salva_png("F5_padronizada-e-extensao.png", 7.2, 4.0, {
  par(mar = c(4.2, 4.4, 3.2, 4.6))
  plot(df_serie$ano, df_serie$pct_exato_csv, type = "b", pch = 19, col = AZUL, lwd = 2,
       xaxt = "n", xlab = "Ano do pedido", ylab = "Resposta padronizada (%)",
       ylim = c(0, max(df_serie$pct_exato_csv) * 1.35),
       main = "Resposta padronizada e extensão média da resposta, 2015–2025")
  axis(1, at = df_serie$ano)
  grid(nx = NA, ny = NULL, col = "#dddddd", lty = 1)
  par(new = TRUE)
  plot(df_serie$ano, df_serie$ext_media_resposta, type = "b", pch = 17, col = VERM,
       lwd = 2, axes = FALSE, xlab = "", ylab = "", xaxt = "n")
  axis(4, col = VERM, col.axis = VERM)
  mtext("Extensão média da resposta (caracteres)", side = 4, line = 2.8, col = VERM, cex = 0.85)
  legend("topleft", bty = "n", cex = 0.82,
         legend = c("Resposta padronizada (repetição literal, eixo esq.)",
                    "Extensão média (caracteres, eixo dir.)"),
         col = c(AZUL, VERM), pch = c(19, 17), lwd = 2)
})

## F2 — Canal de entrega da resposta (2012-2025)
salva_png("F2_canal-de-entrega.png", 7.4, 4.2, {
  par(mar = c(4.2, 4.4, 3.2, 1.2))
  cores <- c(AZUL, VERDE, CINZA, LARANJA, ROXO)
  plot(df_canal$ano, df_canal$plataforma, type = "n", xaxt = "n",
       ylim = c(0, 100), xlab = "Ano do pedido", ylab = "Respostas por canal (%)",
       main = "Canal de entrega da resposta da LAI, 2012–2025")
  axis(1, at = df_canal$ano); grid(nx = NA, ny = NULL, col = "#dddddd", lty = 1)
  for (j in seq_along(canais)) {
    lines(df_canal$ano, df_canal[[canais[j]]], type = "b", pch = 19, lwd = 2, col = cores[j])
  }
  legend("top", bty = "n", cex = 0.8, col = cores, pch = 19, lwd = 2, ncol = 3,
         legend = unname(rot_canal[canais]))
})

## F3 — Tipologia da negativa no registro (2012-2025)
salva_png("F3_tipologia-da-negativa.png", 7.4, 4.2, {
  par(mar = c(4.2, 4.4, 3.2, 1.2))
  cores <- c(VERM, AZUL, VERDE, CINZA, LARANJA, ROXO)
  ymax <- max(m_tip, na.rm = TRUE)
  matplot(df_tipologia$ano, as.matrix(df_tipologia[, fam_rot]),
          type = "b", pch = 19, lty = 1, lwd = 2, col = cores,
          xaxt = "n", xlab = "Ano do pedido", ylab = "Negativas no registro (%)",
          main = "Por que o Estado nega: tipologia da negativa no registro, 2012–2025",
          ylim = c(0, ymax * 1.75))  # folga para a legenda não cobrir as linhas
  axis(1, at = df_tipologia$ano)
  grid(nx = NA, ny = NULL, col = "#dddddd", lty = 1)
  legend("top", bty = "n", cex = 0.74, col = cores, lwd = 2, pch = 19, ncol = 3,
         legend = fam_rot)
})

## ---------------------------------------------------------------------------
## 5. RELATÓRIO DE CONFERÊNCIA — NÚMERO A NÚMERO CONTRA O ARTIGO
## ---------------------------------------------------------------------------
sep("5. CONFERÊNCIA — VALORES DO ARTIGO x VALORES RECALCULADOS")

conf_nome <- character(); conf_art <- numeric(); conf_calc <- numeric(); conf_dec <- integer()
adiciona <- function(nome, artigo, calculado, dec = 1) {
  conf_nome   <<- c(conf_nome, nome)
  conf_art    <<- c(conf_art, artigo)
  conf_calc   <<- c(conf_calc, calculado)
  conf_dec    <<- c(conf_dec, dec)
}

## 5.1 Totais do corpus
adiciona("Respostas com texto, 2015-2025",        938987, tot_resp, 0)
adiciona("Pedidos registrados, 2012-2025",       1641939, pedidos_total_2012_2025, 0)
adiciona("Repetição literal total (md5 250) %",     20.64, totais_pad[["exato_md5_250_pct"]], 2)
adiciona("Quase-repetição MinHash FINAL %",         22.55, totais_pad[["minhash_final_pct"]], 2)
adiciona("MinHash v2 (baldes descartados) %",       22.49, totais_pad[["minhash_v2_descartando_pct"]], 2)
adiciona("MinHash v3 (baldes unidos) %",            37.47, totais_pad[["minhash_v3_unindo_pct"]], 2)

## 5.2 Composição da decisão (Quadro 1)
gi <- function(nm) which(df_decisao$decisao == nm)
adiciona("Quadro 1: Acesso Concedido n",   676295, df_decisao$n[gi("Acesso Concedido")], 0)
adiciona("Quadro 1: Acesso Concedido %",     72.0, df_decisao$pct[gi("Acesso Concedido")], 1)
adiciona("Quadro 1: Nao se trata de solic. %", 7.0, df_decisao$pct[gi("Não se trata de solicitação de informação")], 1)
adiciona("Quadro 1: Acesso Negado n",      61824, df_decisao$n[gi("Acesso Negado")], 0)
adiciona("Quadro 1: Acesso Negado %",         6.6, df_decisao$pct[gi("Acesso Negado")], 1)
adiciona("Quadro 1: Parcialmente Concedido %", 5.5, df_decisao$pct[gi("Acesso Parcialmente Concedido")], 1)
adiciona("Quadro 1: Informacao Inexistente %", 3.6, df_decisao$pct[gi("Informação Inexistente")], 1)
adiciona("Quadro 1: Orgao incompetente %",     2.9, df_decisao$pct[gi("Órgão não tem competência para responder sobre o assunto")], 1)
adiciona("Quadro 1: Pergunta Duplicada %",     2.3, df_decisao$pct[gi("Pergunta Duplicada/Repetida")], 1)

## 5.3 Série por ano: exato e MinHash (Tabela do método + Figura 7)
art_exato   <- c(20.9, 21.2, 20.0, 19.0, 14.9, 24.7, 21.5, 21.3, 22.7, 20.3, 20.4)
art_minhash <- c(24.8, 25.2, 20.9, 22.8, 20.1, 20.6, 21.3, 25.6, 24.4, 22.5, 21.6)
for (i in seq_along(pad$ano)) {
  adiciona(sprintf("Serie %d exato (md5 250) %%" , pad$ano[i]), art_exato[i],   pad$exato_md5_250_pct[i], 1)
}
for (i in seq_along(pad$ano)) {
  adiciona(sprintf("Serie %d quase-repeticao (MinHash) %%", pad$ano[i]), art_minhash[i], pad$minhash_final_pct[i], 1)
}

## 5.4 Composição do pedido (Quadro 2) — contagens
cont2 <- setNames(df_quadro2$n, paste(df_quadro2$dimensao, df_quadro2$categoria, sep = "|"))
adiciona("Quadro 2: tipo contrato n",      335094, cont2[["Tipo (primario)|contrato"]], 0)
adiciona("Quadro 2: tipo indefinido n",    291758, cont2[["Tipo (primario)|indefinido"]], 0)
adiciona("Quadro 2: tipo pessoal n",        85251, cont2[["Tipo (primario)|pessoal"]], 0)
adiciona("Quadro 2: tipo ato n",            64463, cont2[["Tipo (primario)|ato"]], 0)
adiciona("Quadro 2: tipo dado bruto n",     57998, cont2[["Tipo (primario)|dado bruto"]], 0)
adiciona("Quadro 2: tipo politica pub. n",  54307, cont2[["Tipo (primario)|politica publica"]], 0)
adiciona("Quadro 2: tipo gasto n",          50120, cont2[["Tipo (primario)|gasto"]], 0)
adiciona("Quadro 2: espec. generico n",    478527, cont2[["Especificidade|generico"]], 0)
adiciona("Quadro 2: espec. delimitado n",  301196, cont2[["Especificidade|delimitado"]], 0)
adiciona("Quadro 2: espec. especifico n",  159268, cont2[["Especificidade|especifico"]], 0)
adiciona("Quadro 2: art13 desproporcional n", 138098, cont2[["Marca do art. 13|desproporcional"]], 0)
adiciona("Quadro 2: art13 trabalho adic. n",  104971, cont2[["Marca do art. 13|trabalho adicional"]], 0)
adiciona("Quadro 2: art13 generico n",         71473, cont2[["Marca do art. 13|generico"]], 0)
pct2 <- setNames(df_quadro2$pct, paste(df_quadro2$dimensao, df_quadro2$categoria, sep = "|"))
adiciona("Quadro 2: contrato %",             35.7, pct2[["Tipo (primario)|contrato"]], 1)
adiciona("Quadro 2: indefinido %",           31.1, pct2[["Tipo (primario)|indefinido"]], 1)
adiciona("Quadro 2: espec. generico %",      51.0, pct2[["Especificidade|generico"]], 1)

## 5.5 Cruzamento pedido x negativa (Quadro 3): negativa integral e concessão
# Para a coluna "Concessão (%)" o artigo usa duas leituras: no bloco Tipo, a
# concessão INCLUI a parcial (conc_total); nos blocos Especificidade e Marca do
# art. 13, é a concessão INTEGRAL (só "Acesso Concedido"). O script replica as
# duas e compara cada linha com a leitura correspondente — documentado aqui.
q3 <- function(dim, cat_) {
  r <- df_quadro3[df_quadro3$dimensao == dim & df_quadro3$categoria == cat_, ]
  list(n = r$n[1], neg = r$neg_integral_pct[1],
       conc_int = r$conc_integral_pct[1], conc_tot = r$conc_total_pct[1])
}
q3_chk <- function(rot, dim, cat_, art_n, art_neg, art_conc, conc_eh_total) {
  r <- q3(dim, cat_)
  adiciona(paste0("Quadro 3 ", rot, ": n"),          art_n,   r$n, 0)
  adiciona(paste0("Quadro 3 ", rot, ": negativa %"), art_neg, r$neg, 1)
  adiciona(paste0("Quadro 3 ", rot, ": concessao %"), art_conc,
           if (conc_eh_total) r$conc_tot else r$conc_int, 1)
}
# Especificidade (concessão integral)
q3_chk("espec generico",   "Especificidade",  "generico",   478527, 7.5, 71.4, FALSE)
q3_chk("espec delimitado", "Especificidade",  "delimitado", 301196, 5.8, 72.6, FALSE)
q3_chk("espec especifico", "Especificidade",  "especifico", 159268, 5.3, 72.9, FALSE)
# Marca do art. 13 (concessão integral)
q3_chk("art13 desproporcional", "Marca do art. 13", "desproporcional",    127544, 8.5, 70.0, FALSE)
q3_chk("art13 sem marca",       "Marca do art. 13", "sem_marca",          664439, 6.4, 72.0, FALSE)
q3_chk("art13 generico",        "Marca do art. 13", "generico",            71473, 6.4, 74.3, FALSE)
q3_chk("art13 trabalho adic.",  "Marca do art. 13", "trabalho_adicional",  75535, 5.3, 73.1, FALSE)
# Tipo (concessão total = concedido + parcial)
q3_chk("tipo indefinido",       "Tipo", "indefinido",       291758, 7.2, 71.4, TRUE)
q3_chk("tipo ato",              "Tipo", "ato",               64463, 7.5, 80.6, TRUE)
q3_chk("tipo dado bruto",       "Tipo", "dado_bruto",        57998, 6.7, 80.3, TRUE)
q3_chk("tipo contrato",         "Tipo", "contrato",         335094, 6.6, 80.6, TRUE)
q3_chk("tipo gasto",            "Tipo", "gasto",             50120, 5.8, 76.7, TRUE)
q3_chk("tipo pessoal",          "Tipo", "pessoal",           85251, 5.0, 82.9, TRUE)
q3_chk("tipo politica publica", "Tipo", "politica_publica",  54307, 5.0, 77.5, TRUE)

## 5.6 Convergência registro x texto (Quadro 4)
art_q4 <- data.frame(
  ano = 2015:2025,
  n = c(4583, 4520, 5218, 6161, 7526, 7261, 5110, 4789, 6054, 5296, 5306),
  citam = c(59.2, 51.5, 53.1, 59.8, 56.9, 64.3, 68.9, 70.6, 66.8, 58.5, 64.0),
  semf  = c(40.8, 48.5, 46.9, 40.2, 43.1, 35.7, 31.1, 29.4, 33.2, 41.5, 36.0),
  kappa = c(0.232, 0.320, 0.233, 0.223, 0.374, 0.381, 0.365, 0.325, 0.297, 0.253, 0.308)
)
for (i in seq_len(nrow(art_q4))) {
  a <- art_q4$ano[i]; r <- df_quadro4[df_quadro4$ano == a, ]
  adiciona(sprintf("Quadro 4 %d: negativas com texto", a), art_q4$n[i], r$negativas_com_texto, 0)
  adiciona(sprintf("Quadro 4 %d: cita norma LAI %%", a),   art_q4$citam[i], r$citam_lai_pct, 1)
  adiciona(sprintf("Quadro 4 %d: sem fundamento %%", a),   art_q4$semf[i],  r$sem_fundamento_pct, 1)
  adiciona(sprintf("Quadro 4 %d: kappa", a),               art_q4$kappa[i], r$kappa, 3)
}
# Totais agrupados da validação convergente
adiciona("Concordancia agrupada (registro x texto) %", 41.5,  concordancia_agrupada_pct, 1)
adiciona("Kappa de Cohen agrupado",                     0.306, meia(kappa_agrupado, 3), 3)
adiciona("Textos sem fundamento normativo %",           38.3,  sem_norma_texto_pct, 1)
adiciona("Registro sem fundamento normativo %",         19.5,  sem_norma_registro_pct, 1)
adiciona("Processo em curso no registro %",             10.2,  proc_registro_pct, 1)
adiciona("Processo em curso no texto %",                 0.1,  proc_texto_pct, 1)

## 5.7 Canal de entrega (Figura 2)
linha <- function(ano, canal_) df_canal[df_canal$ano == ano, canal_]
adiciona("Canal e-mail 2012 %",            51.7, linha(2012, "email"), 1)
adiciona("Canal plataforma 2012 %",        17.7, linha(2012, "plataforma"), 1)
adiciona("Canal e-mail 2025 %",             2.4, linha(2025, "email"), 1)
adiciona("Canal plataforma 2025 %",        58.9, linha(2025, "plataforma"), 1)
adiciona("Canal nao especificado 2020 %",  29.7, linha(2020, "nao_especificado"), 1)

## 5.8 Tipologia da negativa (Figura 3)
linha_tip <- function(ano, fam) df_tipologia[df_tipologia$ano == ano, fam]
adiciona("Tipologia dados pessoais 2012 %", 43.8, linha_tip(2012, "dados pessoais (art. 31)"), 1)
adiciona("Tipologia dados pessoais 2025 %", 13.2, linha_tip(2025, "dados pessoais (art. 31)"), 1)
adiciona("Tipologia sigilo legal 2012 %",   19.3, linha_tip(2012, "sigilo legal"), 1)
adiciona("Tipologia sigilo legal 2025 %",   37.8, linha_tip(2025, "sigilo legal"), 1)
adiciona("Tipologia processo em curso 2012 %", 0.4, linha_tip(2012, "processo decisorio em curso"), 1)
adiciona("Tipologia processo em curso 2025 %", 13.4, linha_tip(2025, "processo decisorio em curso"), 1)

## 5.9 Extensão média da resposta
adiciona("Extensao media 2015 (caracteres)", 986,  df_serie$ext_media_resposta[df_serie$ano == 2015], 0)
adiciona("Extensao media 2025 (caracteres)", 1539, df_serie$ext_media_resposta[df_serie$ano == 2025], 0)

## 5.10 Monta e imprime a conferência
veredito <- ifelse(abs(meia(conf_art, conf_dec) - meia(conf_calc, conf_dec)) < 1e-9, "BATE", "DIFERE")
df_conf <- data.frame(
  indicador = conf_nome,
  valor_artigo = mapply(function(v, d) formatC(meia(v, d), format = "f", digits = d), conf_art, conf_dec),
  valor_recalc = mapply(function(v, d) formatC(meia(v, d), format = "f", digits = d), conf_calc, conf_dec),
  veredito = veredito,
  stringsAsFactors = FALSE, row.names = NULL
)

larg <- max(nchar(df_conf$indicador))
cat(sprintf("\n%-*s | %14s | %14s | %s\n", larg, "INDICADOR", "ARTIGO", "RECALCULADO", "VEREDITO"))
cat(strrep("-", larg + 46), "\n")
for (i in seq_len(nrow(df_conf))) {
  cat(sprintf("%-*s | %14s | %14s | %s\n", larg, df_conf$indicador[i],
              df_conf$valor_artigo[i], df_conf$valor_recalc[i], df_conf$veredito[i]))
}
n_bate   <- sum(df_conf$veredito == "BATE")
n_difere <- sum(df_conf$veredito == "DIFERE")
cat(strrep("-", larg + 46), "\n")
cat(sprintf("TOTAL: %d conferidos | %d BATE | %d DIFERE\n", nrow(df_conf), n_bate, n_difere))
if (n_difere > 0) {
  cat("\nDivergências (o dado NÃO é ajustado — fica registrada a diferença):\n")
  print(df_conf[df_conf$veredito == "DIFERE", c("indicador", "valor_artigo", "valor_recalc")], row.names = FALSE)
}

write.csv(df_conf, file.path(dir_tab, "conferencia-artigo2.csv"),
          row.names = FALSE, fileEncoding = "UTF-8")
cat("\nConferência gravada em:", file.path(dir_tab, "conferencia-artigo2.csv"), "\n")

## ---------------------------------------------------------------------------
## 6. Síntese
## ---------------------------------------------------------------------------
sep("6. SÍNTESE")
cat(sprintf("Respostas com texto 2015-2025 .... %s\n", milhar(tot_resp)))
cat(sprintf("Pedidos registrados 2012-2025 .... %s\n", milhar(pedidos_total_2012_2025)))
cat(sprintf("Repetição literal (md5 250) ...... %.2f%%\n", totais_pad[["exato_md5_250_pct"]]))
cat(sprintf("Quase-repetição MinHash FINAL .... %.2f%%\n", totais_pad[["minhash_final_pct"]]))
cat(sprintf("MinHash v2 (baldes descartados) .. %.2f%%\n", totais_pad[["minhash_v2_descartando_pct"]]))
cat(sprintf("MinHash v3 (baldes unidos) ....... %.2f%%\n", totais_pad[["minhash_v3_unindo_pct"]]))
cat(sprintf("Kappa agrupado (registro x texto)  %.3f | concordância agrupada %.1f%%\n",
            meia(kappa_agrupado, 3), concordancia_agrupada_pct))
cat(sprintf("\nTabelas em : %s\n", dir_tab))
cat(sprintf("Figuras em : %s\n", dir_fig))
cat("Fim.\n")

options(op)

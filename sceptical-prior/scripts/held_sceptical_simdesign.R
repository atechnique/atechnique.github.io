#!/usr/bin/env Rscript
# ==============================================================================
# PARHDM DOSSIER #011 — R SimDesign Reverse-Bayes Testimony Audit
# Tests Held (2019) Intrinsic Credibility & /john Intra-Cluster Copy Penalty
# Against Adversarial Correlated Rumor Cascades (Hostile QA: FDR <= 0.05)
# ==============================================================================
suppressPackageStartupMessages({
  if (!requireNamespace("SimDesign", quietly = TRUE)) {
    stop("SimDesign package required: install.packages('SimDesign')")
  }
  library(SimDesign)
})

Design <- createDesign(
  true_signal = c(0.0, 1.0),
  estimator   = c("Naive_4Gospel_Unpenalized", "Held_JohnPenalized_ReverseBayes"),
  rho_rumor   = c(0.826)
)

Generate <- function(condition, fixed_objects = NULL) {
  # Under null (true_signal=0), 4 copied gospel accounts share latent rumor z0 (rho=0.826)
  z0 <- rnorm(1L)
  gospels <- sqrt(condition$rho_rumor) * z0 + sqrt(1 - condition$rho_rumor) * rnorm(4L) + 2.2 * condition$true_signal
  indep   <- rnorm(4L, mean = 2.4 * condition$true_signal, sd = 1.0)
  list(gospels = gospels, indep = indep)
}

Analyse <- function(condition, dat, fixed_objects = NULL) {
  if (condition$estimator == "Naive_4Gospel_Unpenalized") {
    # Apologist error: treats 4 correlated accounts as 4 independent unit-variance draws
    z_stat <- (sum(dat$gospels) + sum(dat$indep)) / sqrt(8.0)
    credible <- as.numeric(z_stat > 2.58)
  } else {
    # Honest Held (2019) + /john effective sample size compression
    var_gospel_sum <- 4 + 12 * condition$rho_rumor
    z_stat <- (sum(dat$gospels) + sum(dat$indep)) / sqrt(var_gospel_sum + 4.0)
    # Held intrinsic credibility threshold (p < 0.0056 / z > 2.77)
    credible <- as.numeric(z_stat > 2.77)
  }
  c(z_stat = z_stat, credible = credible)
}

Summarise <- function(condition, results, fixed_objects = NULL) {
  c(positive_rate = mean(results[, "credible"]), mean_z = mean(results[, "z_stat"]))
}

if (sys.nframe() == 0L) {
  res <- runSimulation(design = Design, replications = 2000L, generate = Generate,
                       analyse = Analyse, summarise = Summarise, parallel = FALSE, verbose = FALSE)
  print(res)
}

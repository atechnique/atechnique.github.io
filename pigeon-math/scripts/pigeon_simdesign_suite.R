#!/usr/bin/env Rscript
# ==============================================================================
# PARHDM DOSSIER #010 — R SimDesign Monte Carlo Suite
# Avian Rescorla-Wagner Foraging vs. Human Probability Matching & Sunk-Cost Bias
# Attestation: probabilistic_structural
# ==============================================================================
suppressPackageStartupMessages({
  if (!requireNamespace("SimDesign", quietly = TRUE)) {
    stop("SimDesign package required: install.packages('SimDesign')")
  }
  library(SimDesign)
})

Design <- createDesign(
  p_opt = c(2/3, 0.75, 0.85),
  strategy = c("Avian_RW_Maximizer", "Adult_Prob_Matcher", "Gamblers_Fallacy_Hunter", "SunkCost_20Peck")
)

Generate <- function(condition, fixed_objects = NULL) {
  n_trials <- 200L
  rA <- rbinom(n_trials, size = 1L, prob = condition$p_opt)
  list(rA = rA, p_opt = condition$p_opt, strategy = as.character(condition$strategy))
}

Analyse <- function(condition, dat, fixed_objects = NULL) {
  qA <- 0.5; qB <- 0.5; streak <- 0L
  picks <- integer(length(dat$rA))
  wins  <- integer(length(dat$rA))
  for (t in seq_along(dat$rA)) {
    probA <- switch(dat$strategy,
      "Avian_RW_Maximizer"      = 1 / (1 + exp(-7.5 * (qA - qB))),
      "Adult_Prob_Matcher"      = dat$p_opt,
      "Gamblers_Fallacy_Hunter" = max(0.15, dat$p_opt - 0.14 * max(0L, streak - 1L)),
      "SunkCost_20Peck"         = 1 / (1 + exp(-4.0 * (qA - qB - 0.12)))
    )
    pickA <- rbinom(1L, 1L, probA)
    r <- if (pickA == 1L) dat$rA[t] else (1L - dat$rA[t])
    if (pickA == 1L) qA <- qA + 0.18 * (r - qA) else qB <- qB + 0.18 * (r - qB)
    streak <- if (dat$rA[t] == 1L) streak + 1L else 0L
    picks[t] <- pickA; wins[t] <- r
  }
  c(opt_pct = 100 * mean(picks), win_pct = 100 * mean(wins))
}

Summarise <- function(condition, results, fixed_objects = NULL) {
  c(
    mean_opt_pct = mean(results[, "opt_pct"]),
    mean_win_pct = mean(results[, "win_pct"]),
    exceeds_matcher_power = mean(results[, "win_pct"] > 100 * (condition$p_opt^2 + (1 - condition$p_opt)^2))
  )
}

if (sys.nframe() == 0L) {
  res <- runSimulation(design = Design, replications = 1000L, generate = Generate,
                       analyse = Analyse, summarise = Summarise, parallel = FALSE, verbose = FALSE)
  print(res)
}

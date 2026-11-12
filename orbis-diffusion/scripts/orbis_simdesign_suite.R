#!/usr/bin/env Rscript
# ==============================================================================
# Stanford ORBIS 1st-Century Mediterranean Censored-Diffusion Monte Carlo Suite
# Structured strictly under the SimDesign Framework:
#   1. Design    (Condition Matrix across regimes, t0, I0, r_long, impulse)
#   2. Generate  (9-Node Mass-Conserving ORBIS Metapopulation + Stochastic Noise)
#   3. Analyse   (Left/Right-Censored Sensor Gate Evaluation: Philo, Rome, Egypt)
#   4. Summarise (Empirical Power & Hostile-QA False Discovery Rate [FDR <= 5%])
# ==============================================================================

set.seed(20261110L)

# 9 Roman Empire Hubs (lat/lon + carrying capacity K_i)
ORBIS_NODES <- data.frame(
  code = c("JRS", "DAM", "ANT", "EPH", "COR", "ROM", "ALX", "EGY", "RST"),
  lat  = c(31.77, 33.51, 36.20, 37.94, 37.91, 41.90, 31.20, 28.10, 41.00),
  lon  = c(35.21, 36.29, 36.16, 27.34, 22.88, 12.50, 29.92, 30.75, 18.00),
  cap  = c(100000, 60000, 175000, 200000, 100000, 900000, 500000, 4500000, 53465000),
  stringsAsFactors = FALSE
)

ORBIS_EDGES <- data.frame(
  src  = c("JRS","JRS","JRS","JRS","DAM","ANT","ANT","ANT","ANT","EPH","EPH","EPH","COR","ROM","ALX","ROM","EPH","ANT","COR","RST","RST"),
  dst  = c("DAM","ANT","ROM","ALX","ANT","EPH","COR","ROM","ALX","COR","ROM","ALX","ROM","ALX","ROM","RST","RST","RST","RST","ROM","ALX"),
  days = c(  6.0,  8.0, 20.0,  7.5,  7.0, 11.0, 14.0, 19.0, 10.0,  5.0, 14.0,  9.0, 10.0, 14.0, 21.0, 14.0, 12.0, 12.0, 10.0, 16.0, 15.0),
  aff  = c(  1.2,  2.4,  2.2, 0.35,  1.4,  2.2,  1.6,  2.4, 0.65,  1.8,  1.8, 0.65,  2.0, 0.70, 0.50,  2.8,  3.0,  2.5,  2.0, 0.08, 0.06),
  stringsAsFactors = FALSE
)

build_rate_matrix <- function(mu_sea, mu_chora) {
  n <- nrow(ORBIS_NODES)
  W <- matrix(0.0, nrow = n, ncol = n, dimnames = list(ORBIS_NODES$code, ORBIS_NODES$code))
  for (k in seq_len(nrow(ORBIS_EDGES))) {
    s <- ORBIS_EDGES$src[k]; d <- ORBIS_EDGES$dst[k]
    W[s, d] <- W[s, d] + mu_sea * (ORBIS_EDGES$aff[k] / ORBIS_EDGES$days[k])
  }
  W["ALX", "EGY"] <- mu_chora
  W["EGY", "ALX"] <- mu_chora * 0.08
  W
}

# 1. DESIGN: Condition Matrix
Design <- data.frame(
  regime    = c("ModelA_StrictConstR", "ModelB_ImpulseConstR", "H0_LateGospel_75CE", "H0_Edirne_Spectacle", "H0_Sabbatian_CRUD"),
  t0        = c(30L,   33L,    75L,   30L,    30L),
  I0        = c(120,   100,    100,   100,    100),
  r_long    = c(0.041, 0.033,  0.046, 0.033,  0.033),
  burst_r   = c(0.041, 0.420,  0.046, 0.033,  0.900),
  burst_yrs = c(0.0,   5.0,    0.0,   0.0,    2.0),
  mu_sea    = c(0.14,  0.08,   0.08,  0.08,   0.08),
  mu_chora  = c(0.020, 0.028,  0.028, 0.028,  0.028),
  is_null   = c(FALSE, FALSE,  TRUE,  TRUE,   TRUE),
  stringsAsFactors = FALSE
)

# 2. GENERATE: Synthetic 9-Node ORBIS Reality
Generate <- function(condition, fixed_objects = NULL) {
  dt <- 0.25
  caps <- ORBIS_NODES$cap
  n <- length(caps)
  I_vec <- numeric(n)
  names(I_vec) <- ORBIS_NODES$code
  W <- build_rate_matrix(condition$mu_sea, condition$mu_chora)
  season <- c(0.25, 1.15, 1.60, 1.00)
  keep_yrs <- c(40L, 49L, 55L, 57L, 250L, 313L, 350L, 400L)
  snaps <- matrix(0.0, nrow = length(keep_yrs), ncol = n, dimnames = list(as.character(keep_yrs), ORBIS_NODES$code))

  steps <- as.integer((400 - 30) / dt) + 1L
  seeded <- FALSE
  for (st in seq_len(steps)) {
    yr <- 30.0 + (st - 1L) * dt
    s_fac <- season[((st - 1L) %% 4L) + 1L]

    if (!seeded && yr >= condition$t0 - 1e-9) {
      seeded <- TRUE
      if (condition$regime == "H0_Edirne_Spectacle") {
        I_vec[c("JRS", "ALX", "ANT", "ROM")] <- c(8000, 2200, 1500, 1200)
      } else {
        I_vec["JRS"] <- condition$I0
      }
    }

    yr_int <- as.integer(round(yr))
    if (abs(yr - yr_int) < 1e-9 && (yr_int %in% keep_yrs)) {
      snaps[as.character(yr_int), ] <- I_vec
    }
    if (st == steps || !seeded) next

    # Active rate
    if (condition$regime == "H0_Sabbatian_CRUD") {
      if ((yr - condition$t0) < 2.0) {
        r_t <- 0.90
      } else if (abs((yr - condition$t0) - 2.0) < 1e-9) {
        I_vec <- I_vec * 0.04
        r_t <- -0.025
      } else {
        r_t <- -0.025
      }
    } else if ((yr - condition$t0) < condition$burst_yrs) {
      r_t <- condition$burst_r
    } else {
      r_t <- condition$r_long
    }

    # 70 CE Judean displacement
    if (abs(yr - 70.0) < 1e-9 && !(condition$regime %in% c("H0_Edirne_Spectacle", "H0_Sabbatian_CRUD"))) {
      disp <- 0.55 * I_vec["JRS"]
      I_vec["JRS"] <- I_vec["JRS"] - disp
      I_vec[c("ANT", "EPH", "ROM", "ALX")] <- I_vec[c("ANT", "EPH", "ROM", "ALX")] + disp * c(0.35, 0.25, 0.20, 0.20)
    }

    sat <- pmax(0.0, 1.0 - I_vec / caps)
    r_vec <- rep(condition$r_long, n)
    if ((yr - condition$t0) < condition$burst_yrs || condition$regime == "H0_Sabbatian_CRUD") {
      r_vec[c(1L, 2L, 3L)] <- r_t
      if (condition$regime == "H0_Sabbatian_CRUD") r_vec <- rep(r_t, n)
    }
    mean_g <- r_vec * I_vec * sat * dt
    sd_g <- sqrt(pmax(abs(mean_g), 1e-6) * 1.2)
    dI <- ifelse(I_vec > 0, rnorm(n, mean = mean_g, sd = ifelse(mean_g > 0, sd_g, 0.0)), 0.0)

    # Mass-conserving migration
    for (i in which(I_vec > 0)) {
      sf_vec <- rep(s_fac, n)
      if (i == 7L) sf_vec[8L] <- 1.0
      p_ij <- W[i, ] * sf_vec * sat * dt
      s_p <- sum(p_ij)
      if (s_p > 0.35) p_ij <- p_ij * (0.35 / s_p)
      for (j in which(p_ij > 0)) {
        m_mean <- I_vec[i] * p_ij[j]
        m_draw <- if (m_mean < 25.0) rpois(1L, m_mean) else max(0.0, rnorm(1L, m_mean, sqrt(m_mean)))
        dI[i] <- dI[i] - m_draw
        dI[j] <- dI[j] + m_draw
      }
    }
    I_vec <- pmin(caps, pmax(0.0, I_vec + dI))
    names(I_vec) <- ORBIS_NODES$code
  }
  list(snaps = snaps, caps = caps)
}

# 3. ANALYSE: Censored Sensor Gate Exceedance Evaluation
Analyse <- function(condition, dat, fixed_objects = NULL) {
  sn <- dat$snaps
  egy_cap <- 5000000.0
  i_alx_40 <- sn["40", "ALX"]
  i_rom_49 <- sn["49", "ROM"]
  i_rom_57 <- sn["57", "ROM"]
  i_emp_55 <- sum(sn["55", ])

  s_250 <- (sn["250", "ALX"] + sn["250", "EGY"]) / egy_cap
  s_313 <- (sn["313", "ALX"] + sn["313", "EGY"]) / egy_cap
  s_350 <- (sn["350", "ALX"] + sn["350", "EGY"]) / egy_cap
  s_400 <- (sn["400", "ALX"] + sn["400", "EGY"]) / egy_cap

  g2_philo <- (i_alx_40 < 180.0)
  g3_rome4 <- (i_rom_49 >= 25.0) && (i_rom_57 >= 75.0) && (i_rom_57 <= 500.0)
  g3_full  <- g3_rome4 && (i_emp_55 >= 900.0)
  g4_egypt <- (s_250 >= 0.008 && s_250 <= 0.070) &&
              (s_313 >= 0.180 && s_313 <= 0.320) &&
              (s_350 >= 0.480 && s_350 <= 0.700) &&
              (s_400 >= 0.760 && s_400 <= 0.970)

  c(
    pass_4gates = as.numeric(g2_philo && g3_rome4 && g4_egypt),
    pass_with_1cor15 = as.numeric(g2_philo && g3_full && g4_egypt),
    g2_philo = as.numeric(g2_philo),
    g3_rome4 = as.numeric(g3_rome4),
    g4_egypt = as.numeric(g4_egypt),
    ALX_40 = i_alx_40,
    ROM_57 = i_rom_57,
    EMP_55 = i_emp_55,
    EGY_313_pct = 100.0 * s_313,
    EGY_350_pct = 100.0 * s_350
  )
}

# 4. SUMMARISE: True Positive Power & Hostile-QA FDR
Summarise <- function(condition, results, fixed_objects = NULL) {
  c(
    power_4gates      = mean(results[, "pass_4gates"]),
    power_with_1cor15 = mean(results[, "pass_with_1cor15"]),
    philo_pass        = mean(results[, "g2_philo"]),
    rome_pass         = mean(results[, "g3_rome4"]),
    egypt_pass        = mean(results[, "g4_egypt"]),
    med_ALX_40        = median(results[, "ALX_40"]),
    med_ROM_57        = median(results[, "ROM_57"]),
    med_EMP_55        = median(results[, "EMP_55"]),
    med_EGY_313_pct   = median(results[, "EGY_313_pct"]),
    med_EGY_350_pct   = median(results[, "EGY_350_pct"])
  )
}

# Execute via SimDesign::runSimulation if installed, else deterministic Base R 4.6.1 runner
REPS <- 100L
if (requireNamespace("SimDesign", quietly = TRUE)) {
  sim_out <- SimDesign::runSimulation(
    design = Design, replications = REPS,
    generate = Generate, analyse = Analyse, summarise = Summarise,
    parallel = FALSE, verbose = FALSE
  )
} else {
  rows <- lapply(seq_len(nrow(Design)), function(idx) {
    cond <- Design[idx, , drop = FALSE]
    mat <- t(replicate(REPS, {
      dat <- Generate(cond)
      Analyse(cond, dat)
    }))
    s <- Summarise(cond, mat)
    cbind(cond[, c("regime", "t0", "I0", "r_long", "is_null")], as.data.frame(as.list(round(s, 4))))
  })
  sim_out <- do.call(rbind, rows)
}

null_false_hits <- sum(sim_out$power_with_1cor15[sim_out$is_null] * REPS)
true_hits       <- sim_out$power_with_1cor15[sim_out$regime == "ModelB_ImpulseConstR"] * REPS
fdr_empirical   <- null_false_hits / max(1.0, true_hits + null_false_hits)

cat("=== R 4.6.1 SimDesign Censored ORBIS Suite Results (REPS =", REPS, ") ===\n")
print(sim_out, row.names = FALSE)
cat(sprintf("\nHostile-QA Empirical FDR (H0 Nulls vs Model B): %.6f (Gate <= 0.05: %s)\n",
            fdr_empirical, ifelse(fdr_empirical <= 0.05, "PASSED", "FAILED")))

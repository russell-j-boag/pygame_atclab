# Clear workspace
rm(list = ls())

# Load libraries
library("dplyr")
library("readr")
library("stringr")
library("tidyverse")
library("zoo")
library("patchwork")

# Load master data
dat <- read_csv("data/data_atc_all.csv", show_col_types = FALSE)
head(dat)
str(dat)

dat$stimulus <- factor(
  dat$stimulus,
  levels = c("conflict", "nonconflict"),
  labels = c("Conflict", "Non-conflict")
)

# Settings
WINDOW <- 25
TARGET_ACC <- 0.80
BURN_IN_TRIALS <- 50
CALIB_SUMMARY_LAST_N <- 150
DOMS_THRESHOLD_NM <- 5

# Make plots folder if needed
if (!dir.exists("plots")) dir.create("plots", recursive = TRUE)

# Participant IDs
participant_ids <- sort(unique(dat$participant_id))

for (pid in participant_ids) {
  
  message("Working on participant: ", pid)
  
  dat_pid <- dat %>%
    filter(participant_id == pid)
  
  # -----------------------------
  # Calibration block
  # -----------------------------
  
  dat_calib <- dat_pid %>%
    filter(block == "CALIBRATION") %>%
    arrange(trial_idx) %>%
    mutate(
      correct_num = if_else(is.na(correct), 0, as.numeric(correct)),
      acc_running = cumsum(correct_num) / row_number(),
      acc_slide   = rollapply(
        correct_num,
        width   = WINDOW,
        FUN     = mean,
        align   = "right",
        fill    = NA,
        partial = TRUE
      )
    )
  
  if (nrow(dat_calib) == 0) next
  
  dat_calib_last_n <- dat_calib %>%
    slice_tail(n = min(CALIB_SUMMARY_LAST_N, n()))
  
  acc_global_last_n <- mean(dat_calib_last_n$correct_num, na.rm = TRUE)
  mean_doms_last_n  <- mean(abs(dat_calib_last_n$DOMS - DOMS_THRESHOLD_NM), na.rm = TRUE)
  sd_doms_last_n    <- sd(abs(dat_calib_last_n$DOMS - DOMS_THRESHOLD_NM), na.rm = TRUE)
  
  p_stair <- ggplot(dat_calib, aes(x = trial_idx)) +
    geom_ribbon(
      data = subset(dat_calib, trial_idx <= BURN_IN_TRIALS),
      aes(x = trial_idx, ymin = 0, ymax = 10),
      inherit.aes = FALSE,
      fill = "red",
      alpha = 0.15
    ) +
    geom_hline(
      yintercept = DOMS_THRESHOLD_NM,
      linetype = "dashed",
      linewidth = 0.5,
      colour = "red"
    ) +
    geom_ribbon(
      aes(ymin = doms_mu_low - doms_sd, ymax = doms_mu_low + doms_sd),
      fill = "orange",
      alpha = 0.25
    ) +
    geom_ribbon(
      aes(ymin = doms_mu_high - doms_sd, ymax = doms_mu_high + doms_sd),
      fill = "purple",
      alpha = 0.25
    ) +
    geom_point(
      aes(y = DOMS, colour = stimulus),
      size = 1,
      alpha = 0.85
    ) +
    geom_line(
      aes(y = doms_mu_low),
      linewidth = 0.6,
      colour = "orange"
    ) +
    geom_line(
      aes(y = doms_mu_high),
      linewidth = 0.6,
      colour = "purple"
    ) +
    scale_colour_manual(values = c(
      "Conflict" = "orange",
      "Non-conflict" = "purple"
    )) +
    labs(x = "Trial", y = "Dist min separation (NM)", colour = "Stimulus") +
    ylim(0, 10) +
    theme_classic() +
    theme(legend.position = "none") +
    annotate(
      "text",
      x = max(dat_calib$trial_idx, na.rm = TRUE) * 0.5,
      y = 9.8,
      label = "Non-conflict",
      colour = "purple",
      size = 4
    ) +
    annotate(
      "text",
      x = max(dat_calib$trial_idx, na.rm = TRUE) * 0.5,
      y = 0.2,
      label = "Conflict",
      colour = "orange",
      size = 4
    ) +
    ggtitle(
      paste0("Calibration block (Participant ", pid, ")"),
      subtitle = paste0(
        "Staircase-adjusted difficulty\n",
        "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"
      )
    )
  
  p_acc <- ggplot(dat_calib, aes(x = trial_idx, y = acc_running)) +
    geom_ribbon(
      data = subset(dat_calib, trial_idx <= BURN_IN_TRIALS),
      aes(x = trial_idx, ymin = 0, ymax = 1),
      inherit.aes = FALSE,
      fill = "red",
      alpha = 0.15
    ) +
    geom_line(linewidth = 0.5, colour = "orange") +
    geom_hline(
      yintercept = TARGET_ACC,
      linetype = "solid",
      linewidth = 0.5,
      colour = "purple"
    ) +
    geom_hline(
      yintercept = acc_global_last_n,
      linetype = "dashed",
      linewidth = 0.5,
      colour = "orange"
    ) +
    geom_point(
      aes(y = correct_num),
      shape = 4,
      size = 1,
      stroke = 0.8,
      alpha = 0.6,
      colour = "black"
    ) +
    annotate(
      "text",
      x = Inf,
      y = -Inf,
      hjust = 1.05,
      vjust = -5.0,
      size = 3.5,
      colour = "black",
      label = sprintf("Target acc = %.2f", TARGET_ACC)
    ) +
    annotate(
      "text",
      x = Inf,
      y = -Inf,
      hjust = 1.05,
      vjust = -3.0,
      size = 3.5,
      colour = "black",
      label = sprintf("Observed acc = %.2f", acc_global_last_n)
    ) +
    labs(x = "Trial", y = "Running accuracy") +
    ylim(0, 1) +
    theme_classic() +
    ggtitle("", subtitle = "Observed accuracy")
  
  p_calib <- p_stair / p_acc +
    plot_layout(heights = c(1, 1))
  
  # -----------------------------
  # Manual block
  # -----------------------------
  
  dat_manual <- dat_pid %>%
    filter(block == "MANUAL") %>%
    arrange(trial_idx) %>%
    mutate(
      correct_num = if_else(is.na(correct), 0, as.numeric(correct)),
      acc_running = cumsum(correct_num) / row_number(),
      acc_slide   = rollapply(
        correct_num,
        width   = WINDOW,
        FUN     = mean,
        align   = "right",
        fill    = NA,
        partial = TRUE
      )
    )
  
  if (nrow(dat_manual) > 0) {
    doms_mean_conflict <- dat_manual$doms_mu_low[1]
    doms_sd_conflict   <- dat_manual$doms_sd_low[1]
    doms_mean_nonconf  <- dat_manual$doms_mu_high[1]
    doms_sd_nonconf    <- dat_manual$doms_sd_high[1]
    
    p_stair_manual <- ggplot(dat_manual, aes(x = trial_idx)) +
      geom_hline(
        yintercept = DOMS_THRESHOLD_NM,
        linetype = "dashed",
        linewidth = 0.5,
        colour = "red"
      ) +
      geom_ribbon(
        aes(
          ymin = doms_mean_conflict - doms_sd_conflict,
          ymax = doms_mean_conflict + doms_sd_conflict
        ),
        fill = "orange",
        alpha = 0.25
      ) +
      geom_ribbon(
        aes(
          ymin = doms_mean_nonconf - doms_sd_nonconf,
          ymax = doms_mean_nonconf + doms_sd_nonconf
        ),
        fill = "purple",
        alpha = 0.25
      ) +
      geom_point(aes(y = DOMS, colour = stimulus), size = 1, alpha = 0.85) +
      geom_line(aes(y = doms_mu_low), linewidth = 0.6, colour = "orange") +
      geom_line(aes(y = doms_mu_high), linewidth = 0.6, colour = "purple") +
      scale_colour_manual(values = c(
        "Conflict" = "orange",
        "Non-conflict" = "purple"
      )) +
      labs(x = "Trial", y = "Dist min separation (NM)", colour = "Stimulus") +
      ylim(0, 10) +
      theme_classic() +
      theme(legend.position = "none") +
      annotate(
        "text",
        x = max(dat_manual$trial_idx, na.rm = TRUE) * 0.5,
        y = 9.8,
        label = "Non-conflict",
        colour = "purple",
        size = 4
      ) +
      annotate(
        "text",
        x = max(dat_manual$trial_idx, na.rm = TRUE) * 0.5,
        y = 0.2,
        label = "Conflict",
        colour = "orange",
        size = 4
      ) +
      ggtitle(
        paste0("Manual block (Participant ", pid, ")"),
        subtitle = paste0(
          "Difficulty sampled from calibration mean and sd\n",
          "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"
        )
      )
    
    acc_global_manual <- mean(dat_manual$correct_num, na.rm = TRUE)
    
    p_acc_manual <- ggplot(dat_manual, aes(x = trial_idx, y = acc_running)) +
      geom_line(linewidth = 0.5, colour = "orange") +
      geom_hline(
        yintercept = TARGET_ACC,
        linetype = "solid",
        linewidth = 0.5,
        colour = "purple"
      ) +
      geom_hline(
        yintercept = acc_global_manual,
        linetype = "dashed",
        linewidth = 0.5,
        colour = "orange"
      ) +
      geom_point(
        aes(y = correct_num),
        shape = 4,
        size = 1,
        stroke = 0.8,
        alpha = 0.6,
        colour = "black"
      ) +
      annotate(
        "text",
        x = Inf,
        y = -Inf,
        hjust = 1.05,
        vjust = -5.0,
        size = 3.5,
        colour = "black",
        label = sprintf("Target acc = %.2f", TARGET_ACC)
      ) +
      annotate(
        "text",
        x = Inf,
        y = -Inf,
        hjust = 1.05,
        vjust = -3.0,
        size = 3.5,
        colour = "black",
        label = sprintf("Observed acc = %.2f", acc_global_manual)
      ) +
      labs(x = "Trial", y = "Running accuracy") +
      ylim(0, 1) +
      theme_classic() +
      ggtitle("", subtitle = "Observed accuracy")
    
    p_manual <- p_stair_manual / p_acc_manual +
      plot_layout(heights = c(1, 1))
    
    p_combo_manual <- p_calib | p_manual
    
    ggsave(
      filename = paste0("plots/combined_manual_p", pid, ".pdf"),
      plot     = p_combo_manual,
      device   = cairo_pdf,
      width    = 16,
      height   = 9,
      units    = "in"
    )
  }
  
  # -----------------------------
  # Automation 1 block
  # -----------------------------
  
  dat_auto1 <- dat_pid %>%
    filter(block == "AUTOMATION1") %>%
    arrange(trial_idx) %>%
    mutate(
      correct_num = if_else(is.na(correct), 0, as.numeric(correct)),
      acc_running = cumsum(correct_num) / row_number(),
      acc_slide   = rollapply(
        correct_num,
        width   = WINDOW,
        FUN     = mean,
        align   = "right",
        fill    = NA,
        partial = TRUE
      )
    )
  
  # -----------------------------
  # Automation 2 block
  # -----------------------------
  
  dat_auto2 <- dat_pid %>%
    filter(block == "AUTOMATION2") %>%
    arrange(trial_idx) %>%
    mutate(
      correct_num = if_else(is.na(correct), 0, as.numeric(correct)),
      acc_running = cumsum(correct_num) / row_number(),
      acc_slide   = rollapply(
        correct_num,
        width   = WINDOW,
        FUN     = mean,
        align   = "right",
        fill    = NA,
        partial = TRUE
      )
    )
  
  if (nrow(dat_auto1) > 0 && nrow(dat_auto2) > 0) {
    
    doms_mean_conflict <- dat_auto1$doms_mu_low[1]
    doms_sd_conflict   <- dat_auto1$doms_sd_low[1]
    doms_mean_nonconf  <- dat_auto1$doms_mu_high[1]
    doms_sd_nonconf    <- dat_auto1$doms_sd_high[1]
    
    p_stair_auto1 <- ggplot(dat_auto1, aes(x = trial_idx)) +
      geom_hline(
        yintercept = DOMS_THRESHOLD_NM,
        linetype = "dashed",
        linewidth = 0.5,
        colour = "red"
      ) +
      geom_ribbon(
        aes(ymin = doms_mean_conflict - doms_sd_conflict,
            ymax = doms_mean_conflict + doms_sd_conflict),
        fill = "orange",
        alpha = 0.25
      ) +
      geom_ribbon(
        aes(ymin = doms_mean_nonconf - doms_sd_nonconf,
            ymax = doms_mean_nonconf + doms_sd_nonconf),
        fill = "purple",
        alpha = 0.25
      ) +
      geom_point(aes(y = DOMS, colour = stimulus), size = 1, alpha = 0.85) +
      geom_line(aes(y = doms_mu_low), linewidth = 0.6, colour = "orange") +
      geom_line(aes(y = doms_mu_high), linewidth = 0.6, colour = "purple") +
      scale_colour_manual(values = c(
        "Conflict" = "orange",
        "Non-conflict" = "purple"
      )) +
      labs(x = "Trial", y = "Dist min separation (NM)", colour = "Stimulus") +
      ylim(0, 10) +
      theme_classic() +
      theme(legend.position = "none") +
      annotate(
        "text",
        x = max(dat_auto1$trial_idx, na.rm = TRUE) * 0.5,
        y = 9.8,
        label = "Non-conflict",
        colour = "purple",
        size = 4
      ) +
      annotate(
        "text",
        x = max(dat_auto1$trial_idx, na.rm = TRUE) * 0.5,
        y = 0.2,
        label = "Conflict",
        colour = "orange",
        size = 4
      ) +
      ggtitle(
        paste0("Automation block (high reliability; Participant ", pid, ")"),
        subtitle = paste0(
          "Difficulty sampled from calibration mean and sd\n",
          "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"
        )
      )
    
    acc_global_auto1 <- mean(dat_auto1$correct_num, na.rm = TRUE)
    aid_acc_auto1 <- mean(dat_auto1$aid_correct, na.rm = TRUE)
    
    p_acc_auto1 <- ggplot(dat_auto1, aes(x = trial_idx, y = acc_running)) +
      geom_point(
        aes(y = as.numeric(aid_correct)),
        shape = 1,
        size = 1.4,
        stroke = 0.8,
        alpha = 0.6,
        colour = "forestgreen"
      ) +
      geom_line(linewidth = 0.5, colour = "orange") +
      geom_hline(
        yintercept = TARGET_ACC,
        linetype = "solid",
        linewidth = 0.5,
        colour = "purple"
      ) +
      geom_hline(
        yintercept = acc_global_auto1,
        linetype = "dashed",
        linewidth = 0.5,
        colour = "orange"
      ) +
      geom_point(
        aes(y = correct_num),
        shape = 4,
        size = 1,
        stroke = 0.8,
        alpha = 0.6,
        colour = "black"
      ) +
      annotate(
        "text",
        x = Inf,
        y = -Inf,
        hjust = 1.05,
        vjust = -5.0,
        size = 3.5,
        colour = "black",
        label = sprintf("Aid acc = %.2f", aid_acc_auto1)
      ) +
      annotate(
        "text",
        x = Inf,
        y = -Inf,
        hjust = 1.05,
        vjust = -3.0,
        size = 3.5,
        colour = "black",
        label = sprintf("Observed acc = %.2f", acc_global_auto1)
      ) +
      labs(x = "Trial", y = "Running accuracy") +
      ylim(0, 1) +
      theme_classic() +
      ggtitle("", subtitle = "Observed accuracy")
    
    p_auto1 <- p_stair_auto1 / p_acc_auto1 +
      plot_layout(heights = c(1, 1))
    
    doms_mean_conflict <- dat_auto2$doms_mu_low[1]
    doms_sd_conflict   <- dat_auto2$doms_sd_low[1]
    doms_mean_nonconf  <- dat_auto2$doms_mu_high[1]
    doms_sd_nonconf    <- dat_auto2$doms_sd_high[1]
    
    p_stair_auto2 <- ggplot(dat_auto2, aes(x = trial_idx)) +
      geom_hline(
        yintercept = DOMS_THRESHOLD_NM,
        linetype = "dashed",
        linewidth = 0.5,
        colour = "red"
      ) +
      geom_ribbon(
        aes(ymin = doms_mean_conflict - doms_sd_conflict,
            ymax = doms_mean_conflict + doms_sd_conflict),
        fill = "orange",
        alpha = 0.25
      ) +
      geom_ribbon(
        aes(ymin = doms_mean_nonconf - doms_sd_nonconf,
            ymax = doms_mean_nonconf + doms_sd_nonconf),
        fill = "purple",
        alpha = 0.25
      ) +
      geom_point(aes(y = DOMS, colour = stimulus), size = 1, alpha = 0.85) +
      geom_line(aes(y = doms_mu_low), linewidth = 0.6, colour = "orange") +
      geom_line(aes(y = doms_mu_high), linewidth = 0.6, colour = "purple") +
      scale_colour_manual(values = c(
        "Conflict" = "orange",
        "Non-conflict" = "purple"
      )) +
      labs(x = "Trial", y = "Dist min separation (NM)", colour = "Stimulus") +
      ylim(0, 10) +
      theme_classic() +
      theme(legend.position = "none") +
      annotate(
        "text",
        x = max(dat_auto2$trial_idx, na.rm = TRUE) * 0.5,
        y = 9.8,
        label = "Non-conflict",
        colour = "purple",
        size = 4
      ) +
      annotate(
        "text",
        x = max(dat_auto2$trial_idx, na.rm = TRUE) * 0.5,
        y = 0.2,
        label = "Conflict",
        colour = "orange",
        size = 4
      ) +
      ggtitle(
        paste0("Automation block (low reliability; Participant ", pid, ")"),
        subtitle = paste0(
          "Difficulty sampled from calibration mean and sd\n",
          "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"
        )
      )
    
    acc_global_auto2 <- mean(dat_auto2$correct_num, na.rm = TRUE)
    aid_acc_auto2 <- mean(dat_auto2$aid_correct, na.rm = TRUE)
    
    p_acc_auto2 <- ggplot(dat_auto2, aes(x = trial_idx, y = acc_running)) +
      geom_point(
        aes(y = as.numeric(aid_correct)),
        shape = 1,
        size = 1.4,
        stroke = 0.8,
        alpha = 0.6,
        colour = "forestgreen"
      ) +
      geom_line(linewidth = 0.5, colour = "orange") +
      geom_hline(
        yintercept = TARGET_ACC,
        linetype = "solid",
        linewidth = 0.5,
        colour = "purple"
      ) +
      geom_hline(
        yintercept = acc_global_auto2,
        linetype = "dashed",
        linewidth = 0.5,
        colour = "orange"
      ) +
      geom_point(
        aes(y = correct_num),
        shape = 4,
        size = 1,
        stroke = 0.8,
        alpha = 0.6,
        colour = "black"
      ) +
      annotate(
        "text",
        x = Inf,
        y = -Inf,
        hjust = 1.05,
        vjust = -5.0,
        size = 3.5,
        colour = "black",
        label = sprintf("Aid acc = %.2f", aid_acc_auto2)
      ) +
      annotate(
        "text",
        x = Inf,
        y = -Inf,
        hjust = 1.05,
        vjust = -3.0,
        size = 3.5,
        colour = "black",
        label = sprintf("Observed acc = %.2f", acc_global_auto2)
      ) +
      labs(x = "Trial", y = "Running accuracy") +
      ylim(0, 1) +
      theme_classic() +
      ggtitle("", subtitle = "Observed accuracy")
    
    p_auto2 <- p_stair_auto2 / p_acc_auto2 +
      plot_layout(heights = c(1, 1))
    
    p_combo_auto <- p_auto1 | p_auto2
    
    ggsave(
      filename = paste0("plots/combined_auto_p", pid, ".pdf"),
      plot     = p_combo_auto,
      device   = cairo_pdf,
      width    = 16,
      height   = 9,
      units    = "in"
    )
  }
}

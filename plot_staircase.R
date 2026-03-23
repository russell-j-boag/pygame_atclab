# Clear workspace
rm(list = ls())

# Load libraries
library("dplyr")
library("readr")
library("stringr")
library("tidyverse")
library("zoo")
library("patchwork")

# Load latest complete results file
files <- list.files(
  "output",
  pattern = "^results_.*_b00_ALL\\.csv$",
  full.names = TRUE
)

latest_file <- files[which.max(file.info(files)$mtime)]
print(latest_file)

dat <- read_csv(latest_file)
head(dat)
str(dat)

dat$stimulus <- factor(
  dat$stimulus,
  levels = c("conflict", "nonconflict"),
  labels = c("Conflict", "Non-conflict")
)

# Calibration settings
WINDOW <- 25                  # sliding accuracy window size
TARGET_ACC <- 0.80            # target accuracy in calibration block
BURN_IN_TRIALS <- 50          # burn-in period in calibration block
CALIB_SUMMARY_LAST_N <- 150   # last N trials used in calibration block

# Calibration block -------------------------------------------------------

dat_calib <- dat %>%
  filter(block == "CALIBRATION") %>%
  arrange(trial_idx) %>%
  mutate(
    correct_num = as.numeric(correct),
    acc_running = cummean(correct),
    acc_slide   = rollapply(
      correct_num,
      width   = WINDOW,
      FUN     = mean,
      align   = "right",
      fill    = NA,
      partial = TRUE
    )
  )

# Keep only the last N calibration trials for summary calculations
dat_calib_last_n <- dat_calib %>%
  slice_tail(n = CALIB_SUMMARY_LAST_N)

dat_calib_last_n$doms_mu_low
dat_calib_last_n$doms_sd

# Summary values based only on the last N trials
acc_global_last_n <- mean(dat_calib_last_n$correct_num, na.rm = TRUE)
mean_doms_last_n  <- mean(abs(dat_calib_last_n$DOMS - 5), na.rm = TRUE)
sd_doms_last_n <- sd(abs(dat_calib_last_n$DOMS - 5), na.rm = TRUE)

# Staircase plot
p_stair <- ggplot(dat_calib, aes(x = trial_idx)) +
  # Burn-in period shaded region
  geom_ribbon(
    data = subset(dat_calib, trial_idx <= BURN_IN_TRIALS),
    aes(x = trial_idx, ymin = 0, ymax = 10),
    inherit.aes = FALSE,
    fill = "red",
    alpha = 0.15
  ) +
  # Minimun separation threshold line
  geom_hline(
    yintercept = 5,
    linetype = "dashed",
    size = 0.5,
    colour = "red"
  ) +
  # Lower mean ribbon
  geom_ribbon(
    aes(ymin = doms_mu_low - doms_sd, ymax = doms_mu_low + doms_sd),
    fill = "orange",
    alpha = 0.25
  ) +
  # Upper mean ribbon
  geom_ribbon(
    aes(ymin = doms_mu_high - doms_sd, ymax = doms_mu_high + doms_sd),
    fill = "purple",
    alpha = 0.25
  ) +
  
  # DOMS samples
  geom_point(aes(y = DOMS, colour = stimulus),
             size = 1,
             alpha = 0.85) +
  
  # Low mean line
  geom_line(
    aes(y = doms_mu_low),
    linewidth = 0.6,
    linetype = "solid",
    colour = "orange"
  ) +
  
  # High mean line
  geom_line(
    aes(y = doms_mu_high),
    linewidth = 0.6,
    linetype = "solid",
    colour = "purple"
  ) +
  
  scale_colour_manual(values = c(
    "Conflict"    = "orange",
    "Non-conflict" = "purple"
  )) +
  
  labs(x = "Trial", y = "Dist min separation (NM)", colour = "Stimulus") +
  ylim(0, 10) +
  theme_classic() +
  theme(legend.position = "none") +
  annotate(
    "text",
    x = max(dat_calib$trial_idx) * 0.5,
    # adjust horizontal position
    y = 9.8,
    # slightly above centre
    label = "Non-conflict",
    colour = "purple",
    size = 4
  ) +
  annotate(
    "text",
    x = max(dat_calib$trial_idx) * 0.5,
    y = 0.2,
    # slightly below centre
    label = "Conflict",
    colour = "orange",
    size = 4
  ) +
  ggtitle("Calibration block", 
          subtitle = paste0("Staircase-adjusted difficulty\n",
                            "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"))

p_stair

# Accuracy plot
dat_calib_plot <- dat_calib %>%
  arrange(trial_idx) %>%
  mutate(correct_num = as.numeric(correct),
         acc_cum = cummean(correct_num))

p_acc <- ggplot(dat_calib_plot, aes(x = trial_idx, y = acc_cum)) +
  # Burn-in period shaded region
  geom_ribbon(
    data = subset(dat_calib, trial_idx <= BURN_IN_TRIALS),
    aes(x = trial_idx, ymin = 0, ymax = 1),
    inherit.aes = FALSE,
    fill = "red",
    alpha = 0.15
  ) +
  
  # Cumulative accuracy
  geom_line(size = 0.5, colour = "orange") +
  
  # Target line
  geom_hline(
    yintercept = TARGET_ACC,
    linetype = "solid",
    size = 0.5,
    colour = "purple"
  ) +
  # Global mean
  geom_hline(
    yintercept = acc_global_last_n,
    linetype = "dashed",
    size = 0.5,
    colour = "orange"
  ) +
  # Trial-level correctness as X's
  geom_point(
    aes(y = correct_num),
    shape = 4,
    size = 1,
    stroke = 0.8,
    alpha = 0.6,
    colour = "black"
  ) +
  # annotation: target accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -5.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Target acc = %.2f", TARGET_ACC)
  ) +
  # annotation: observed global accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -3.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Observed acc = %.2f", acc_global_last_n)
  ) +
  labs(x = "Trial", y = "Running accuracy") +
  ylim(0, 1) +
  theme_classic() +
  ggtitle("", subtitle = "Observed accuracy")

p_acc

p_calib <- p_stair / p_acc +
  plot_layout(heights = c(1, 1))

p_calib

# ggsave(
#   filename = "plots/calibration.pdf",
#   plot     = p_calib,
#   device   = cairo_pdf,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )
# 
# ggsave(
#   filename = "plots/calibration.png",
#   plot     = p_calib,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )


# Manual block ------------------------------------------------------------

dat_manual <- dat %>%
  filter(block == "MANUAL") %>%
  arrange(trial_idx) %>%
  mutate(
    correct_num = as.numeric(correct),
    acc_running = cummean(correct),
    acc_slide   = rollapply(
      correct_num,
      width   = WINDOW,
      FUN     = mean,
      align   = "right",
      fill    = NA,
      partial = TRUE
    )
  )

BURN_IN_TRIALS <- 0

# DOMS summary values
doms_mean_conflict <- dat_manual$doms_mu_low[1]
doms_sd_conflict   <- dat_manual$doms_sd_low[1]
doms_mean_nonconf <- dat_manual$doms_mu_high[1]
doms_sd_nonconf   <- dat_manual$doms_sd_high[1]

# Checks (should be TRUE)
abs(doms_mean_conflict - 5) == abs(doms_mean_nonconf - 5)
doms_sd_conflict == doms_sd_nonconf

# Staircase plot
p_stair_manual <- ggplot(dat_manual, aes(x = trial_idx)) +
  geom_hline(
    yintercept = 5,
    linetype = "dashed",
    size = 0.5,
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
  geom_point(aes(y = DOMS, colour = stimulus),
             size = 1,
             alpha = 0.85) +
  geom_line(
    aes(y = doms_mu_low),
    linewidth = 0.6,
    linetype = "solid",
    colour = "orange"
  ) +
  geom_line(
    aes(y = doms_mu_high),
    linewidth = 0.6,
    linetype = "solid",
    colour = "purple"
  ) +
  scale_colour_manual(values = c(
    "Conflict"     = "orange",
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
  ggtitle("Manual block", 
          subtitle = paste0("Difficulty sampled from calibration mean and sd\n",
                            "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"))

p_stair_manual


# Accuracy plot
dat_manual_plot <- dat_manual %>%
  arrange(trial_idx) %>%
  mutate(correct_num = as.numeric(correct),
         acc_cum = cummean(correct_num))

acc_global_manual <- mean(dat_manual_plot$correct_num, na.rm = TRUE)

p_acc_manual <- ggplot(dat_manual_plot, aes(x = trial_idx, y = acc_cum)) +
  geom_line(size = 0.5, colour = "orange") +
  geom_hline(
    yintercept = TARGET_ACC,
    linetype = "solid",
    size = 0.5,
    colour = "purple"
  ) +
  geom_hline(
    yintercept = acc_global_manual,
    linetype = "dashed",
    size = 0.5,
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
  # annotation: target accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -5.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Target acc = %.2f", TARGET_ACC)
  ) +
  # annotation: observed global accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -3.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Observed acc = %.2f", acc_global_manual)
  ) +
  labs(x = "Trial", y = "Running accuracy") +
  ylim(0, 1) +
  theme_classic() +
  ggtitle("", subtitle = "Observed accuracy")

p_acc_manual


p_manual <- p_stair_manual / p_acc_manual +
  plot_layout(heights = c(1, 1))

p_manual

# ggsave(
#   filename = "plots/manual.pdf",
#   plot     = p_manual,
#   device   = cairo_pdf,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )
# 
# ggsave(
#   filename = "plots/manual.png",
#   plot     = p_manual,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )

# Combine plots
p_combo <- p_calib | p_manual

p_combo

ggsave(
  filename = "plots/combined_manual.pdf",
  plot     = p_combo,
  device   = cairo_pdf,
  width    = 16,
  height   = 9,
  units    = "in"
)

# ggsave(
#   filename = "plots/combined_manual.png",
#   plot     = p_combo,
#   width    = 16,
#   height   = 9,
#   units    = "in"
# )


# Automation block (high reliability) -------------------------------------

dat_auto1 <- dat %>%
  filter(block == "AUTOMATION1") %>%
  arrange(trial_idx) %>%
  mutate(
    correct_num = as.numeric(correct),
    acc_running = cummean(correct),
    acc_slide   = rollapply(
      correct_num,
      width   = WINDOW,
      FUN     = mean,
      align   = "right",
      fill    = NA,
      partial = TRUE
    )
  )

BURN_IN_TRIALS <- 0

# DOMS summary values
doms_mean_conflict <- dat_auto1$doms_mu_low[1]
doms_sd_conflict   <- dat_auto1$doms_sd_low[1]
doms_mean_nonconf <- dat_auto1$doms_mu_high[1]
doms_sd_nonconf   <- dat_auto1$doms_sd_high[1]

# Staricase plot
p_stair_auto1 <- ggplot(dat_auto1, aes(x = trial_idx)) +
  geom_hline(
    yintercept = 5,
    linetype = "dashed",
    size = 0.5,
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
  geom_point(aes(y = DOMS, colour = stimulus),
             size = 1,
             alpha = 0.85) +
  geom_line(
    aes(y = doms_mu_low),
    linewidth = 0.6,
    linetype = "solid",
    colour = "orange"
  ) +
  geom_line(
    aes(y = doms_mu_high),
    linewidth = 0.6,
    linetype = "solid",
    colour = "purple"
  ) +
  scale_colour_manual(values = c(
    "Conflict"     = "orange",
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
  ggtitle("Automation block (high reliability)", 
          subtitle = paste0("Difficulty sampled from calibration mean and sd\n",
                            "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"))

p_stair_auto1

# Accuracy plot
dat_auto1_plot <- dat_auto1 %>%
  arrange(trial_idx) %>%
  mutate(correct_num = as.numeric(correct),
         acc_cum = cummean(correct_num))

acc_global_auto1 <- mean(dat_auto1_plot$correct_num, na.rm = TRUE)
aid_acc_auto1 <- 1 - mean(dat_auto1_plot$auto_fail, na.rm = TRUE)

p_acc_auto1 <- ggplot(dat_auto1_plot, aes(x = trial_idx, y = acc_cum)) +
  # trial-level aid correctness (open circles)
  geom_point(
    aes(y = as.numeric(aid_correct)),
    shape  = 1,        # open circle
    size   = 1.4,
    stroke = 0.8,
    alpha  = 0.6,
    colour = "forestgreen"
  ) +
  geom_line(size = 0.5, colour = "orange") +
  geom_hline(
    yintercept = TARGET_ACC,
    linetype = "solid",
    size = 0.5,
    colour = "purple"
  ) +
  geom_hline(
    yintercept = acc_global_auto1,
    linetype = "dashed",
    size = 0.5,
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
  # annotation: observed aid accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -5.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Aid acc = %.2f", aid_acc_auto1)
  ) +
  # annotation: observed global accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -3.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Observed acc = %.2f", acc_global_auto1)
  ) +
  labs(x = "Trial", y = "Running accuracy") +
  ylim(0, 1) +
  theme_classic() +
  ggtitle("", subtitle = "Observed accuracy")

p_acc_auto1

p_auto1 <- p_stair_auto1 / p_acc_auto1 +
  plot_layout(heights = c(1, 1))

p_auto1

# ggsave(
#   filename = "plots/automation1.pdf",
#   plot     = p_auto1,
#   device   = cairo_pdf,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )
# 
# ggsave(
#   filename = "plots/automation1.png",
#   plot     = p_auto1,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )


# Automation block (low reliability) --------------------------------------

dat_auto2 <- dat %>%
  filter(block == "AUTOMATION2") %>%
  arrange(trial_idx) %>%
  mutate(
    correct_num = as.numeric(correct),
    acc_running = cummean(correct),
    acc_slide   = rollapply(
      correct_num,
      width   = WINDOW,
      FUN     = mean,
      align   = "right",
      fill    = NA,
      partial = TRUE
    )
  )

BURN_IN_TRIALS <- 0

# DOMS summary values
doms_mean_conflict <- dat_auto2$doms_mu_low[1]
doms_sd_conflict   <- dat_auto2$doms_sd_low[1]
doms_mean_nonconf <- dat_auto2$doms_mu_high[1]
doms_sd_nonconf   <- dat_auto2$doms_sd_high[1]

# Staricase plot
p_stair_auto2 <- ggplot(dat_auto2, aes(x = trial_idx)) +
  geom_hline(
    yintercept = 5,
    linetype = "dashed",
    size = 0.5,
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
  geom_point(aes(y = DOMS, colour = stimulus),
             size = 1,
             alpha = 0.85) +
  geom_line(
    aes(y = doms_mu_low),
    linewidth = 0.6,
    linetype = "solid",
    colour = "orange"
  ) +
  geom_line(
    aes(y = doms_mu_high),
    linewidth = 0.6,
    linetype = "solid",
    colour = "purple"
  ) +
  scale_colour_manual(values = c(
    "Conflict"     = "orange",
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
  ggtitle("Automation block (low reliability)", 
          subtitle = paste0("Difficulty sampled from calibration mean and sd\n",
                            "Summary uses last ", nrow(dat_calib_last_n), " post-burn-in calibration trials"))

p_stair_auto2


# Accuracy plot
dat_auto2_plot <- dat_auto2 %>%
  arrange(trial_idx) %>%
  mutate(correct_num = as.numeric(correct),
         acc_cum = cummean(correct_num))

acc_global_auto2 <- mean(dat_auto2_plot$correct_num, na.rm = TRUE)
aid_acc_auto2 <- 1 - mean(dat_auto2_plot$auto_fail, na.rm = TRUE)

p_acc_auto2 <- ggplot(dat_auto2_plot, aes(x = trial_idx, y = acc_cum)) +
  # trial-level aid correctness (open circles)
  geom_point(
    aes(y = as.numeric(aid_correct)),
    shape  = 1,        # open circle
    size   = 1.4,
    stroke = 0.8,
    alpha  = 0.6,
    colour = "forestgreen"
  ) +
  geom_line(size = 0.5, colour = "orange") +
  geom_hline(
    yintercept = TARGET_ACC,
    linetype = "solid",
    size = 0.5,
    colour = "purple"
  ) +
  geom_hline(
    yintercept = acc_global_auto2,
    linetype = "dashed",
    size = 0.5,
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
  # annotation: observed aid accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -5.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Aid acc = %.2f", aid_acc_auto2)
  ) +
  # annotation: observed global accuracy
  annotate(
    "text",
    x      = Inf,
    y      = -Inf,
    hjust  = 1.05,
    vjust  = -3.0,
    size   = 3.5,
    colour = "black",
    label  = sprintf("Observed acc = %.2f", acc_global_auto2)
  ) +
  labs(x = "Trial", y = "Running accuracy") +
  ylim(0, 1) +
  theme_classic() +
  ggtitle("", subtitle = "Observed accuracy")

p_acc_auto2

p_auto2 <- p_stair_auto2 / p_acc_auto2 +
  plot_layout(heights = c(1, 1))

p_auto2

# ggsave(
#   filename = "plots/automation2.pdf",
#   plot     = p_auto2,
#   device   = cairo_pdf,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )
# 
# ggsave(
#   filename = "plots/automation2.png",
#   plot     = p_auto2,
#   width    = 9,
#   height   = 6,
#   units    = "in"
# )

# Combine plots
p_combo <- p_auto1 | p_auto2

p_combo

ggsave(
  filename = "plots/combined_auto.pdf",
  plot     = p_combo,
  device   = cairo_pdf,
  width    = 16,
  height   = 9,
  units    = "in"
)

# ggsave(
#   filename = "plots/combined_auto.png",
#   plot     = p_combo,
#   width    = 16,
#   height   = 9,
#   units    = "in"
# )

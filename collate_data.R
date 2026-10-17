# Clear workspace
rm(list = ls())

# Optional positional directories allow tests without touching study outputs.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("Usage: Rscript collate_data.R [input_dir] [output_dir]")
input_dir <- if (length(args) >= 1L) args[[1L]] else "output"
output_dir <- if (length(args) >= 2L) args[[2L]] else "data"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
timing_audit_columns <- c(
  "rt_timing_version", "rt_backend_version", "stimulus_onset_s",
  "response_timestamp_s", "n_ignored_pre_onset_keydowns", "response_readout_delay_s"
)

# Load libraries
library("dplyr")
library("readr")
library("stringr")
library("purrr")


# 1) First collate all choice-RT results files ----------------------------

# Find all complete results files
files <- list.files(
  input_dir,
  pattern = "^results_.*_b00_ALL\\.csv$",
  full.names = TRUE
)

# Make a file table
file_tbl <- tibble(path = files) %>%
  mutate(
    file_name = basename(path),
    participant_id = str_extract(file_name, "(?<=results_)[^_]+"),
    mtime = file.info(path)$mtime
  )

# For each participant, keep only the most recent b00_ALL file
latest_per_participant <- file_tbl %>%
  group_by(participant_id) %>%
  slice_max(order_by = mtime, n = 1, with_ties = FALSE) %>%
  ungroup()

# Show which files were selected
print(latest_per_participant %>% select(participant_id, path, mtime))
nrow(latest_per_participant)

# Read and bind all selected files
dat <- latest_per_participant %>%
  mutate(data = map(path, read_csv, show_col_types = FALSE)) %>%
  pull(data) %>%
  bind_rows()

# Inspect combined data
head(dat)
tail(dat)
str(dat)
length(unique(dat$participant_id))

# Save master CSV
write_csv(dat, file.path(output_dir, "data_atc_all.csv"))

# To make the data more manageable, take a subset of relevant columns 
dat <- latest_per_participant %>%
  mutate(data = map(path, read_csv, show_col_types = FALSE)) %>%
  pull(data) %>%
  bind_rows() %>%
  select(
    participant_id,
    block,
    block_idx,
    trial_idx,
    stimulus,
    DOMS,
    aid_accuracy_setting,
    aid_label,
    aid_correct,
    response,
    rt_s,
    correct,
    feedback,
    any_of(timing_audit_columns)
  )

dat <- data.frame(dat)

# Inspect combined data
head(dat)
tail(dat)
str(dat)
# View(dat)

# Save master CSV
write_csv(dat, file.path(output_dir, "data_atc.csv"))


# 2) Collate post-block questionnaire files -------------------------------

# Find all complete post-block results files
files <- list.files(
  input_dir,
  pattern = "^results_.*_b00_POSTBLOCK_ALL\\.csv$",
  full.names = TRUE
)

# Make a file table
file_tbl <- tibble(path = files) %>%
  mutate(
    file_name = basename(path),
    participant_id = str_extract(file_name, "(?<=results_)[^_]+"),
    mtime = file.info(path)$mtime
  )

# For each participant, keep only the most recent POSTBLOCK_ALL file
latest_per_participant <- file_tbl %>%
  group_by(participant_id) %>%
  slice_max(order_by = mtime, n = 1, with_ties = FALSE) %>%
  ungroup()

# Show which files were selected
print(latest_per_participant %>% select(participant_id, path, mtime))

# Read and bind all selected files
dat <- latest_per_participant %>%
  mutate(data = map(path, read_csv, show_col_types = FALSE)) %>%
  pull(data) %>%
  bind_rows()

# Inspect combined data
head(dat)
tail(dat)
str(dat)
# View(dat)

# Save master CSV
write_csv(dat, file.path(output_dir, "data_atc_postblock_all.csv"))


# 3) Collate post-block accuracy slider files -----------------------------

# Find all complete post-block results files
files <- list.files(
  input_dir,
  pattern = "^results_.*_b00_POSTBLOCK_SLIDERS_ALL\\.csv$",
  full.names = TRUE
)

# Make a file table
file_tbl <- tibble(path = files) %>%
  mutate(
    file_name = basename(path),
    participant_id = str_extract(file_name, "(?<=results_)[^_]+"),
    mtime = file.info(path)$mtime
  )

# For each participant, keep only the most recent POSTBLOCK_SLIDERS_ALL file
latest_per_participant <- file_tbl %>%
  group_by(participant_id) %>%
  slice_max(order_by = mtime, n = 1, with_ties = FALSE) %>%
  ungroup()

# Show which files were selected
print(latest_per_participant %>% select(participant_id, path, mtime))

# Read and bind all selected files
dat <- latest_per_participant %>%
  mutate(data = map(path, read_csv, show_col_types = FALSE)) %>%
  pull(data) %>%
  bind_rows()

# Inspect combined data
head(dat)
tail(dat)
str(dat)
# View(dat)

# Save master CSV
write_csv(dat, file.path(output_dir, "data_atc_sliders_all.csv"))

# Clear workspace
rm(list = ls())

# Source helper functions
source("0-helpers.R")

# Run pre-task instructions
run_instructions()

# Run task
run_atclab()

# # You can also run one block at a time by selecting a specific block:
# run_atclab(block = "CALIBRATION")
# run_atclab(block = "MANUAL")
# run_atclab(block = "AUTOMATION1")
# run_atclab(block = "AUTOMATION2")

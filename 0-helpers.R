# Helper to activate conda env and return Python binary
get_python_bin <- function(conda_env = "r-pygame") {
  if (!requireNamespace("reticulate", quietly = TRUE)) {
    stop("Package 'reticulate' is required but not installed.")
  }
  
  reticulate::use_condaenv(conda_env, required = TRUE)
  py_bin <- reticulate::py_config()$python
  message("Using Python: ", py_bin)
  py_bin
}


# Helper to validate block names
validate_block <- function(block) {
  if (is.null(block)) {
    return(NULL)
  }
  
  stopifnot(is.character(block), length(block) == 1)
  
  b <- toupper(trimws(block))
  
  valid <- c("TRAINING", "CALIBRATION", "MANUAL", "AUTOMATION1", "AUTOMATION2")
  
  if (!(b %in% valid)) {
    stop(
      "`block` must be one of: ", paste(valid, collapse = ", "),
      " (got: ", sQuote(block), ")"
    )
  }
  
  b
}


# Helper function to run pre-task instructions
run_instructions <- function(atclab_script = "python/instructions.py",
                             conda_env = "r-pygame") {
  stopifnot(file.exists(atclab_script))
  
  py_bin <- get_python_bin(conda_env)
  
  args <- c(atclab_script)
  
  message("Running command:\n  ", py_bin, " ", paste(args, collapse = " "))
  
  status <- system2(py_bin, args)
  invisible(status)
}


# Helper function to run task
run_atclab <- function(n_trials         = 20,
                       seed             = NULL,
                       conda_env        = "r-pygame",
                       atclab_script    = "python/atclab.py",
                       drt              = FALSE,
                       pm_prop          = 0,
                       automation_on    = FALSE,
                       automation_acc   = 0.90,
                       automation_delay = NULL,
                       width            = NULL,
                       height           = NULL,
                       block            = NULL,
                       extra_args       = NULL) {
  stopifnot(file.exists(atclab_script))
  stopifnot(is.numeric(n_trials), length(n_trials) == 1, n_trials > 0)
  stopifnot(is.numeric(pm_prop), length(pm_prop) == 1, pm_prop >= 0, pm_prop <= 1)
  stopifnot(is.logical(automation_on), length(automation_on) == 1)
  stopifnot(is.numeric(automation_acc), length(automation_acc) == 1,
            automation_acc >= 0, automation_acc <= 1)
  
  if (!is.null(automation_delay)) {
    stopifnot(is.numeric(automation_delay), length(automation_delay) == 1)
  }
  
  block <- validate_block(block)
  py_bin <- get_python_bin(conda_env)
  
  args <- c(atclab_script, "--n-trials", as.character(n_trials))
  
  if (!is.null(block)) {
    args <- c(args, "--block", block)
  }
  
  if (!is.null(seed)) {
    args <- c(args, "--seed", as.character(seed))
  }
  
  if (isTRUE(drt)) {
    args <- c(args, "--drt")
  }
  
  if (pm_prop > 0) {
    args <- c(args, "--pm-prop", as.character(pm_prop))
  }
  
  args <- c(args, "--automation-on", if (isTRUE(automation_on)) "TRUE" else "FALSE")
  
  if (isTRUE(automation_on)) {
    args <- c(args, "--automation-acc", as.character(automation_acc))
    
    if (!is.null(automation_delay)) {
      args <- c(args, "--automation-delay", as.character(automation_delay))
    }
  }
  
  if (!is.null(width)) {
    args <- c(args, "--width", as.character(width))
  }
  
  if (!is.null(height)) {
    args <- c(args, "--height", as.character(height))
  }
  
  if (!is.null(extra_args)) {
    stopifnot(is.character(extra_args))
    args <- c(args, extra_args)
  }
  
  message("Running command:\n  ", py_bin, " ", paste(args, collapse = " "))
  
  status <- system2(py_bin, args)
  invisible(status)
}

# # You can run one block at a time by selecting a specific block:
# run_atclab(block = "CALIBRATION")
# run_atclab(block = "MANUAL")
# run_atclab(block = "AUTOMATION1")
# run_atclab(block = "AUTOMATION2")

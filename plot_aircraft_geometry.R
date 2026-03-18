rm(list = ls())

# Helper: run plot_aircraft_geometry.py
run_atc_extremes_plot <- function(
    speed_min      = 400,
    speed_max      = 650,
    ttms_min       = 140,
    ttms_max       = 210,
    doms_min       = 0,
    doms_max       = 10,
    angle          = 90,
    width          = 1280,
    height         = 720,
    geom_scale     = 8,
    circle_radius  = 10,
    margin_px      = -10,
    min_start_px   = 100,
    theta1_deg     = 30,
    out            = "aircraft_geometry.pdf",
    seed           = NULL,
    conda_env      = "r-pygame",
    plot_script    = "python/plot_aircraft_geometry.py",
    extra_args     = NULL
) {
  stopifnot(file.exists(plot_script))
  
  # basic validation
  stopifnot(is.numeric(speed_min), is.numeric(speed_max), speed_min > 0, speed_max > 0)
  stopifnot(is.numeric(ttms_min),  is.numeric(ttms_max),  ttms_min >= 0, ttms_max >= 0)
  stopifnot(is.numeric(doms_min),  is.numeric(doms_max))
  stopifnot(is.numeric(width), is.numeric(height), width > 0, height > 0)
  stopifnot(is.numeric(geom_scale), geom_scale > 0)
  # stopifnot(is.numeric(circle_radius), circle_radius > 0)
  
  # reticulate -> conda python
  if (!requireNamespace("reticulate", quietly = TRUE)) {
    stop("Package 'reticulate' is required but not installed.")
  }
  reticulate::use_condaenv(conda_env, required = TRUE)
  py_bin <- reticulate::py_config()$python
  message("Using Python: ", py_bin)
  
  # Build args exactly as the plotting script expects
  args <- c(
    plot_script,
    "--width",       as.character(as.integer(width)),
    "--height",      as.character(as.integer(height)),
    "--geom-scale",  as.character(geom_scale),
    "--circle-radius", as.character(circle_radius),
    "--speed-min",   as.character(speed_min),
    "--speed-max",   as.character(speed_max),
    "--ttms-min",    as.character(ttms_min),
    "--ttms-max",    as.character(ttms_max),
    "--doms-min",    as.character(doms_min),
    "--doms-max",    as.character(doms_max),
    "--angle",       as.character(angle),
    "--margin-px",   as.character(margin_px),
    "--min-start-px", as.character(min_start_px),
    "--theta1-deg",  as.character(theta1_deg),
    "--out",         as.character(out)
  )
  
  # Optional: seed (only if you update the python script to accept it;
  # harmless if not supported ONLY IF your python uses argparse to ignore unknowns - it won't.
  # So: only pass when script supports --seed.
  if (!is.null(seed)) {
    stopifnot(is.numeric(seed), length(seed) == 1)
    # If you add argparse for --seed in python, uncomment:
    # args <- c(args, "--seed", as.character(as.integer(seed)))
    warning("`seed` provided but the current atc_extremes_plot.py does not accept --seed. Ignoring.")
  }
  
  # Any additional raw args
  if (!is.null(extra_args)) {
    stopifnot(is.character(extra_args))
    args <- c(args, extra_args)
  }
  
  message("Running command:\n  ", py_bin, " ", paste(args, collapse = " "))
  
  status <- system2(py_bin, args)
  invisible(status)
}

# Example
run_atc_extremes_plot(
  speed_min = 450, speed_max = 650,
  ttms_min = 180,  ttms_max = 200,
  geom_scale = 8,
  out = "plots/aircraft_geometry.pdf"
)

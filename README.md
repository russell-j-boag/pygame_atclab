# pygame_atclab

ATCLAB conflict detection task built in Pygame for studying decision-making and automation use. 

## Structure
- Python experiment code in `/python`
- Output data saved to `/output`
- Plots saved to `/plots`
- Analysis conducted in R

## Getting started
- Run `0-setup_pygame.R` to install the required versions of python and pygame
- Use `1-run_atclab.R` to launch task and pre-task instructions using the helper functions

## Semester 1 2026 source archive

The existing source ZIP is preserved byte-for-byte in
[source_archives/semester1_2026](source_archives/semester1_2026/README.md).
It was copied from `../pygame_atclab.zip`, which remains unchanged. Its tracked
source files match the embedded Git revision `1de22e4f4d7c` from 23 March 2026.
It retains the historical response timing and differs from the later pre-fix
checkout. The manifest records provenance and ZIP/member checksums.

Future bundles must be built from current repository source and use
`rt_timing_version = ptb_queue_flip_v1`. Include `python/response_timing.py`,
`python/check_response_timing.py`, the updated task and dependency setup, and
the normal launcher, helpers, project file, instructions and font. Include the
current timing setup and validation guidance below. Use a distinct release name
and source manifest; preserve the Semester 1 archive unchanged.

## Response timing

New trials require `psychtoolbox==3.0.22.2` in the `r-pygame` environment.
Keyboard acquisition uses a native asynchronous queue. RT is the original
key-down timestamp minus `GetSecs()` recorded immediately after the first
aircraft display flip. Drawing/readout delays are reported separately and do
not enter RT. The queue starts before preparing that frame. Pre-onset presses
are ignored; held keys require release before another down can respond.
The first valid response is retained, including RTs below 200 ms, with no
rounding of `rt_s` or `rt_ms`. Events at or after `TrialSpec.deadline` are
excluded, while pre-deadline events retrieved later remain eligible.

The 300-trial calibration, three 500-trial main blocks, 80% calibration target,
95%/65% advice reliability, counterbalancing, scoring, and default 10-second
deadline are unchanged. Custom trial deadlines remain supported. Aircraft
start at their initial positions and move according to time since their first
flip. Advanced advice remains a non-response preview; simultaneous and delayed
advice retain their visibility rules. `aid_onset_s` and `aid_onset_ms` describe
the signed configured delay, not a measured presentation timestamp.

D/J retain the participant's conflict/nonconflict mapping. When PM is enabled,
9 and keypad 9 compete for the first main response. When DRT is enabled, Space
is processed separately from that same native event stream. Each flash is
timestamped after its first visible flip; its response interval ends at the
next flash onset (not at visual offset). `flash_onsets` remains relative to
aircraft onset in seconds; `flash_rts` remains a semicolon-separated list with
`NA` for missing responses. New values use round-trip float formatting.
The scheduled blocks still disable DRT by default.

Raw block files, combined participant files, and full/reduced collated files
retain these optional audit columns:

- `rt_timing_version`: `ptb_queue_flip_v1` for new trials.
- `rt_backend_version`: the native package version.
- `stimulus_onset_s`: the post-flip PTB clock reading.
- `response_timestamp_s`: the accepted original key-down timestamp.
- `n_ignored_pre_onset_keydowns`: main response downs after the initial held-state
  snapshot and before onset.
- `response_readout_delay_s`: retrieval time minus key-down time.

Clock readings are monotonic timestamps with a backend-defined origin, not
dates. Timeout RT/response timestamps remain blank. Historical values, including
negative/zero RTs and old timeout conventions, are preserved without assigning
them the new timing version. Existing run selection remains by file modification
time independently within each export family.

Collation accepts optional input/output directories and creates the output
directory; defaults remain `output` and `data`:

```sh
Rscript collate_data.R /path/to/input /path/to/collated
```

## Timing validation

Use the `r-pygame` Python interpreter. On the reference Mac:

```sh
PYTHON_BIN=/Users/rjb779/Library/r-miniconda-arm64/envs/r-pygame/bin/python
"$PYTHON_BIN" -m unittest discover -s tests -v
"$PYTHON_BIN" python/check_response_timing.py --preflight --pm --drt
"$PYTHON_BIN" python/check_response_timing.py --pm --drt
```

Resolve the environment's interpreter locally on other computers. The tests
use synthetic exports in temporary directories, including actual R collation
with `dplyr`, `readr`, `stringr`, and `purrr`. Imports, `--help`, and screenshot
generation do not initialise keyboard capture. Missing/wrong native backends
fail visibly; there is no frame-based timing fallback.

Run the native checks on every collection computer. On macOS, grant Input
Monitoring access to the application launching Python (Terminal or R/RStudio),
restart it, and run outside input-restricting sandboxes. During the interactive
check, release keys between presses, respond to the red border with Space,
then press the requested main key. Omit `--pm`/`--drt` to check only D/J.
The diagnostic records original event timestamps, readout delays, configured
and observed keys, and 0/8/20/50 ms stalls in a separate JSON artifact under
`analysis_outputs/response_timing/` (or a new path supplied with `--output`).
Timeouts or absent keys are missing validation evidence.

The 17 October 2026 port used the reference working files and SHA-256 snapshot
listed in `CODEX_RT_TIMING_PORT_GUIDE.md`, based on target commit `758904db0c1c`.
Validation evidence is recorded in `validation/response_timing_20261017.json`.
Automated tests and queue preflights establish numerical precision and
independence from rendering, not physical screen-to-keypress accuracy within
±1 ms. Interactive physical-key checks and native Windows validation remain
outstanding; Windows mapping tests alone do not establish native operation.

## Author
Russell J. Boag

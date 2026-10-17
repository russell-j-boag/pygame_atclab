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

## Participant and historical-run exclusion audit

The standalone `participant_qc/` pipeline adapts the dynamic-reliability and
time-pressure Virus audits to ATCLAB's Semester 1 design. It produces review
evidence and candidate lists; **it applies no exclusions, trims no trials, and
does not change canonical data or behavioural analyses**.

```sh
/Users/rjb779/Library/r-miniconda-arm64/envs/r-pygame/bin/python participant_qc/run_qc.py
/Users/rjb779/Library/r-miniconda-arm64/envs/r-pygame/bin/python -m unittest discover -s tests -v
/Users/rjb779/Library/r-miniconda-arm64/envs/r-pygame/bin/python tests/validate_participant_qc.py --expect-current-cohort
```

Open `analysis_outputs/semester1_2026_qc/index.html`. CLI options are `--input`
(default `data/data_atc_all.csv`), `--raw-dir` (`output`), `--config`
(`participant_qc/config.json`), and `--output-dir` (the report directory above).
The existing `r-pygame` environment supplies NumPy, Matplotlib and Pillow;
validation additionally uses `pdfinfo`. No dependency installation is required.
Omit `--expect-current-cohort` when validating future data deliveries; normal
processing discovers run counts dynamically.

### Agreed retrospective screens

The following first-pass screens were agreed on 17 October 2026. They are
retrospective descriptive criteria, not preregistered rules or proof of
statistical equivalence to chance.

| Screen | Scope | Role |
| --- | --- | --- |
| Accuracy differs from 80% by **more than 10 percentage points** | Calibration trials 151–300 | Exclusion candidate |
| Same target-deviation screen | Full 500-trial manual block | Diagnostic only |
| All-trial accuracy **≤55%** | Each whole scope below | Exclusion candidate |
| RT **<200 ms** on **≥20% of all trials**, **≥20 fast responses**, and fast-response accuracy **≤55%**, jointly within the same scope | Each whole scope below | Exclusion candidate |

Whole scopes are calibration (300 trials), manual, automation 95%, automation
65% (500 each), pooled automation (1,000), and all experimental trials (1,500).
Calibration-tail checks are target-only; 50-trial bins are plotting diagnostics
and never trigger exclusions. Calibration accuracy exactly 70% or 90% passes.
Thresholds, bin size, interval level and sensitivity thresholds are configurable.
The Semester 1 study contract remains explicit: 80% target, 300/500-trial blocks,
six orders, a 12-ID key-mapping cycle, 95%/65% advice and 10-second deadlines.
Future design changes require an explicit adaptation; changing the task source
must not silently reinterpret historical data.

Accuracy counts timeouts as incorrect, even when legacy timeout rows retain an
RT. Fast proportions use all trials; fast accuracy uses answered fast trials.
Exactly 200 ms is not fast. Finite zero and negative answered RTs remain visible
and count as fast. Empty fast-response subsets have missing accuracy. Mean
answered RT, positive median RT, answered accuracy and timeout counts provide
context; slow RT alone is not an exclusion criterion. Wilson intervals are
purely descriptive and do not account for serial dependence or adaptive calibration.

Missing or invalid scopes are **not assessable**, never silently clear. Missing
required columns, duplicate trial identities, multiple selected runs per ID,
ambiguous raw exports and raw/collated discrepancies stop generation. Timing
metadata is optional for historical exports. New `ptb_queue_flip_v1` timestamps,
readout delays and deadline consistency are checked in `timing_diagnostics.csv`;
these findings are diagnostic only, not an additional exclusion rule. The audit
preserves legacy RTs without retrospective correction or timing-version assignment.

### Selected cohort and historical sessions

The selected cohort is taken from the existing collated CSV and reconciled to
raw combined exports by participant ID and run timestamp, with numeric-aware
comparison of all source columns. **The audit does not reselect runs.** Existing
collation uses file modification times, not run timestamps; both are recorded
separately in `run_inventory.csv` with file checksums.

The current snapshot contains 48 selected runs (86,400 trials) plus five earlier
complete sessions (9,000 trials), sharing recorded IDs 005, 017, 033, 038 and 045.
The user recalls that later sessions may be different replacement participants,
but no replacement log was found in the repository. Identity and historical
replacement reasons therefore remain **unconfirmed**. Observed performance is
reported separately from that recollection. No new participant IDs are assigned.

All 53 sessions receive individual PDF/PNG diagnostics. The five earlier runs
also receive paired comparisons with the selected runs, scope-level comparison
tables and a separate historical screening summary. Historical runs do not
contribute to selected-cohort counts, candidate totals or reference pools. Future
unselected later or unmatched raw exports are also inventoried and audited
separately rather than selected automatically.

The first audit found **no exclusion candidates in the selected 48-run cohort**;
003, 005, 012, 016 and 042 had manual-only diagnostic flags. Earlier runs 005 and
017 failed the calibration-target screen (62.7% and 51.3% final-150 accuracy).
Earlier 017, 033 and 045 had manual diagnostic flags. Earlier 038 met none of the
agreed criteria despite slow responding. These findings do not establish why
any original session was replaced. All current scopes were assessable.

### Figures, outputs and validation

Plots retain sibling typography, colours, phase shading, RT scatter with a linear
scale below 200 ms and logarithmic scale above, deadline markers, 50-trial fast-rate
and accuracy panels, fast-only accuracy, and peer median/IQR bands. Traces follow
each run's counterbalanced order. Peer bands align by condition and within-block
trial across complete selected runs without anticipatory flags, excluding the
focal recorded ID. This also excludes the corresponding selected run when viewing
an earlier session with uncertain identity. Bands are descriptive references,
not adjustments for order effects.

Anticipatory comparators match both block order and key mapping. Among complete
selected runs with no anticipatory flag, choose the minimum summed absolute
MAD-standardised distance from subgroup medians of experimental accuracy and
positive median RT. Zero-MAD terms contribute zero; participant ID breaks ties.
Other review flags do not disqualify comparators. Missing comparators are explicit;
there is no unmatched fallback. Pools, rankings and reference-band values are exported.

The HTML index links cohort figures, all individual pages, historical comparisons,
metrics, screening results, candidate unions, overlaps and integrity findings.
`n_flagged_rules` covers all four screens; `n_exclusion_rules` covers only the
three candidate criteria. Repeated scopes count once per criterion and once in
the overall candidate total. Incomplete checks remain separate. Empty candidate
lists are valid outputs.

Generation hashes its input, raw exports, configuration, audit source, task source,
collation source and report artifacts. It builds in a staging directory, preserves
previous reports as `.previous_<timestamp>` siblings and publishes only completed
generation. Failed builds remain unpublished. Reports and validation receipts
under `analysis_outputs/` are generated local artifacts and ignored by Git.

The independent validator imports no production QC modules. It recomputes metrics,
intervals, flags, bins, candidate unions, peer references, comparator rankings and
paired-session tables from source data, and checks report links, hashes and PDF/PNG
structure. Tests also cover threshold boundaries, invalid/missing data, repeated
IDs, output protection and the current task design. Rendered visual review is
required after plotting changes. Current validation receipts and visual-review
records are kept in `analysis_outputs/semester1_2026_qc_validation/`.

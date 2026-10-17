# Semester 1 2026 source archive

This directory preserves the existing ATCLAB source ZIP designated by the user
as the Semester 1 2026 archive. The canonical artifact is
[pygame_atclab_task_source_semester1_2026.zip](pygame_atclab_task_source_semester1_2026.zip).
It retains the historical response timing: the clock starts before the first
aircraft frame and responses receive the drawing loop's elapsed time.

On 17 October 2026 the archive was copied from
`/Users/rjb779/Documents/pygame_atclab.zip` without recompression or changes to
its bytes. The original remains in place. The ZIP is 1,309,258 bytes and has
SHA-256:

```text
54e4cbef96d1f426993058a6f2f30ed09ea65bf29b18ab7c204f8b2bf2478c65
```

[manifest.json](manifest.json) records the ZIP checksum, every member-file
checksum and stored timestamp, and comparisons with Git. All 15 tracked source
members match the embedded Git revision
`1de22e4f4d7c04810eb14639b371433b2a2df705`, dated 23 March 2026. The task and
instructions differ from the later pre-fix checkout at `758904db0c1c`; this
archive preserves the existing ZIP rather than substituting the later source.
These comparisons establish the source contents, without independently
verifying which version was installed on every collection computer.

The original Git metadata, RStudio state, R history, Python cache files and
macOS metadata remain inside the ZIP unchanged. The archived `output/` and
`plots/` directories contain metadata/placeholders, with no participant CSV
exports. Do not clean or rebuild the historical ZIP.

The ZIP passed its CRC integrity check. All three archived Python modules
compiled, the archived task's `--help` succeeded in `r-pygame`, and all six
archived R scripts parsed. Checks used temporary extraction of tracked source
files only; no historical task run or participant-data generation was performed.

No separate extracted copy is required. Optional local extraction under
`extracted/` is ignored by Git because the ZIP is the canonical record. Keep
any extracted historical copy unchanged.

## Future bundles

Build future bundles from the current repository source. The updated RT timing
implementation is present in the working tree and remains uncommitted at
archive creation. It uses `rt_timing_version = ptb_queue_flip_v1`: native
keypress timestamps with onset recorded immediately after the first aircraft
flip, including the ATCLAB-specific PM and DRT handling.

Include `python/response_timing.py`, `python/check_response_timing.py`, the
updated `python/atclab.py` and `0-setup_pygame.R`, plus `0-helpers.R`,
`1-run_atclab.R`, `pygame_atclab.Rproj`, `python/instructions.py`,
`python/fonts/Roboto-Light.ttf`, and any other required assets. Include the
[current timing setup and validation instructions](../../README.md#response-timing).
Any distributed setup handout must describe the Psychtoolbox dependency and
native checks. If distributing collation, use the current `collate_data.R`
that retains optional timing audit columns.

Use a distinct release name and source manifest. Record the source revision,
working-tree changes, timing convention, and ZIP/member checksums. Validate
bundled dependencies and imports, and complete native checks on each collection
platform as described in the current README.

Do not rebuild this Semester 1 archive, modify an extracted historical copy,
or use it as the basis for a future bundle. No new distribution bundle is
created by this archival step. Historical participant data and RTs are unchanged.

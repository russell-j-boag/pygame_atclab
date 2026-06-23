"""
Render clean ATCLAB conflict/non-conflict stimulus examples for papers.

Example:

    python python/capture_atclab_stimulus_screenshots.py --overwrite
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import re
import shutil
import sys
import warnings
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

import pygame

import atclab as task


DEFAULT_OUTPUT_DIR = Path("atclab_stimulus_screenshots")
DEFAULT_RESOLUTION = "1512x982"
DEFAULT_SEED = 20260623
DEFAULT_PARTICIPANT = 1
DEFAULT_ELAPSED = 0.5
CLEAR_CONFLICT_DOMS_MAX = 2.0
CLEAR_NONCONFLICT_DOMS_MIN = 8.0
EXAMPLE_SPEED_RANGE = (500, 540)

MANIFEST_FIELDS = [
    "filename",
    "stimulus",
    "is_conflict",
    "aid_state",
    "aid_label",
    "participant",
    "key_conflict",
    "key_nonconf",
    "seed",
    "example_seed",
    "resolution",
    "elapsed_s",
    "DOMS",
    "TTMS",
    "angle_deg",
    "OOP",
    "TCOP1",
    "TCOP2",
    "ac1_speed",
    "ac2_speed",
    "callsign1",
    "callsign2",
    "automation_correct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render four clean ATCLAB stimulus screenshots: conflict/manual, "
            "nonconflict/manual, conflict/aided, and nonconflict/aided."
        )
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for PNG files and manifest.csv. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        help=f"Capture size as WIDTHxHEIGHT. Default: {DEFAULT_RESOLUTION}",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Base random seed for deterministic examples. Default: {DEFAULT_SEED}",
    )
    parser.add_argument(
        "--participant",
        type=int,
        default=DEFAULT_PARTICIPANT,
        help=(
            "Representative participant for key counterbalancing metadata. "
            f"Default: {DEFAULT_PARTICIPANT}"
        ),
    )
    parser.add_argument(
        "--elapsed",
        type=float,
        default=DEFAULT_ELAPSED,
        help=(
            "Stimulus time in seconds to render after trial onset. "
            f"Default: {DEFAULT_ELAPSED}"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output directory before writing files.",
    )
    return parser.parse_args()


def parse_resolution(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+)\s*", value.lower())
    if match is None:
        raise ValueError(f"invalid --resolution {value!r}; use WIDTHxHEIGHT")

    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError("resolution dimensions must be positive")
    return width, height


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not output_dir.is_dir():
            raise RuntimeError(f"output path exists and is not a directory: {output_dir}")
        if overwrite:
            shutil.rmtree(output_dir)
        elif any(output_dir.iterdir()):
            raise RuntimeError(
                f"{output_dir} is not empty; pass --overwrite to replace its contents"
            )

    output_dir.mkdir(parents=True, exist_ok=True)


def apply_key_mapping(participant: int) -> dict:
    mapping = task.counterbalanced_key_mapping(participant)
    task.KEY_CONFLICT = mapping["conflict_key"]
    task.KEY_NONCONFLICT = mapping["nonconflict_key"]
    return mapping


def load_fonts() -> dict:
    font_path = Path(task.__file__).resolve().parent / "fonts" / "Roboto-Light.ttf"
    if not font_path.exists():
        raise RuntimeError(f"font file not found: {font_path}")

    font = pygame.font.Font(str(font_path), max(14, task.ui(24)))
    info_font = pygame.font.Font(str(font_path), max(10, task.ui(16)))
    aid_label_font = pygame.font.Font(str(font_path), max(12, task.ui(20)))
    aid_font = pygame.font.Font(str(font_path), max(18, task.ui(32)))
    aid_font.set_bold(True)

    return {
        "font": font,
        "info_font": info_font,
        "aid_label_font": aid_label_font,
        "aid_font": aid_font,
    }


def make_example_trial(*, conflict: bool, seed: int) -> task.TrialSpec:
    previous_automation_on = task.AUTOMATION_ON
    task.AUTOMATION_ON = False
    random.seed(seed)

    conflict_high = min(
        task.DOMS_THRESHOLD_NM - task.DOMS_EPS_NM,
        CLEAR_CONFLICT_DOMS_MAX - 0.01,
    )
    nonconflict_low = max(
        task.DOMS_THRESHOLD_NM + task.DOMS_EPS_NM,
        CLEAR_NONCONFLICT_DOMS_MIN + 0.01,
    )

    try:
        for _ in range(1000):
            trial = task.build_atc_trial(
                x_dim=task.SCREEN_WIDTH,
                aspect_ratio=task.SCREEN_HEIGHT / task.SCREEN_WIDTH,
                angle_deg=90.0,
                speed_range=EXAMPLE_SPEED_RANGE,
                mu_low_start=1.5,
                mu_high_start=8.75,
                doms_sd=0.25,
                doms_sd_low=0.25,
                doms_sd_high=0.25,
                doms_low_bounds=(0.0, conflict_high),
                doms_high_bounds=(nonconflict_low, 10.0),
                ttms_range=(170, 190),
                flight_level=370,
                default_deadline=task.DEADLINE_SEC,
                callsigns=None,
                enforce_unique_callsigns=False,
                used_callsigns=None,
                pm_prop=0.0,
                staircase=None,
            )
            if conflict:
                doms_ok = float(trial.doms_nm) < CLEAR_CONFLICT_DOMS_MAX
            else:
                doms_ok = float(trial.doms_nm) > CLEAR_NONCONFLICT_DOMS_MIN

            if bool(trial.is_conflict) == bool(conflict) and doms_ok:
                return replace(
                    trial,
                    automation=None,
                    auto_delay=0.0,
                    auto_fail=None,
                    auto_fail_prop=None,
                )
    finally:
        task.AUTOMATION_ON = previous_automation_on

    label = "conflict" if conflict else "non-conflict"
    raise RuntimeError(f"could not generate a clear {label} example trial")


def screenshot_specs(conflict_trial: task.TrialSpec, nonconflict_trial: task.TrialSpec) -> list[dict]:
    return [
        {
            "filename": "conflict_manual.png",
            "stimulus": "CONFLICT",
            "aid_state": "manual",
            "aid_label": task.MASKED_AID_BANNER_TEXT,
            "trial": replace(conflict_trial, automation=None, auto_delay=0.0),
            "show_automation": False,
            "show_masked_banner": True,
        },
        {
            "filename": "nonconflict_manual.png",
            "stimulus": "NONCONFLICT",
            "aid_state": "manual",
            "aid_label": task.MASKED_AID_BANNER_TEXT,
            "trial": replace(nonconflict_trial, automation=None, auto_delay=0.0),
            "show_automation": False,
            "show_masked_banner": True,
        },
        {
            "filename": "conflict_aided.png",
            "stimulus": "CONFLICT",
            "aid_state": "aided",
            "aid_label": "CONFLICT",
            "trial": replace(
                conflict_trial,
                automation="CONFLICT",
                auto_delay=0.0,
                auto_fail=False,
                auto_fail_prop=None,
            ),
            "show_automation": True,
            "show_masked_banner": False,
        },
        {
            "filename": "nonconflict_aided.png",
            "stimulus": "NONCONFLICT",
            "aid_state": "aided",
            "aid_label": "NON-CONF",
            "trial": replace(
                nonconflict_trial,
                automation="NON-CONF",
                auto_delay=0.0,
                auto_fail=False,
                auto_fail_prop=None,
            ),
            "show_automation": True,
            "show_masked_banner": False,
        },
    ]


def metadata_row(
    *,
    spec: dict,
    participant: int,
    key_mapping: dict,
    seed: int,
    example_seed: int,
    resolution: str,
    elapsed: float,
) -> dict:
    trial = spec["trial"]
    return {
        "filename": spec["filename"],
        "stimulus": spec["stimulus"],
        "is_conflict": int(bool(trial.is_conflict)),
        "aid_state": spec["aid_state"],
        "aid_label": spec["aid_label"],
        "participant": int(participant),
        "key_conflict": key_mapping["conflict_label"],
        "key_nonconf": key_mapping["nonconflict_label"],
        "seed": int(seed),
        "example_seed": int(example_seed),
        "resolution": resolution,
        "elapsed_s": round(float(elapsed), 3),
        "DOMS": round(float(trial.doms_nm), 3),
        "TTMS": round(float(trial.ttms), 3),
        "angle_deg": round(float(trial.angle), 3),
        "OOP": "" if trial.OOP is None else int(trial.OOP),
        "TCOP1": "" if trial.TCOP1 is None else round(float(trial.TCOP1), 3),
        "TCOP2": "" if trial.TCOP2 is None else round(float(trial.TCOP2), 3),
        "ac1_speed": round(float(trial.ac1_speed), 3),
        "ac2_speed": round(float(trial.ac2_speed), 3),
        "callsign1": trial.callsign1,
        "callsign2": trial.callsign2,
        "automation_correct": "" if spec["aid_state"] == "manual" else 1,
    }


def write_manifest(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def render_screens(
    *,
    output_dir: Path,
    width: int,
    height: int,
    seed: int,
    participant: int,
    elapsed: float,
) -> list[Path]:
    task.configure_display_and_scaling(
        fullscreen=False,
        requested_w=width,
        requested_h=height,
    )
    key_mapping = apply_key_mapping(participant)
    fonts = load_fonts()
    surface = pygame.Surface((width, height))

    conflict_seed = seed + 1
    nonconflict_seed = seed + 2
    conflict_trial = make_example_trial(conflict=True, seed=conflict_seed)
    nonconflict_trial = make_example_trial(conflict=False, seed=nonconflict_seed)

    paths = []
    rows = []
    for idx, spec in enumerate(screenshot_specs(conflict_trial, nonconflict_trial)):
        trial = spec["trial"]
        task.draw_trial_frame_state(
            surface,
            fonts["font"],
            fonts["info_font"],
            trial,
            trial_idx=idx,
            total_trials=4,
            elapsed=elapsed,
            aid_label_font=fonts["aid_label_font"],
            aid_font=fonts["aid_font"],
            show_automation=bool(spec["show_automation"]),
            show_masked_banner=bool(spec["show_masked_banner"]),
        )

        path = output_dir / spec["filename"]
        pygame.image.save(surface, str(path))
        paths.append(path)

        example_seed = conflict_seed if bool(trial.is_conflict) else nonconflict_seed
        rows.append(
            metadata_row(
                spec=spec,
                participant=participant,
                key_mapping=key_mapping,
                seed=seed,
                example_seed=example_seed,
                resolution=f"{width}x{height}",
                elapsed=elapsed,
            )
        )

    manifest_path = output_dir / "manifest.csv"
    write_manifest(manifest_path, rows)
    paths.append(manifest_path)
    return paths


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)

    if args.participant < 1:
        print("capture_atclab_stimulus_screenshots: error: --participant must be >= 1", file=sys.stderr)
        return 1

    try:
        width, height = parse_resolution(args.resolution)
        if args.elapsed < 0:
            raise ValueError("--elapsed must be >= 0")
        prepare_output_dir(output_dir, args.overwrite)

        pygame.font.init()
        written = render_screens(
            output_dir=output_dir,
            width=width,
            height=height,
            seed=int(args.seed),
            participant=int(args.participant),
            elapsed=float(args.elapsed),
        )
    except (RuntimeError, ValueError, OSError, pygame.error) as exc:
        print(f"capture_atclab_stimulus_screenshots: error: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()

    print(f"Wrote {len(written) - 1} ATCLAB stimulus screenshots to {output_dir}")
    print(f"Manifest: {output_dir / 'manifest.csv'}")
    print(f"Participant: {args.participant}")
    print(f"Resolution: {width}x{height}")
    print(f"Seed: {args.seed}")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

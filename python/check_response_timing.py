"""Native input preflight and interactive timestamp/readout diagnostic.

Run separately on every collection computer. This measures queue readout delay,
not physical keyboard or display accuracy. Optional PM/DRT keys are supported.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time

from response_timing import FlashResponses, PsychtoolboxKeyboard, TimingError, TIMING_VERSION


KEYMAP = {"D": "conflict", "J": "nonconflict"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", help="Check native queue APIs without opening a window.")
    parser.add_argument("--output", type=Path, help="New JSON diagnostic path; existing files are never overwritten.")
    parser.add_argument("--pm", action="store_true", help="Include both 9 and keypad 9 as prospective-memory responses.")
    parser.add_argument("--drt", action="store_true", help="Include Space as a separate flash response.")
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    report = dict(platform=platform.platform(), architecture=platform.machine(),
                  python=sys.version, timing_version=TIMING_VERSION,
                  timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  validation="native_preflight" if args.preflight else "native_interactive",
                  physical_accuracy_validated=False)
    keymap = dict(KEYMAP)
    if args.pm:
        keymap.update({"9": "pm", "KP9": "pm"})
    keys = set(keymap) | ({"SPACE"} if args.drt else set())
    report.update(configured_keys=sorted(keys), pm_enabled=args.pm, drt_enabled=args.drt)
    with PsychtoolboxKeyboard(keys=keys) as timing:
        report.update(backend_version=timing.backend_version, native_queue_preflight="passed")
        if not args.preflight:
            report["trials"] = interactive_check(timing, keymap, args.drt)
            report["answered_trials"] = sum(r["response"] != "TIMEOUT" for r in report["trials"])
            report["all_stall_conditions_answered"] = all(r["response"] != "TIMEOUT" for r in report["trials"])
            observed = {e["key"] for r in report["trials"] for e in r["events"] if e["pressed"]}
            report["observed_keys"] = sorted(observed)
            report["all_configured_keys_observed"] = keys <= observed
            if args.drt:
                report["drt_flashes_answered"] = sum(r["flash_rts"] != "NA" for r in report["trials"])
    if args.output is None and not args.preflight:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        args.output = Path("analysis_outputs/response_timing") / f"native_{sys.platform}_{stamp}.json"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
        print(f"Saved {args.output}")
    print(json.dumps(report, indent=2, allow_nan=False))


def interactive_check(timing, keymap, drt_enabled):
    import pygame
    pygame.init()
    try:
        screen = pygame.display.set_mode((1000, 400))
        pygame.display.set_caption("ATCLAB native keyboard timing check")
        pygame.key.set_repeat()
        font = pygame.font.Font(None, 30)
        rows = []
        for index, stall_ms in enumerate((0, 8, 20, 50) * 2, 1):
            with timing.trial(keymap) as responses:
                flashes = FlashResponses(responses.start_s, responses.held_keys, timing.backend_version)
                recorded_events = []
                target = list(keymap)[(index - 1) % len(keymap)]
                screen.fill((245, 245, 245))
                for y, msg in enumerate((f"Check {index}/8: press {target} ({keymap[target]}). Release between presses.",
                                         f"Added main-thread stall: {stall_ms} ms",
                                         "Press SPACE for the red border first." if drt_enabled else "D = conflict; J = nonconflict.",
                                         "Esc closes this diagnostic; no participant data are written.")):
                    screen.blit(font.render(msg, True, (25, 25, 25)), (25, 60 + 65*y))
                if drt_enabled:
                    pygame.draw.rect(screen, (220, 30, 30), screen.get_rect(), 12)
                pygame.display.flip()
                responses.mark_onset(timing.now(), 15.0)
                if drt_enabled:
                    flashes.add_flash(responses.onset_s)
                while responses.response is None:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                            raise TimingError("Interactive timing check cancelled; no completed report written.")
                    # Sleeping simulates a busy/unavailable rendering thread;
                    # the native queue continues timestamping independently.
                    time.sleep(max(stall_ms / 1000.0, .001))
                    fence_s = timing.now()
                    events = timing.drain()
                    recorded_events.extend(asdict(e) for e in events)
                    responses.consume(events)
                    responses.expire(fence_s)
                    if drt_enabled:
                        end_s = responses.response_event.timestamp_s if responses.response_event else responses.deadline_s
                        flashes.consume(events, end_s=end_s)
                rows.append(dict(trial=index, requested_key=target, requested_stall_ms=stall_ms,
                                 events=recorded_events, **responses.result(), **flashes.export(responses.onset_s)))
        return rows
    finally:
        pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except TimingError as exc:
        print(f"[TIMING ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

"""Native, asynchronous response timing; no Pygame polling-time fallback.

PTB event Time and GetSecs share a clock. Pygame still owns the display and
interface events. Importing this module does not initialise native input.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from importlib.metadata import version
import math
import sys


PTB_VERSION = "3.0.22.2"
TIMING_VERSION = "ptb_queue_flip_v1"
AUDIT_FIELDS = (
    "rt_timing_version", "rt_backend_version", "stimulus_onset_s",
    "response_timestamp_s", "n_ignored_pre_onset_keydowns",
    "response_readout_delay_s",
)
# PTB key codes, not pygame constants or Python array indices. Verified against
# Psychtoolbox/PsychBasic/KbName.m (OSX USB usages and Windows virtual keys):
# https://github.com/Psychtoolbox-3/Psychtoolbox-3/blob/master/Psychtoolbox/PsychBasic/KbName.m
KEY_CODES = {
    "darwin": {"D": 7, "J": 13, "9": 38, "KP9": 97, "SPACE": 44},
    "win32": {"D": 68, "J": 74, "9": 57, "KP9": 105, "SPACE": 32},
}


class TimingError(RuntimeError):
    """Acquisition cannot provide the requested timing contract."""


@dataclass(frozen=True)
class KeyEvent:
    key: str
    pressed: bool
    timestamp_s: float
    readout_s: float


class ResponseWindow:
    """Select a response using source timestamps, independently of rendering."""

    def __init__(self, start_s, held_keys, keymap, backend_version):
        self.start_s = start_s
        self.held_keys = set(held_keys)
        self.choices = dict(keymap)
        if not self.choices or not set(self.choices) <= set(KEY_CODES["darwin"]):
            raise TimingError("Response timing requires supported logical key names.")
        self.backend_version = backend_version
        self.onset_s = None
        self.deadline_s = None
        self.response = None
        self.response_event = None
        self.ignored_early = 0
        self._last_event_s = start_s

    def mark_onset(self, onset_s, duration_s):
        if self.onset_s is not None or not math.isfinite(onset_s) or onset_s < self.start_s:
            raise TimingError("Invalid or repeated stimulus onset timestamp.")
        if duration_s is not None and (not math.isfinite(duration_s) or duration_s <= 0):
            raise TimingError("The response deadline must be positive or absent.")
        self.onset_s = onset_s
        self.deadline_s = None if duration_s is None else onset_s + duration_s

    def keydowns(self, events):
        """Track releases and repeated downs, including before a visible onset."""
        # Stable sorting retains native queue order for equal timestamps.
        for event in sorted(events, key=lambda e: e.timestamp_s):
            if event.key not in self.choices:
                continue
            if not all(math.isfinite(v) for v in (event.timestamp_s, event.readout_s)):
                raise TimingError("Non-finite keyboard timestamp.")
            if event.readout_s < event.timestamp_s:
                raise TimingError("Keyboard event and readout clocks disagree.")
            if event.timestamp_s <= self.start_s:
                # Initial held-state snapshot already represents these events.
                continue
            if event.timestamp_s < self._last_event_s:
                raise TimingError("Keyboard events arrived out of timestamp order.")
            self._last_event_s = event.timestamp_s
            was_held = event.key in self.held_keys
            if event.pressed:
                self.held_keys.add(event.key)
            else:
                self.held_keys.discard(event.key)
                continue
            yield event, was_held

    def consume(self, events):
        if self.onset_s is None:
            raise TimingError("Display stimulus onset before selecting a response.")
        for event, was_held in self.keydowns(events):
            if event.timestamp_s < self.onset_s:
                self.ignored_early += 1
                continue
            if was_held or self.response is not None:
                continue
            if self.deadline_s is not None and event.timestamp_s >= self.deadline_s:
                continue
            self.response = self.choices[event.key]
            self.response_event = event

    def expire(self, now_s):
        """Call only AFTER draining available events, including at expiry."""
        if self.onset_s is None:
            raise TimingError("Cannot expire a trial before stimulus onset.")
        if self.response is None and self.deadline_s is not None and now_s >= self.deadline_s:
            self.response = "TIMEOUT"

    def result(self):
        if self.response is None:
            raise TimingError("Response window is not complete.")
        event = self.response_event
        return {
            "response": self.response,
            "rt_s": None if event is None else event.timestamp_s - self.onset_s,
            "rt_timing_version": TIMING_VERSION,
            "rt_backend_version": self.backend_version,
            "stimulus_onset_s": self.onset_s,
            "response_timestamp_s": None if event is None else event.timestamp_s,
            "n_ignored_pre_onset_keydowns": self.ignored_early,
            "response_readout_delay_s": None if event is None else event.readout_s - event.timestamp_s,
        }


class FlashResponses:
    """Space responses belong to [visible flash onset, next visible onset).

    Flash offset does not close its response interval. A single continuous
    held-key state prevents repeats, including keys held across flashes.
    """

    def __init__(self, start_s, held_keys, backend_version):
        self.keys = ResponseWindow(start_s, held_keys, {"SPACE": "flash"}, backend_version)
        self.flashes = []

    def add_flash(self, onset_s):
        if self.flashes:
            if onset_s <= self.flashes[-1]["onset_s"]:
                raise TimingError("Flash onsets must increase.")
            self.flashes[-1]["window_end_s"] = onset_s
        self.flashes.append(dict(onset_s=onset_s, window_end_s=None, rt=None))

    def consume(self, events, end_s=None):
        for event, was_held in self.keys.keydowns(events):
            if was_held or (end_s is not None and event.timestamp_s >= end_s):
                continue
            for flash in reversed(self.flashes):
                end = flash["window_end_s"]
                if event.timestamp_s >= flash["onset_s"] and (end is None or event.timestamp_s < end):
                    if flash["rt"] is None:
                        flash["rt"] = event.timestamp_s - flash["onset_s"]
                    break

    def export(self, stimulus_onset_s):
        return {
            "flash_onsets": ";".join(repr(f["onset_s"] - stimulus_onset_s) for f in self.flashes),
            "flash_rts": ";".join("NA" if f["rt"] is None else repr(f["rt"]) for f in self.flashes),
        }


class PsychtoolboxKeyboard:
    """One reusable native queue, active only during trial acquisition.

Only configured response keys are recorded. Queue state and initial held keys use PTB; Pygame key
state is deliberately not mixed with this input stream. No keys are trapped.
"""

    def __init__(self, *, device=None, keys=("D", "J")):
        self.device = device
        self.keys = set(keys)
        self._created = False
        self._running = False
        self._ptb = None
        self._buffer_size = 10000

    @staticmethod
    def _help():
        return (
            "Install psychtoolbox==3.0.22.2 in r-pygame and run "
            "python/check_response_timing.py --preflight. On macOS, grant Input "
            "Monitoring access to the application launching Python (Terminal or "
            "R/RStudio), then restart it. No frame-polling fallback is used."
        )

    def __enter__(self):
        try:
            if sys.platform not in KEY_CODES:
                raise TimingError("Native response timing supports Windows and macOS.")
            self.backend_version = version("psychtoolbox")
            if self.backend_version != PTB_VERSION:
                raise TimingError(f"Expected Psychtoolbox {PTB_VERSION}, found {self.backend_version}.")
            import numpy as np
            import psychtoolbox as ptb
            self._ptb = ptb
            if not self.keys or not self.keys <= set(KEY_CODES[sys.platform]):
                raise TimingError("Unsupported keyboard capture keys.")
            self.codes = {name: code for name, code in KEY_CODES[sys.platform].items() if name in self.keys}
            self.names = {code: name for name, code in self.codes.items()}
            flags = np.zeros(256, dtype=float)
            for code in self.codes.values():
                flags[code - 1] = 1
            ptb.PsychHID("KbQueueCreate", self.device, flags, 0, self._buffer_size)
            self._created = True
            # Exercise the actual queue and held-state API before any trials.
            self._begin()
            self.drain()
            self.end_trial()
            return self
        except Exception as exc:
            self.close()
            raise TimingError(f"Keyboard timing initialisation failed: {exc}. {self._help()}") from exc

    def __exit__(self, *exc):
        self.close()

    def now(self):
        value = float(self._ptb.GetSecs())
        if not math.isfinite(value):
            raise TimingError("Non-finite PTB clock reading.")
        return value

    def _begin(self):
        if not self._created or self._running:
            raise TimingError("Keyboard queue is unavailable or already recording.")
        self._ptb.PsychHID("KbQueueFlush", self.device, 3)
        self._ptb.PsychHID("KbQueueStart", self.device)
        self._running = True
        _, snapshot_s, state = self._ptb.PsychHID("KbCheck", self.device)
        # PTB returns a MATLAB-shaped (1, 256) array on some platforms.
        state = state.reshape(-1)
        if len(state) != 256:
            raise TimingError("Unexpected native keyboard-state shape.")
        snapshot_s = float(snapshot_s)
        if not math.isfinite(snapshot_s) or snapshot_s > self.now():
            raise TimingError("Keyboard state snapshot has an invalid clock.")
        held = {name for name, code in self.codes.items() if state[code - 1]}
        return snapshot_s, held

    @contextmanager
    def trial(self, keymap):
        try:
            if not set(keymap) <= self.keys:
                raise TimingError("Response keys were not enabled in the native queue.")
            start_s, held = self._begin()
            yield ResponseWindow(start_s, held, keymap, self.backend_version)
        finally:
            self.end_trial()

    def drain(self):
        if not self._running:
            raise TimingError("Cannot read a stopped keyboard queue.")
        events = []
        while True:
            raw, remaining = self._ptb.PsychHID("KbQueueGetEvent", self.device, 0)
            readout_s = self.now()
            if remaining >= self._buffer_size - 1:
                raise TimingError("Keyboard queue reached capacity; trial timing is unreliable.")
            if isinstance(raw, dict):
                code = int(raw["Keycode"])
                if code in self.names:
                    events.append(KeyEvent(self.names[code], bool(raw["Pressed"]),
                                           float(raw["Time"]), readout_s))
            elif raw is not None and len(raw):
                raise TimingError("Unexpected native keyboard-event format.")
            if not remaining:
                return events

    def end_trial(self):
        if self._running:
            self._ptb.PsychHID("KbQueueStop", self.device)
            self._running = False

    def close(self):
        try:
            self.end_trial()
        finally:
            if self._created:
                self._ptb.PsychHID("KbQueueRelease", self.device)
                self._created = False

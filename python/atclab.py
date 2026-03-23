import pygame
import random
import math
import csv
import os
import argparse
import time
import glob
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import warnings
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning
)

# ---------------- Output directory ---------------------------------------

RESULTS_DIR = "output"

# ---------------- Display parameters -------------------------------------

BASE_W = 1280
BASE_H = 720
SCREEN_WIDTH  = BASE_W
SCREEN_HEIGHT = BASE_H
FPS = 60

THEME = "dark"   # options: "grey", "dark"

SHOW_DOMS_OVERLAY = False   # set to 'True' to verify aircraft DOMS and guidecross scaled correctly

# Global UI scaling factor (computed at runtime)
UI_SCALE = 1.0

def ui(x: float) -> int:
    """Scale a pixel dimension (int)."""
    return int(round(float(x) * UI_SCALE))

# How much to expand R geometry into pixels
GEOM_SCALE_BASE = 8.0     # tuned for 1280x720
GEOM_SCALE = GEOM_SCALE_BASE

# Aircraft icon radius
CIRCLE_RADIUS_BASE  = 10
CIRCLE_RADIUS  = CIRCLE_RADIUS_BASE

# Guide cross
GUIDE_MARGIN_BASE = 20                # pixels from the left edge
GUIDE_MARGIN      = GUIDE_MARGIN_BASE
GUIDE_COLOR       = (255, 255, 0)     # pure yellow, super bright

# DOMS (minimum separation) threshold
DOMS_THRESHOLD_NM = 5.0  # global fixed threshold
DOMS_EPS_NM = 1e-6       # small buffer to avoid 5nm exactly

# ---------------- Block definitions --------------------------------------

BLOCKS = [
    # dict(
    #     name="TRAINING",
    #     N_TRIALS=1,
    #     AUTOMATION_ON=False,               # automation off
    #     AUTOMATION_ACC=1.0,                # not used (automation off), but harmless
    #     STAIRCASE_ON=True,                 # staircase on
    #     TARGET_ACC=0.80,                   # target accuracy for adaptive staircase
    #     TRIAL_FEEDBACK_ON=True,
    #     FIXATION_ON=True,
    #     ENABLE_POSTBLOCK_QUESTIONS=False,
    #     SHOW_BLOCK_FEEDBACK=True,
    #     RESET_STAIRCASE=True,              # per-block reset
    #     DRT_ON=False,
    # ),
    dict(
        name="CALIBRATION",
        N_TRIALS=300,
        AUTOMATION_ON=False,               # automation off
        AUTOMATION_ACC=1.0,                # not used (automation off), but harmless
        STAIRCASE_ON=True,                 # staircase on
        TARGET_ACC=0.80,                   # target accuracy for adaptive staircase
        TRIAL_FEEDBACK_ON=True,
        FIXATION_ON=True,
        ENABLE_POSTBLOCK_QUESTIONS=False,
        SHOW_BLOCK_FEEDBACK=True,
        RESET_STAIRCASE=True,              # if False, keep adapting across training->calibration 
        DRT_ON=False,
    ),
    dict(
        name="MANUAL",
        N_TRIALS=500,
        AUTOMATION_ON=False,               # automation off
        AUTOMATION_ACC=1.0,                # not used (automation off), but harmless
        STAIRCASE_ON=False,                # staircase off
        TARGET_ACC=0.80,                   # not used (staircase off), but harmless
        TRIAL_FEEDBACK_ON=True,
        FIXATION_ON=True,
        ENABLE_POSTBLOCK_QUESTIONS=False,
        SHOW_BLOCK_FEEDBACK=True,
        RESET_STAIRCASE=False,             # not used (staircase off), but harmless  
        DRT_ON=False,
        MASKED_AID_BANNER_ON=True,
    ),
    dict(
        name="AUTOMATION1",
        N_TRIALS=500,
        AUTOMATION_ON=True,                # automation on
        AUTOMATION_ACC=0.95,               # high reliability block
        STAIRCASE_ON=False,                # staircase off
        TARGET_ACC=0.80,                   # not used (staircase off), but harmless
        TRIAL_FEEDBACK_ON=True,
        FIXATION_ON=True,
        ENABLE_POSTBLOCK_QUESTIONS=True,
        SHOW_BLOCK_FEEDBACK=True,
        RESET_STAIRCASE=False,             # not used (staircase off), but harmless  
        DRT_ON=False,
    ),
    dict(
        name="AUTOMATION2",
        N_TRIALS=500,
        AUTOMATION_ON=True,                # automation on
        AUTOMATION_ACC=0.65,               # low reliability block
        STAIRCASE_ON=False,                # staircase off
        TARGET_ACC=0.80,                   # not used (staircase off), but harmless
        TRIAL_FEEDBACK_ON=True,
        FIXATION_ON=True,
        ENABLE_POSTBLOCK_QUESTIONS=True,
        SHOW_BLOCK_FEEDBACK=True,
        RESET_STAIRCASE=False,             # not used (staircase off), but harmless         
        DRT_ON=False,
    ),
]

# ---------------- Block instructions -------------------------------------

BLOCK_INSTRUCTIONS = {
    "CALIBRATION": [
        {
            "title": "MANUAL BLOCK",
            "body": (
                "You will now begin your first block of trials."
            ),
        },
    ],

    "MANUAL": [
        {
            "title": "MANUAL BLOCK",
            "body": (
                "In this block, there is no special information shown at the top of the display.\n"
                "There is simply a string '########', which you should ignore."
            ),
        },
    ],

    "AUTOMATION1": [
        {
            "title": "AUTOMATION BLOCK",
            "body": (
                "You will be provided with an automated decision aid to assist you with this task. "
                "The automation will recommend a classification (either conflict or non-conflict) for each aircraft pair. "
                "The recommended classification will be presented at the top of the display. "
                "If the aid shows 'CONFLICT', this means that the automation recommends you classify that aircraft pair as a conflict. "
                "If it shows 'NON-CONF', this means that the automation recommends you classify the aircraft pair as a non-conflict."
            ),
        },
        {
            "title": "",
            "body": (
                "In the next block, although the automation is highly reliable, it is not perfect, and automation advice errors are unlikely but still possible."
            ),
        },
        {
            "title": "",
            "body": (
                "In the event that the automation makes an incorrect recommendation, it is essential that you perform the correct action. "
                "Remember that deciding whether a pair is a conflict or non-conflict is your responsibility."
            ),
        },
    ],

    "AUTOMATION2": [
        {
            "title": "AUTOMATION BLOCK",
            "body": (
                "You will be provided with an automated decision aid to assist you with this task. "
                "The automation will recommend a classification (either conflict or non-conflict) for each aircraft pair. "
                "The recommended classification will be presented at the top of the display. "
                "If the aid shows 'CONFLICT', this means that the automation recommends you classify that aircraft pair as a conflict. "
                "If it shows 'NON-CONF', this means that the automation recommends you classify the aircraft pair as a non-conflict."
            ),
        },
        {
            "title": "",
            "body": (
                "In the next block, although the automation is reasonably reliable, it is not perfect, and automation advice errors may be relatively common."
            ),
        },
        {
            "title": "",
            "body": (
                "In the event that the automation makes an incorrect recommendation, it is essential that you perform the correct action. "
                "Remember that deciding whether a pair is a conflict or non-conflict is your responsibility."
            ),
        },
    ],
}


# ---------------- Adaptive staircase (DOMS discriminability) -------------

STAIRCASE_ON   = True
TARGET_ACC     = 0.80

# The controlled quantity is the GAP between mean conflict and non-conflict DOMS distributions.
# Default (0,2.5) and (7.5,10) => gap = 5.0
GAP_INIT_NM    = 5.0
# Harder step (correct response): gap -= STEP_DOWN
GAP_STEP_DOWN  = 0.2  # nm per correct (tune as needed)
# Bounds on the gap
GAP_MIN_NM     = 0.0   # nm (very hard, near threshold)
GAP_MAX_NM     = 10.0  # nm (very easy, far from threshold)
# Step-size annealing (burn-in)
STEP_DOWN_INIT_NM   = 0.5   # larger early step (e.g., 0.5 nm)
STEP_DOWN_MIN_NM    = 0.1   # minimum late step (e.g., 0.1 nm)
# Burn-in period with annealing
STAIRCASE_BURNIN = 50  # reach min step by this update count
# Calibration summary window
# None = use all eligible trials after burn-in exclusion
# int  = use only the most recent N eligible trials after burn-in exclusion
CALIB_SUMMARY_LAST_N = 150

# ---------------- Automation decision aid --------------------------------

AUTOMATION_ON  = True         # master switch
AUTOMATION_ACC = 0.90         # P(aid is correct), e.g., 0.90
AUTOMATION_DELAY_SEC = 0.0    # seconds after trial onset before it appears
# Show/hide the automation label inside each aircraft info box
AUTOMATION_IN_INFOBOX = False

# ---------------- Masked aid banner (for MANUAL blocks) ------------------

MASKED_AID_BANNER_ON   = False
MASKED_AID_BANNER_TEXT = "########"
MASKED_AID_BANNER_Y    = 20  # baseline px (will be ui()'d at draw time)

# Default number of trials
N_TRIALS       = 20

# Trial response deadline
DEADLINE_SEC   = 10.0

# Speeds (pixels/second)
SPEED_MIN = 1
SPEED_MAX = 15

# Minimum time before keypress is accepted on inter-trial screens
MIN_SCREEN_TIME_MS = 250

# ---------------- Display element colours --------------------------------

if THEME == "grey":

    BG_COLOR        = (70, 70, 70)      # dark grey background
    BG_CIRCLE_COLOR = (128, 128, 128)   # neutral grey airspace

    ROUTE_COLOR     = (0, 0, 0)         # black routes

    AIRCRAFT_COLOR  = (25, 45, 90)      # navy aircraft
    INFOBOX_COLOR   = (25, 45, 90)

    AC1_CIRCLE_COLOR   = AIRCRAFT_COLOR
    AC2_CIRCLE_COLOR   = AIRCRAFT_COLOR

    TEXT_COLOR      = (235, 235, 235)

elif THEME == "dark":

    # original dark theme
    BG_COLOR        = (20, 20, 20)      # nearly black
    BG_CIRCLE_COLOR = (30, 30, 30)      # slightly lighter airspace

    ROUTE_COLOR     = (100, 100, 100)   # grey routes

    AIRCRAFT_COLOR  = (255, 255, 255)   # white aircraft
    INFOBOX_COLOR   = (255, 255, 255)

    AC1_CIRCLE_COLOR   = AIRCRAFT_COLOR
    AC2_CIRCLE_COLOR   = AIRCRAFT_COLOR

    TEXT_COLOR      = (240, 240, 240)

# Feedback colours
CORRECT_COLOR   = (0, 200, 0)
INCORRECT_COLOR = (220, 50, 50)
TOO_SLOW_COLOR  = (200, 200, 0)
PM_COLOR        = (80, 160, 255)

# ---------------- Pre-trial fixation screen ------------------------------

FIXATION_ON = True              # master switch
FIXATION_DURATION_MS = 750      # e.g., 750 ms

FIX_COLOR = (240, 240, 240)
FIX_SIZE_BASE      = 21             # half-length of each arm (pixels)
FIX_SIZE           = FIX_SIZE_BASE
FIX_THICKNESS_BASE = 1              # line thickness
FIX_THICKNESS  = FIX_THICKNESS_BASE

# ---------------- Post-block slider questions -----------------------------

ENABLE_POSTBLOCK_SLIDERS = True

ACCURACY_SLIDER_ANCHORS = [
    (0,   "All incorrect"),
    (50,  "Half correct and half incorrect"),
    (100, "All correct"),
]

SLIDER_ITEMS_MANUAL = [
    {
        "key": "perc_self_correct",
        "question": "For your responses, what percentage do you think were correct in the preceding block of trials?",
        "anchors": ACCURACY_SLIDER_ANCHORS,
    },
]

SLIDER_ITEMS_AUTOMATION = [
    {
        "key": "perc_auto_correct",
        "question": "For the automation's recommendations, what percentage do you think were correct in the preceding block of trials?",
        "anchors": ACCURACY_SLIDER_ANCHORS,
    },
    {
        "key": "perc_self_correct",
        "question": "For your responses, what percentage do you think were correct in the preceding block of trials?",
        "anchors": ACCURACY_SLIDER_ANCHORS,
    },
]

# ---------------- Questionnaire settings ---------------------------------

ENABLE_POSTBLOCK_QUESTIONS = True

QUESTION_SCALE_MIN = 1
QUESTION_SCALE_MAX = 5

QUESTION_ITEMS = [
    {
        "question": "I believe the automated decision aid is a competent performer.",
        "left_anchor": "Strongly disagree",
        "right_anchor": "Strongly agree",
    },
    {
        "question": "I trust the automated decision aid.",
        "left_anchor": "Strongly disagree",
        "right_anchor": "Strongly agree",
    },
    {
        "question": "I have confidence in the advice given by the automated decision aid. ",
        "left_anchor": "Strongly disagree",
        "right_anchor": "Strongly agree",
    },
    {
        "question": "I can depend on the automated decision aid.",
        "left_anchor": "Strongly disagree",
        "right_anchor": "Strongly agree",
    },
    {
        "question": "I can rely on the automated decision aid to behave in consistent ways.",
        "left_anchor": "Strongly disagree",
        "right_anchor": "Strongly agree",
    },
    {
        "question": "I can rely on the automated decision aid to do its best every time I take its advice.",
        "left_anchor": "Strongly disagree",
        "right_anchor": "Strongly agree",
    },
]

# ---------------- Inter-trial question settings --------------------------

INTERTRIAL_QUESTION_EVERY = 0  # set 0/None to disable

INTERTRIAL_QUESTION_ITEM = {
    "question": "Were your thoughts more on-task or off-task?",
    "left_anchor": "More off-task",
    "right_anchor": "More on-task",
}

# ---------------- DRT parameters -----------------------------------------
FLASH_RATE             = 2/3   # e.g., 2/3 -> average 2 flashes per 3 seconds
FLASH_DURATION         = 0.15  # seconds each flash stays on
FLASH_COLOR            = (255, 255, 0)
FLASH_WIDTH_BASE       = 350   # pixels
FLASH_WIDTH            = FLASH_WIDTH_BASE
FLASH_HEIGHT_BASE      = 50    # pixels
FLASH_HEIGHT           = FLASH_HEIGHT_BASE
FLASH_Y_OFFSET_BASE    = 20    # distance from top edge
FLASH_Y_OFFSET         = FLASH_Y_OFFSET_BASE
FLASH_JITTER_FRACTION  = 0.5
FLASH_KEY              = pygame.K_SPACE  # key for flash responses

# ---------------- Response key bindings (counterbalanced) ----------------

KEY_CONFLICT     = pygame.K_d
KEY_NONCONFLICT  = pygame.K_j

# ------------------------ Staircase function -----------------------------

@dataclass
class DomGapStaircase:
    on: bool = STAIRCASE_ON
    target_acc: float = TARGET_ACC

    gap_nm: float = GAP_INIT_NM
    gap_min: float = GAP_MIN_NM
    gap_max: float = GAP_MAX_NM

    # Counts actual staircase updates (annealing clock)
    n_updates: int = 0

    # Burn in: number of early trials to force large step size
    burnin: int = STAIRCASE_BURNIN

    # Distribution width
    sd_nm: float = 0.1

    # Annealed step schedule
    step_init: float = STEP_DOWN_INIT_NM
    step_min: float = STEP_DOWN_MIN_NM
    anneal_trials: int = STAIRCASE_BURNIN

    def current_step_down(self) -> float:
        """
        Linear annealing from step_init → step_min over anneal_trials.
        """
        if self.anneal_trials <= 0:
            return float(self.step_min)

        t = float(self.n_updates)
        frac = min(1.0, max(0.0, t / float(self.anneal_trials)))

        step = float(self.step_init) - (
            float(self.step_init) - float(self.step_min)
        ) * frac

        return clamp(step, float(self.step_min), float(self.step_init))

    def means_from_gap(self, *, mid: float = 5.0) -> tuple[float, float]:
        g = clamp(float(self.gap_nm), float(self.gap_min), float(self.gap_max))
        mu_low  = mid - 0.5 * g
        mu_high = mid + 0.5 * g
        mu_low  = clamp(mu_low,  0.0, mid - DOMS_EPS_NM)
        mu_high = clamp(mu_high, mid + DOMS_EPS_NM, 10.0)
        return mu_low, mu_high

    def update(self, correct: bool):
        if not self.on:
            return

        # ---- Determine step size ----
        step_down_now = self.current_step_down()

        # During first `burnin` updates, force large step
        if self.burnin > 0 and self.n_updates < self.burnin:
            step_down_now = float(self.step_init)

        # ---- Apply update ----
        if correct:
            self.gap_nm -= step_down_now
        else:
            # Weighted up-step to target stationary accuracy
            p = max(1e-6, min(0.999999, float(self.target_acc)))
            step_up_now = step_down_now * (p / (1.0 - p))
            self.gap_nm += step_up_now

        self.gap_nm = clamp(self.gap_nm, self.gap_min, self.gap_max)

        # Advance annealing clock
        self.n_updates += 1


# ------------------------- Trial definition ------------------------------

@dataclass
class TrialSpec:
    # Start positions & velocities (from R)
    pos1_start_x: float
    pos1_start_y: float
    vel1_x: float
    vel1_y: float

    pos2_start_x: float
    pos2_start_y: float
    vel2_x: float
    vel2_y: float

    # Route line endpoints (from R)
    route1_start_x: float
    route1_start_y: float
    route1_end_x: float
    route1_end_y: float

    route2_start_x: float
    route2_start_y: float
    route2_end_x: float
    route2_end_y: float

    # Aircraft flight levels
    ac1_fl: float
    ac2_fl: float

    # Trial properties
    conflict_status: str
    is_conflict: bool
    min_sep: float          # trial-wise min sep (DOMS; gets converted to pixels)
    guide_min_sep: float    # fixed 5 NM threshold, in pixels
    deadline: float
    
    # Design variables straight from R (unscaled)
    doms_nm: float          # DOMS in nautical miles
    ttms: float             # TTMS in seconds
    angle: float            # angle between routes (deg)

    ac1_speed: float
    ac2_speed: float
    
    callsign1: str = "AAA000"
    callsign2: str = "BBB111"
    
    # ATC timing/order variables
    OOP: Optional[int] = None
    TCOP1: Optional[float] = None
    TCOP2: Optional[float] = None
    
    # Bearing angles
    theta1: Optional[float] = None
    theta2: Optional[float] = None
    
    # Optional design flags (may be None if not provided)
    is_PM: Optional[bool] = None
    pm_prop: Optional[float] = None
    automation: Optional[str] = None
    auto_fail: Optional[bool] = None
    auto_fail_prop: Optional[float] = None
    auto_delay: Optional[float] = None
    context_id: Optional[int] = None
    
    # Staircase diagnostics
    stair_gap_nm: Optional[float] = None
    stair_step_nm: Optional[float] = None
    # Per-class DOMS mean used for sampling (defined in build_atc_trial)
    doms_mu_low: Optional[float] = None
    doms_mu_high: Optional[float] = None
    # Per-class DOMS SD used for sampling (defined in build_atc_trial)
    doms_sd_low: Optional[float] = None
    doms_sd_high: Optional[float] = None
    # SD used on that trial
    doms_sd: Optional[float] = None
    stair_update_idx: Optional[int] = None


# ---------------- Results schema (fixed columns across all CSVs) ---------

ALL_RESULT_FIELDS = [
    # identifiers
    "participant_id", "run_timestamp", "block", "block_idx", "trial_idx",

    # key mappings
    "key_conflict",
    "key_nonconf",
    "key_pm",
    
    # task vars
    "stimulus", "is_conflict", "response", "rt_s", "rt_ms", "correct", "outcome", "feedback",
    "deadline_s", "doms_thresh_px", "doms_px", "doms_thresh_nm", "DOMS", "TTMS", 
    "angle_deg", "theta1_deg", "theta2_deg",
    "OOP", "TCOP1", "TCOP2", "ac1_speed", "ac2_speed",
    "callsign1", "callsign2",

    # automation
    "automation", "aid_label", "aid_correct", "auto_fail", 
    "aid_accuracy_setting", "auto_fail_prop", "aid_onset_s", "aid_onset_ms",

    # PM
    "is_PM", "PM_prop",

    # DRT
    "flash_onsets", "flash_rts",

    # intertrial thought probe
    "intertrial_q_shown", "intertrial_q_resp",

    # staircase diagnostics / generation params
    "stair_update_idx", "stair_gap_nm", "stair_step_nm",
    "doms_mu_low", "doms_mu_high",
    "doms_sd_low", "doms_sd_high", "doms_sd",

    # optional context
    "context_id",
]


def normalize_result_row(row: Dict[str, Any], fieldnames: List[str]) -> Dict[str, Any]:
    """
    Ensure:
      - missing keys become ""
      - None becomes ""
    Keeps extras too (writer will ignore extras if extrasaction='ignore').
    """
    out = dict(row)
    for k in fieldnames:
        if k not in out or out[k] is None:
            out[k] = ""
    # Also avoid literal "None" strings sneaking in
    for k, v in list(out.items()):
        if v is None:
            out[k] = ""
    return out


# ----------------------------- Utilities ---------------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def configure_display_and_scaling(*, fullscreen: bool, requested_w: int, requested_h: int):
    """
    Sets SCREEN_WIDTH/SCREEN_HEIGHT based on fullscreen display resolution (or requested window),
    computes UI_SCALE relative to BASE_W/BASE_H, and updates all scale-dependent globals.
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT, UI_SCALE
    global GEOM_SCALE
    global CIRCLE_RADIUS, GUIDE_MARGIN
    global FIX_SIZE, FIX_THICKNESS
    global FLASH_WIDTH, FLASH_HEIGHT, FLASH_Y_OFFSET

    if fullscreen:
        info = pygame.display.Info()
        SCREEN_WIDTH  = int(info.current_w)
        SCREEN_HEIGHT = int(info.current_h)
    else:
        SCREEN_WIDTH  = int(requested_w)
        SCREEN_HEIGHT = int(requested_h)

    # Scale relative to baseline; use min so everything fits on smaller dimension
    UI_SCALE = min(SCREEN_WIDTH / float(BASE_W), SCREEN_HEIGHT / float(BASE_H))

    # ---- scale geometry ----
    GEOM_SCALE = float(GEOM_SCALE_BASE) * UI_SCALE

    # ---- scale UI pixel sizes ----
    CIRCLE_RADIUS = max(2, ui(CIRCLE_RADIUS_BASE))
    GUIDE_MARGIN  = max(0, ui(GUIDE_MARGIN_BASE))

    FIX_SIZE      = max(4, ui(FIX_SIZE_BASE))
    FIX_THICKNESS = max(1, ui(FIX_THICKNESS_BASE))

    FLASH_WIDTH    = max(50, ui(FLASH_WIDTH_BASE))
    FLASH_HEIGHT   = max(10, ui(FLASH_HEIGHT_BASE))
    FLASH_Y_OFFSET = max(0, ui(FLASH_Y_OFFSET_BASE))


def configure_scaling_from_surface(surface: pygame.Surface):
    """
    Use the *actual created* display surface size (important on macOS/Retina),
    then recompute UI_SCALE and all derived globals.
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT, UI_SCALE
    global GEOM_SCALE
    global CIRCLE_RADIUS, GUIDE_MARGIN
    global FIX_SIZE, FIX_THICKNESS
    global FLASH_WIDTH, FLASH_HEIGHT, FLASH_Y_OFFSET

    SCREEN_WIDTH, SCREEN_HEIGHT = surface.get_size()

    UI_SCALE = min(SCREEN_WIDTH / float(BASE_W), SCREEN_HEIGHT / float(BASE_H))

    GEOM_SCALE = float(GEOM_SCALE_BASE) * UI_SCALE

    CIRCLE_RADIUS = max(2, ui(CIRCLE_RADIUS_BASE))
    GUIDE_MARGIN  = max(0, ui(GUIDE_MARGIN_BASE))

    FIX_SIZE      = max(4, ui(FIX_SIZE_BASE))
    FIX_THICKNESS = max(1, ui(FIX_THICKNESS_BASE))

    FLASH_WIDTH    = max(50, ui(FLASH_WIDTH_BASE))
    FLASH_HEIGHT   = max(10, ui(FLASH_HEIGHT_BASE))
    FLASH_Y_OFFSET = max(0, ui(FLASH_Y_OFFSET_BASE))
    
    
def truncnorm_sample(mu: float, sd: float, lo: float, hi: float,
                     max_tries: int = 10000) -> float:
    """
    Simple rejection sampler for a truncated normal.
    For sd=0.1 this is fast and perfectly fine.
    """
    mu = float(mu)
    sd = float(sd)
    lo = float(lo)
    hi = float(hi)

    if sd <= 0:
        return clamp(mu, lo, hi)

    for _ in range(max_tries):
        x = random.gauss(mu, sd)
        if lo <= x <= hi:
            return x

    # Fallback if mu is far outside bounds (should be rare)
    return clamp(mu, lo, hi)


def _round_or_blank(x, ndigits: int):
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        if isinstance(x, (int, float)) and math.isnan(x):
            return ""
    except Exception:
        pass
    try:
        return round(float(x), ndigits)
    except Exception:
        return x


def str2bool(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    raise argparse.ArgumentTypeError(
        f"Boolean value expected for --automation-on (got {v!r}). Use TRUE/FALSE."
    )


def is_hard_quit_event(event) -> bool:
    """
    Hard quit shortcut:
      - Option + Q (macOS)
      - Alt + Q (Windows/Linux)

    ESC is ignored entirely.
    """
    if event.type != pygame.KEYDOWN:
        return False

    # must press Q
    if event.key != pygame.K_q:
        return False

    mods = event.mod

    # Option on Mac == Alt in pygame
    return bool(mods & (pygame.KMOD_ALT | pygame.KMOD_LALT | pygame.KMOD_RALT))


def get_block_display_title(block_name: str) -> str:
    key = str(block_name).strip().upper()
    spec = BLOCK_INSTRUCTIONS.get(key, {})

    # New format: list of slides
    if isinstance(spec, list):
        if len(spec) > 0 and isinstance(spec[0], dict):
            title = str(spec[0].get("title", "")).strip()
            return title if title else f"{key} BLOCK"
        return f"{key} BLOCK"

    # Old format: single dict
    if isinstance(spec, dict):
        title = str(spec.get("title", "")).strip()
        return title if title else f"{key} BLOCK"

    return f"{key} BLOCK"
  
  
def counterbalanced_block_ordering(participant_id: int):
    """
    Cycle through the 6 permutations of (MANUAL, AUTOMATION1, AUTOMATION2).

    participant_id:
      1 -> permutation 1
      2 -> permutation 2
      ...
      6 -> permutation 6
      7 -> permutation 1 again
      etc.
    """
    perms = [
        ("MANUAL",     "AUTOMATION1", "AUTOMATION2"),
        ("MANUAL",     "AUTOMATION2", "AUTOMATION1"),
        ("AUTOMATION1","MANUAL",      "AUTOMATION2"),
        ("AUTOMATION1","AUTOMATION2", "MANUAL"),
        ("AUTOMATION2","MANUAL",      "AUTOMATION1"),
        ("AUTOMATION2","AUTOMATION1", "MANUAL"),
    ]
    idx = (int(participant_id) - 1) % 6
    return perms[idx], (idx + 1)  # also return 1-based order id for logging
  
  
def counterbalanced_key_mapping(participant_id: int):
    """
    Flip every 6 participants:
      1-6:  D=CONFLICT, J=NON-CONFLICT
      7-12: J=CONFLICT, D=NON-CONFLICT
      13-18: D=CONFLICT, J=NON-CONFLICT
      ...

    Equivalent: floor((pid-1)/6) toggles swap status.
    """
    pid = int(participant_id)
    block6_idx = (pid - 1) // 6          # 0 for 1-6, 1 for 7-12, 2 for 13-18, ...
    swapped = (block6_idx % 2) == 1      # swap on odd blocks of 6

    if not swapped:
        return {
            "conflict_key": pygame.K_d,
            "nonconflict_key": pygame.K_j,
            "conflict_label": "D",
            "nonconflict_label": "J",
            "swapped": False,
        }
    else:
        return {
            "conflict_key": pygame.K_j,
            "nonconflict_key": pygame.K_d,
            "conflict_label": "J",
            "nonconflict_label": "D",
            "swapped": True,
        }


def apply_block_settings(block: Dict[str, Any]):
    """
    Apply block-specific overrides to the module-level globals.
    This keeps the rest of the code unchanged (it reads globals).
    """
    global AUTOMATION_ON, AUTOMATION_ACC, AUTOMATION_DELAY_SEC
    global STAIRCASE_ON, TARGET_ACC
    global TRIAL_FEEDBACK_ON
    global FIXATION_ON
    global ENABLE_POSTBLOCK_QUESTIONS
    global MASKED_AID_BANNER_ON, MASKED_AID_BANNER_TEXT, MASKED_AID_BANNER_Y

    # Automation
    if "AUTOMATION_ON" in block:
        AUTOMATION_ON = bool(block["AUTOMATION_ON"])
    if "AUTOMATION_ACC" in block:
        AUTOMATION_ACC = float(block["AUTOMATION_ACC"])
    if "AUTOMATION_DELAY_SEC" in block:
        AUTOMATION_DELAY_SEC = float(block["AUTOMATION_DELAY_SEC"])

    # Masked aid banner (drawing-only; does not affect automation logic)
    if "MASKED_AID_BANNER_ON" in block:
        MASKED_AID_BANNER_ON = bool(block["MASKED_AID_BANNER_ON"])
    else:
        MASKED_AID_BANNER_ON = False  # default off unless explicitly enabled

    if "MASKED_AID_BANNER_TEXT" in block:
        MASKED_AID_BANNER_TEXT = str(block["MASKED_AID_BANNER_TEXT"])

    if "MASKED_AID_BANNER_Y" in block:
        MASKED_AID_BANNER_Y = int(block["MASKED_AID_BANNER_Y"])
        
    # Staircase
    if "STAIRCASE_ON" in block:
        STAIRCASE_ON = bool(block["STAIRCASE_ON"])
    if "TARGET_ACC" in block:
        TARGET_ACC = float(block["TARGET_ACC"])

    # Intertrial
    if "TRIAL_FEEDBACK_ON" in block:
        TRIAL_FEEDBACK_ON = bool(block["TRIAL_FEEDBACK_ON"])

    # Fixation / questionnaire convenience toggles
    if "FIXATION_ON" in block:
        FIXATION_ON = bool(block["FIXATION_ON"])
    if "ENABLE_POSTBLOCK_QUESTIONS" in block:
        ENABLE_POSTBLOCK_QUESTIONS = bool(block["ENABLE_POSTBLOCK_QUESTIONS"])


def make_automation_label(is_conflict: bool,
                          acc: Optional[float] = None) -> str:
    """
    Return the automation's displayed judgement as "CONFLICT" or "NON-CONF",
    correct with probability acc.
    """
    if acc is None:
        acc = AUTOMATION_ACC

    acc = max(0.0, min(1.0, float(acc)))

    true_label = "CONFLICT" if is_conflict else "NON-CONF"
    wrong_label = "NON-CONF" if is_conflict else "CONFLICT"

    return true_label if (random.random() < acc) else wrong_label


def sample_drt_flash_interval() -> float:
    """
    Draw a jittered inter-flash interval.

    Mean interval = 1 / FLASH_RATE.
    Actual interval is uniform in [mean*(1 - jitter), mean*(1 + jitter)].
    """
    if FLASH_RATE <= 0:
        return float("inf")

    base = 1.0 / FLASH_RATE                      # mean interval in seconds
    jitter = FLASH_JITTER_FRACTION * base
    lo = max(0.05, base - jitter)
    hi = base + jitter
    return random.uniform(lo, hi)


def load_latest_calibration_doms_params(
    results_dir: str = RESULTS_DIR,
    *,
    participant_tag: str
) -> Optional[Dict[str, float]]:
    """
    Select the newest CALIBRATION DOMS summary for this participant.

    Matches files like:
      results_p007_*_CALIBRATION_DOMS_SUMMARY.csv

    Only the participant tag must match; the timestamp/base name may differ.
    Chooses the newest matching file by modification time (mtime) and uses
    the last row.
    """
    pt = str(participant_tag).strip()
    pattern = os.path.join(results_dir, f"results_{pt}_*_CALIBRATION_DOMS_SUMMARY.csv")
    paths = glob.glob(pattern)

    if not paths:
        return None

    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    newest = paths[0]
    
    print(f"[DOMS fallback] Using calibration summary: {newest}")

    try:
        with open(newest, newline="") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return None

    if not rows:
        return None

    r = rows[-1]  # last row in newest file

    def _to_int(x, default=0):
        try:
            return int(float(x))
        except Exception:
            return default

    def _to_float(x):
        try:
            v = float(x)
            if math.isnan(v) or (not math.isfinite(v)):
                return None
            return v
        except Exception:
            return None

    n_c = _to_int(r.get("n_conflict", 0))
    n_n = _to_int(r.get("n_nonconflict", 0))

    mean_absdiff = _to_float(r.get("mean_absdiff", None))
    sd_absdiff   = _to_float(r.get("sd_absdiff", None))

    if not (n_c >= 5 and n_n >= 5):
        return None
    if any(v is None for v in (mean_absdiff, sd_absdiff)):
        return None

    mu_low_start = DOMS_THRESHOLD_NM - float(mean_absdiff)
    mu_high_start = DOMS_THRESHOLD_NM + float(mean_absdiff)
    shared_sd = max(1e-6, float(sd_absdiff))

    return {
        "mu_low_start": mu_low_start,
        "mu_high_start": mu_high_start,
        "doms_sd_low": shared_sd,
        "doms_sd_high": shared_sd,
    }


def load_trials_from_csv(path: str) -> List[TrialSpec]:
    """
    Load trials from an R-generated CSV, scaling geometry
    around the (possibly CSV-specified) screen centre.
    Updates SCREEN_WIDTH/HEIGHT if x_dim/y_dim columns are present.
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT

    trials: List[TrialSpec] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        first_row = True

        fieldnames = reader.fieldnames or []
        print("Trials CSV columns:", fieldnames)

        for row in reader:
            if first_row:
                first_row = False
                # Allow CSV to override window dimensions if present
                if "x_dim" in row and "y_dim" in row:
                    try:
                        w = int(float(row["x_dim"]))
                        h = int(float(row["y_dim"]))
                        # Only override if we're not in fullscreen resolution
                        # (fullscreen should stay at the actual surface size)
                        if (w > 0 and h > 0) and (w != SCREEN_WIDTH or h != SCREEN_HEIGHT):
                            # optional: only do this if you know you're in windowed mode
                            pass
                    except (TypeError, ValueError):
                        pass
                cx = SCREEN_WIDTH / 2.0
                cy = SCREEN_HEIGHT / 2.0

            # --- Basic conflict flag ------------------------------------
            is_conf_str = str(row["is_conflict"]).strip().lower()
            is_conflict = is_conf_str in ("true", "1", "t", "yes", "y")

            # --- Raw geometry from R ------------------------------------
            raw_x1 = float(row["x1"])
            raw_y1 = float(row["y1"])
            raw_x2 = float(row["x2"])
            raw_y2 = float(row["y2"])

            raw_v1x = float(row["ac1_vel_x"])
            raw_v1y = float(row["ac1_vel_y"])
            raw_v2x = float(row["ac2_vel_x"])
            raw_v2y = float(row["ac2_vel_y"])

            # DOMS / min_sep per trial (in NM)
            raw_doms = float(row.get("DOMS", row.get("min_sep", 0.0)))
            
            # TTMS per trial (seconds to min sep)
            ttms = float(row["TTMS"])
            angle = float(row["angle_deg"])
            
            theta1_raw = str(row.get("theta1", "")).strip()
            theta2_raw = str(row.get("theta2", "")).strip()

            theta1 = float(theta1_raw) if theta1_raw != "" else None
            theta2 = float(theta2_raw) if theta2_raw != "" else None
            
            OOP_raw = str(row.get("OOP", "")).strip()
            OOP = int(float(OOP_raw)) if OOP_raw != "" else None

            TCOP1_raw = str(row.get("TCOP1", "")).strip()
            TCOP1 = float(TCOP1_raw) if TCOP1_raw != "" else None

            TCOP2_raw = str(row.get("TCOP2", "")).strip()
            TCOP2 = float(TCOP2_raw) if TCOP2_raw != "" else None

            # -------- Optional PM / automation fields --------------------
            def parse_bool(cell: str) -> Optional[bool]:
                s = str(cell).strip()
                if s == "":
                    return None
                return s.lower() in ("1", "true", "t", "yes", "y")

            def parse_float(cell: str) -> Optional[float]:
                s = str(cell).strip()
                if s == "":
                    return None
                return float(s)

            is_PM          = parse_bool(row.get("is_PM", ""))
            pm_prop        = parse_float(row.get("PM_prop", ""))
            
            automation_raw = str(row.get("automation", "")).strip()
            automation = automation_raw or None
            auto_delay = parse_float(row.get("aid_onset_s", "")) or 0.0
            # If global automation is ON, override / populate automation fields
            if AUTOMATION_ON:
                automation = make_automation_label(is_conflict, acc=AUTOMATION_ACC)
                auto_delay = AUTOMATION_DELAY_SEC
                # auto_fail_prop = 1 - AUTOMATION_ACC
                true_lbl = "CONFLICT" if is_conflict else "NON-CONF"
                # auto_fail = (str(automation).upper() != true_lbl)
                
            auto_fail      = parse_bool(row.get("auto_fail", ""))
            auto_fail_prop = parse_float(row.get("auto_fail_prop", ""))
            context_raw    = str(row.get("context_id", "")).strip()
            context_id     = int(float(context_raw)) if context_raw else None

            # Route endpoints (unscaled from R)
            route1_start_x = float(row["x1start"])
            route1_start_y = float(row["y1start"])
            route1_end_x   = float(row["x1end"])
            route1_end_y   = float(row["y1end"])

            route2_start_x = float(row["x2start"])
            route2_start_y = float(row["y2start"])
            route2_end_x   = float(row["x2end"])
            route2_end_y   = float(row["y2end"])
            
            def scale_about_center(x, y):
                return (cx + (x - cx) * GEOM_SCALE,
                        cy + (y - cy) * GEOM_SCALE)

            route1_start_x, route1_start_y = scale_about_center(route1_start_x, route1_start_y)
            route1_end_x,   route1_end_y   = scale_about_center(route1_end_x,   route1_end_y)
            route2_start_x, route2_start_y = scale_about_center(route2_start_x, route2_start_y)
            route2_end_x,   route2_end_y   = scale_about_center(route2_end_x,   route2_end_y)

            # --- Scale positions and velocities about the centre --------
            dx1 = raw_x1 - cx
            dy1 = raw_y1 - cy
            dx2 = raw_x2 - cx
            dy2 = raw_y2 - cy

            pos1_start_x = cx + dx1 * GEOM_SCALE
            pos1_start_y = cy + dy1 * GEOM_SCALE
            pos2_start_x = cx + dx2 * GEOM_SCALE
            pos2_start_y = cy + dy2 * GEOM_SCALE

            vel1_x = raw_v1x * GEOM_SCALE
            vel1_y = raw_v1y * GEOM_SCALE
            vel2_x = raw_v2x * GEOM_SCALE
            vel2_y = raw_v2y * GEOM_SCALE

            # --- Trial-wise minimum separation (DOMS), in pixels -------
            min_sep = raw_doms * GEOM_SCALE

            # --- Global policy threshold for guide cross, in pixels -----
            guide_min_sep = DOMS_THRESHOLD_NM * GEOM_SCALE

            # Ensure velocities point toward centre
            to_cx1 = cx - pos1_start_x
            to_cy1 = cy - pos1_start_y
            to_cx2 = cx - pos2_start_x
            to_cy2 = cy - pos2_start_y

            dot1 = vel1_x * to_cx1 + vel1_y * to_cy1
            dot2 = vel2_x * to_cx2 + vel2_y * to_cy2

            if dot1 <= 0.0:
                vel1_x = -vel1_x
                vel1_y = -vel1_y
            if dot2 <= 0.0:
                vel2_x = -vel2_x
                vel2_y = -vel2_y

            trial = TrialSpec(
                pos1_start_x=pos1_start_x,
                pos1_start_y=pos1_start_y,
                vel1_x=vel1_x,
                vel1_y=vel1_y,

                pos2_start_x=pos2_start_x,
                pos2_start_y=pos2_start_y,
                vel2_x=vel2_x,
                vel2_y=vel2_y,

                route1_start_x=route1_start_x,
                route1_start_y=route1_start_y,
                route1_end_x=route1_end_x,
                route1_end_y=route1_end_y,

                route2_start_x=route2_start_x,
                route2_start_y=route2_start_y,
                route2_end_x=route2_end_x,
                route2_end_y=route2_end_y,

                ac1_fl=float(row["ac1_fl"]),
                ac2_fl=float(row["ac2_fl"]),
                
                conflict_status=row.get("conflict_status"),
                is_conflict=is_conflict,
                min_sep=min_sep,
                guide_min_sep=guide_min_sep,
                deadline=float(row.get("deadline_s", DEADLINE_SEC)),
                
                doms_nm=raw_doms,
                ttms=ttms,
                angle=angle,
                theta1=theta1,
                theta2=theta2,
                
                OOP=OOP,
                TCOP1=TCOP1,
                TCOP2=TCOP2,

                ac1_speed=float(row["ac1_speed"]),
                ac2_speed=float(row["ac2_speed"]),
                
                callsign1=row.get("callsign1", "AAA000"),
                callsign2=row.get("callsign2", "BBB111"),

                is_PM=is_PM,
                pm_prop=pm_prop,
                automation=automation,
                auto_fail=auto_fail,
                auto_fail_prop=auto_fail_prop,
                auto_delay=auto_delay,
                context_id=context_id,
            )
            trials.append(trial)

    return trials

def _random_callsign_suffix() -> str:
    num = random.randint(1, 999)
    return f"{num:03d}"

def sample_callsign_nonpm() -> str:
    """
    Non-PM constraint: first 3 letters must have NO duplicates.
    Disallow: AAB, BAA, AAA, ABA, etc. => require all three letters distinct.
    """
    letters = random.sample("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 3)  # distinct
    return "".join(letters) + _random_callsign_suffix()

def sample_callsign_pm() -> str:
    """
    PM constraint: pattern L1 == L3 (ABA123).
    Also enforce L2 != L1 to avoid AAA.
    """
    a = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    b = random.choice([c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c != a])
    return f"{a}{b}{a}{_random_callsign_suffix()}"


def sample_callsign_constrained(is_pm: bool) -> str:
    return sample_callsign_pm() if is_pm else sample_callsign_nonpm()


def degtorad(deg: float) -> float:
    return deg * math.pi / 180.0


def build_atc_trial(
    *,
    x_dim: int,
    aspect_ratio: float,
    angle_deg: float = 90.0,
    speed_range=(450, 650),
    mu_low_start: float = 2.5,
    mu_high_start: float = 7.5,
    doms_sd: float = 0.5, # default/fall-back sd
    doms_sd_low: Optional[float] = None, # sd for conflicts
    doms_sd_high: Optional[float] = None, # sd for non-conflicts
    doms_low_bounds: tuple[float, float] = (0.0, DOMS_THRESHOLD_NM - DOMS_EPS_NM),
    doms_high_bounds: tuple[float, float] = (DOMS_THRESHOLD_NM + DOMS_EPS_NM, 10.0),
    ttms_range=(180, 200),
    flight_level: int = 370,
    default_deadline: float = 10.0,
    callsigns: Optional[List[str]] = None,
    enforce_unique_callsigns: bool = False,
    used_callsigns: Optional[set] = None,
    pm_prop: float = 0.0,
    staircase: Optional[DomGapStaircase] = None,
) -> TrialSpec:
    """
    Sample ONE trial on demand, using the same math as the R generator.
    Balance constraints (conflict/nonconflict, OOP) are done as 50:50 random draws per trial.
    """
    y_dim = x_dim * aspect_ratio
    cx = 0.5 * x_dim
    cy = 0.5 * y_dim
    
    # Draw PM trial if PM proportion > 0 supplied
    pm_prop = max(0.0, min(1.0, float(pm_prop)))
    is_PM = (random.random() < pm_prop) if pm_prop > 0 else False

    # 50:50 draw for conflict vs nonconflict (instead of half/half across block)
    is_conflict_target = (random.random() < 0.5)

    # --- Optional staircase override of doms ---
    low_lo, low_hi = float(doms_low_bounds[0]), float(doms_low_bounds[1])
    high_lo, high_hi = float(doms_high_bounds[0]), float(doms_high_bounds[1])

    # Defaults come from args
    mu_low = float(mu_low_start)
    mu_high = float(mu_high_start)
    
    # Per-category SDs (fallback to doms_sd if not provided)
    sd_low  = float(doms_sd if doms_sd_low  is None else doms_sd_low)
    sd_high = float(doms_sd if doms_sd_high is None else doms_sd_high)

    stair_gap_nm = None
    stair_step_nm = None
    stair_update_idx = None

    if staircase is not None and staircase.on:
        mu_low, mu_high = staircase.means_from_gap(mid=5.0)
        stair_gap_nm = float(staircase.gap_nm)
        stair_step_nm = staircase.current_step_down()
        stair_update_idx = int(staircase.n_updates) 

    # Clamp means to their valid sides to keep truncation mild
    mu_low = clamp(mu_low, low_lo, low_hi)
    mu_high = clamp(mu_high, high_lo, high_hi)

    # Clamp SDs to something sane to avoid 0/negative
    sd_low  = max(1e-6, float(sd_low))
    sd_high = max(1e-6, float(sd_high))

    # Sample DOMS from truncated normals
    if is_conflict_target:
        doms = truncnorm_sample(mu_low, sd_low, lo=low_lo, hi=low_hi)
        sd_used = sd_low
    else:
        doms = truncnorm_sample(mu_high, sd_high, lo=high_lo, hi=high_hi)
        sd_used = sd_high

    doms = round(float(doms), 2)

    if doms == DOMS_THRESHOLD_NM:
        if is_conflict_target:
            doms = DOMS_THRESHOLD_NM - 0.01
        else:
            doms = DOMS_THRESHOLD_NM + 0.01

    conflict_status = "conflict" if doms < DOMS_THRESHOLD_NM else "nonconflict"
    is_conflict = (conflict_status == "conflict")
    
    automation = None
    auto_delay = 0.0
    auto_fail_prop = None
    auto_fail = None
    
    if AUTOMATION_ON:
        automation = make_automation_label(is_conflict, acc=AUTOMATION_ACC)
        auto_delay = AUTOMATION_DELAY_SEC
        auto_fail_prop = 1 - AUTOMATION_ACC
        true_lbl = "CONFLICT" if is_conflict else "NON-CONF"
        auto_fail = (str(automation).upper() != true_lbl)

    # 50:50 draw for OOP (instead of alternating 1,2,...)
    OOP = 1 if (random.random() < 0.5) else 2

    # Speeds and TTMS (integers like R sample(a:b))
    ac1_speed = random.randint(int(speed_range[0]), int(speed_range[1]))
    ac2_speed = random.randint(int(speed_range[0]), int(speed_range[1]))
    ttms = random.randint(int(ttms_range[0]), int(ttms_range[1]))

    # Convert to NM/sec
    v1m_sec = ac1_speed / 3600.0
    v2m_sec = ac2_speed / 3600.0

    # Angle radians
    rad = degtorad(angle_deg)

    # Lindsay ATC math
    A = v1m_sec*v1m_sec + v2m_sec*v2m_sec - 2.0*v1m_sec*v2m_sec*math.cos(rad)
    Y = v1m_sec*v2m_sec*math.sin(rad)
    W = v2m_sec - v1m_sec*math.cos(rad)

    if Y == 0.0:
        raise ValueError("Y computed as 0 (angle likely 0 or 180). Choose different angle_deg.")

    absM = doms * math.sqrt(A) / Y
    M = (-1.0 if OOP == 1 else 1.0) * absM

    TCOP1 = ttms - (v2m_sec * M * W) / A
    TCOP2 = TCOP1 + M

    dist1 = TCOP1 * v1m_sec
    dist2 = TCOP2 * v2m_sec

    # Bearing angles
    theta1 = degtorad(random.randint(0, 360))
    theta2 = theta1 + degtorad(angle_deg)

    # Raw starting positions (R-space)
    raw_x1 = cx + math.cos(theta1) * dist1
    raw_y1 = cy + math.sin(theta1) * dist1
    raw_x2 = cx + math.cos(theta2) * dist2
    raw_y2 = cy + math.sin(theta2) * dist2

    # Route endpoints on screen diagonal (R-space)
    screen_diag_radius = 0.5 * math.sqrt(x_dim*x_dim + y_dim*y_dim)

    x1start = cx + math.cos(theta1) * screen_diag_radius
    y1start = cy + math.sin(theta1) * screen_diag_radius
    x1end   = x_dim - x1start
    y1end   = y_dim - y1start

    x2start = cx + math.cos(theta2) * screen_diag_radius
    y2start = cy + math.sin(theta2) * screen_diag_radius
    x2end   = x_dim - x2start
    y2end   = y_dim - y2start

    # ---- Scale route endpoints about centre (match aircraft scaling) ----
    def scale_about_center(x, y):
        return (cx + (x - cx) * GEOM_SCALE,
                cy + (y - cy) * GEOM_SCALE)

    x1start, y1start = scale_about_center(x1start, y1start)
    x1end,   y1end   = scale_about_center(x1end,   y1end)

    x2start, y2start = scale_about_center(x2start, y2start)
    x2end,   y2end   = scale_about_center(x2end,   y2end)

    # Raw velocities (NM/sec)
    raw_v1x = v1m_sec * math.cos(theta1)
    raw_v1y = v1m_sec * math.sin(theta1)
    raw_v2x = v2m_sec * math.cos(theta2)
    raw_v2y = v2m_sec * math.sin(theta2)

    # Apply GEOM_SCALE transform about centre
    dx1, dy1 = raw_x1 - cx, raw_y1 - cy
    dx2, dy2 = raw_x2 - cx, raw_y2 - cy

    pos1_start_x = cx + dx1 * GEOM_SCALE
    pos1_start_y = cy + dy1 * GEOM_SCALE
    pos2_start_x = cx + dx2 * GEOM_SCALE
    pos2_start_y = cy + dy2 * GEOM_SCALE

    vel1_x = raw_v1x * GEOM_SCALE
    vel1_y = raw_v1y * GEOM_SCALE
    vel2_x = raw_v2x * GEOM_SCALE
    vel2_y = raw_v2y * GEOM_SCALE
    
    # ---- Ensure velocities point toward centre (robust) ----
    to_cx1 = cx - pos1_start_x
    to_cy1 = cy - pos1_start_y
    to_cx2 = cx - pos2_start_x
    to_cy2 = cy - pos2_start_y

    dot1 = vel1_x * to_cx1 + vel1_y * to_cy1
    dot2 = vel2_x * to_cx2 + vel2_y * to_cy2

    if dot1 <= 0.0:
        vel1_x = -vel1_x
        vel1_y = -vel1_y
    if dot2 <= 0.0:
        vel2_x = -vel2_x
        vel2_y = -vel2_y


    # Callsigns per trial with constraints for PM targets:
    # - If PM trial: exactly one callsign must be ABA-style (L1==L3), other must be non-PM (all distinct letters).
    # - If non-PM trial: both callsigns must be non-PM (all distinct letters).
    pm_aircraft = random.choice([1, 2]) if is_PM else None

    def draw_cs(required_pm: bool) -> str:
        # If user provides a pool, we can't guarantee letter-structure constraints.
        # So only enforce constraints when callsigns is None.
        if callsigns:
            return sample_callsign(callsigns)

        for _ in range(20000):
            cs = sample_callsign_constrained(required_pm)
            if not enforce_unique_callsigns or used_callsigns is None:
                return cs
            if cs not in used_callsigns:
                used_callsigns.add(cs)
                return cs
        # fallback
        return sample_callsign_constrained(required_pm)

    if is_PM:
        # One PM-pattern callsign, one non-PM callsign
        if pm_aircraft == 1:
            c1 = draw_cs(required_pm=True)
            c2 = draw_cs(required_pm=False)
        else:
            c1 = draw_cs(required_pm=False)
            c2 = draw_cs(required_pm=True)
    else:
        c1 = draw_cs(required_pm=False)
        c2 = draw_cs(required_pm=False)

    # ensure within-trial different callsigns
    if enforce_unique_callsigns and used_callsigns is not None:
        # already handled by used_callsigns (across-block), but still protect within-trial
        tries = 0
        while c2 == c1 and tries < 5000:
            # redraw c2 with the same required type
            if is_PM and pm_aircraft == 2:
                c2 = draw_cs(required_pm=True)
            else:
                c2 = draw_cs(required_pm=False)
            tries += 1
    else:
        while c2 == c1:
            if is_PM and pm_aircraft == 2:
                c2 = draw_cs(required_pm=True)
            else:
                c2 = draw_cs(required_pm=False)

    # Separations
    min_sep = doms * GEOM_SCALE
    guide_min_sep = DOMS_THRESHOLD_NM * GEOM_SCALE

    return TrialSpec(
        pos1_start_x=pos1_start_x,
        pos1_start_y=pos1_start_y,
        vel1_x=vel1_x,
        vel1_y=vel1_y,

        pos2_start_x=pos2_start_x,
        pos2_start_y=pos2_start_y,
        vel2_x=vel2_x,
        vel2_y=vel2_y,

        route1_start_x=x1start,
        route1_start_y=y1start,
        route1_end_x=x1end,
        route1_end_y=y1end,

        route2_start_x=x2start,
        route2_start_y=y2start,
        route2_end_x=x2end,
        route2_end_y=y2end,

        ac1_speed=float(ac1_speed),
        ac2_speed=float(ac2_speed),
        ac1_fl=float(flight_level),
        ac2_fl=float(flight_level),

        OOP=int(OOP),
        TCOP1=float(TCOP1),
        TCOP2=float(TCOP2),
        
        callsign1=c1,
        callsign2=c2,
        
        conflict_status=conflict_status,
        is_conflict=is_conflict,
        min_sep=min_sep,
        guide_min_sep=guide_min_sep,
        deadline=float(default_deadline),
        
        doms_nm=float(doms),
        ttms=float(ttms),
        angle=float(angle_deg),
        theta1=float(theta1),
        theta2=float(theta2),

        is_PM=bool(is_PM),
        pm_prop=float(pm_prop) if pm_prop > 0 else None,
        
        automation=automation,
        auto_delay=auto_delay,
        auto_fail_prop=auto_fail_prop,
        auto_fail=auto_fail, 
        
        stair_gap_nm=stair_gap_nm,
        stair_step_nm=stair_step_nm,
        doms_mu_low=mu_low,
        doms_mu_high=mu_high,
        doms_sd_low=sd_low,
        doms_sd_high=sd_high,
        doms_sd=sd_used,
        stair_update_idx=stair_update_idx,

    )


# ---------------------------- Drawing helpers ----------------------------

def draw_text(screen, font, text, color, center, antialias=True):
    surf = font.render(text, antialias, color)
    rect = surf.get_rect(center=center)
    screen.blit(surf, rect)


def draw_guide_cross(screen, center_x, center_y, min_sep,
                     color=GUIDE_COLOR, thickness=1, tick_len=8):
    """
    Draw a guide cross whose horizontal arm length from the centre = min_sep
    and vertical arm length from the centre = 2 * min_sep.
    """
    tick_len = ui(tick_len)
    h_half = min_sep
    v_half = min_sep * 2

    pygame.draw.line(
        screen,
        color,
        (center_x - h_half, center_y),
        (center_x + h_half, center_y),
        thickness,
    )

    pygame.draw.line(
        screen,
        color,
        (center_x, center_y - v_half),
        (center_x, center_y + v_half),
        thickness,
    )

    h_segment = h_half / 5.0
    for i in range(1, 5):
        offset = h_segment * i
        x_left = center_x - offset
        x_right = center_x + offset

        pygame.draw.line(
            screen,
            color,
            (x_left, center_y - tick_len / 2.0),
            (x_left, center_y + tick_len / 2.0),
            1,
        )
        pygame.draw.line(
            screen,
            color,
            (x_right, center_y - tick_len / 2.0),
            (x_right, center_y + tick_len / 2.0),
            1,
        )

    long_tick = tick_len * 2.0
    for x_end in (center_x - h_half, center_x + h_half):
        pygame.draw.line(
            screen,
            color,
            (x_end, center_y - long_tick / 2.0),
            (x_end, center_y + long_tick / 2.0),
            1,
        )

    v_segment = v_half / 10.0
    for i in range(1, 10):
        offset = v_segment * i
        y_up = center_y - offset
        y_down = center_y + offset

        pygame.draw.line(
            screen,
            color,
            (center_x - tick_len / 2.0, y_up),
            (center_x + tick_len / 2.0, y_up),
            1,
        )
        pygame.draw.line(
            screen,
            color,
            (center_x - tick_len / 2.0, y_down),
            (center_x + tick_len / 2.0, y_down),
            1,
        )

    for y_end in (center_y - v_half, center_y + v_half):
        pygame.draw.line(
            screen,
            color,
            (center_x - long_tick / 2.0, y_end),
            (center_x + long_tick / 2.0, y_end),
            1,
        )


def draw_doms_marker_and_label(
    screen,
    font,
    *,
    trial: TrialSpec,
    guide_x: float,
    guide_y: float,
    guide_min_sep: float,
    doms_px: float,
    doms_nm: float,
    color=TEXT_COLOR,
    line_color=(255, 255, 255),
):
    """
    Draw the realised DOMS in two places:

    1. A horizontal reference line under the guide cross right arm
    2. The realised minimum-separation segment at the actual point of
       closest approach between the two aircraft trajectories
    """

    # =========================================================
    # 1) DOMS reference line under the guide cross
    # =========================================================
    gap_below_arm = ui(14)
    line_y = int(guide_y + gap_below_arm)

    x0 = int(guide_x)
    x1 = int(guide_x + doms_px)

    if x1 <= x0:
        x1 = x0 + 1

    line_w = max(1, ui(2))
    tick_w = max(1, ui(1))
    tick_h = ui(8)

    pygame.draw.line(screen, line_color, (x0, line_y), (x1, line_y), line_w)

    pygame.draw.line(
        screen, line_color,
        (x0, int(line_y - tick_h / 2)),
        (x0, int(line_y + tick_h / 2)),
        tick_w,
    )

    pygame.draw.line(
        screen, line_color,
        (x1, int(line_y - tick_h / 2)),
        (x1, int(line_y + tick_h / 2)),
        tick_w,
    )

    # =========================================================
    # 2) Realised DOMS segment at point of minimum separation
    # =========================================================
    p1x0 = float(trial.pos1_start_x)
    p1y0 = float(trial.pos1_start_y)
    p2x0 = float(trial.pos2_start_x)
    p2y0 = float(trial.pos2_start_y)

    v1x = float(trial.vel1_x)
    v1y = float(trial.vel1_y)
    v2x = float(trial.vel2_x)
    v2y = float(trial.vel2_y)

    # Relative motion: aircraft 2 relative to aircraft 1
    rx = p2x0 - p1x0
    ry = p2y0 - p1y0
    vx = v2x - v1x
    vy = v2y - v1y

    vv = vx * vx + vy * vy

    if vv > 1e-12:
        t_min = - (rx * vx + ry * vy) / vv
    else:
        t_min = 0.0

    t_min = max(0.0, t_min)

    p1_min_x = p1x0 + v1x * t_min
    p1_min_y = p1y0 + v1y * t_min
    p2_min_x = p2x0 + v2x * t_min
    p2_min_y = p2y0 + v2y * t_min

    # Draw the realised DOMS segment
    pygame.draw.line(
        screen,
        line_color,
        (int(p1_min_x), int(p1_min_y)),
        (int(p2_min_x), int(p2_min_y)),
        max(1, ui(2)),
    )

    # Hollow circles at each end, matching aircraft radius/appearance
    aircraft_outline_w = max(1, ui(1))
    pygame.draw.circle(
        screen,
        line_color,
        (int(p1_min_x), int(p1_min_y)),
        CIRCLE_RADIUS,
        aircraft_outline_w,
    )
    pygame.draw.circle(
        screen,
        line_color,
        (int(p2_min_x), int(p2_min_y)),
        CIRCLE_RADIUS,
        aircraft_outline_w,
    )

    # =========================================================
    # 3) DOMS label under the guide cross
    # =========================================================
    guide_bottom_y = int(guide_y + 2 * guide_min_sep)

    label = f"DOMS: {doms_nm:.2f} nm ({doms_px:.1f} px)"
    label_surf = font.render(label, True, color)

    # shift right so it does not hug the left edge
    label_x = int(guide_x + ui(40))

    label_rect = label_surf.get_rect(
        midtop=(label_x, guide_bottom_y + ui(10))
    )

    screen.blit(label_surf, label_rect)

    return {
        "line_start": (x0, line_y),
        "line_end": (x1, line_y),
        "label_rect": label_rect,
        "closest_seg_start": (p1_min_x, p1_min_y),
        "closest_seg_end": (p2_min_x, p2_min_y),
        "closest_t": t_min,
    }
    
    
def draw_fixation_cross(screen,
                        center,
                        color=FIX_COLOR,
                        size: Optional[int] = None,
                        thickness: Optional[int] = None):
    # IMPORTANT: defaults must be evaluated at call time, not definition time
    if size is None:
        size = FIX_SIZE
    if thickness is None:
        thickness = FIX_THICKNESS

    cx, cy = int(center[0]), int(center[1])
    pygame.draw.line(screen, color, (cx - size, cy), (cx + size, cy), thickness)
    pygame.draw.line(screen, color, (cx, cy - size), (cx, cy + size), thickness)


def draw_info_box(screen, font, callsign, speed_text, top_left,
                  auto_text=None, padding=4, fg=TEXT_COLOR):
    """
    Draw left-justified lines:
      callsign
      'B737'
      speed_text
      [optional] auto_text
    """
    cs_surf   = font.render(callsign, True, fg)
    type_surf = font.render("B737",   True, fg)
    sp_surf   = font.render(speed_text, True, fg)

    auto_surf = None
    if auto_text is not None:
        auto_upper = auto_text.upper()
        auto_color = fg

        if "NON-CONF" in auto_upper or "NONCONFLICT" in auto_upper:
            auto_color = CORRECT_COLOR
        elif "CONFLICT" in auto_upper:
            auto_color = INCORRECT_COLOR

        auto_surf = font.render(auto_text, True, auto_color)

    gap = 2

    width = max(
        cs_surf.get_width(),
        type_surf.get_width(),
        sp_surf.get_width(),
        auto_surf.get_width() if auto_surf is not None else 0,
    )
    height = (
        cs_surf.get_height()
        + type_surf.get_height()
        + sp_surf.get_height()
        + (auto_surf.get_height() if auto_surf is not None else 0)
        + 3 * gap
    )

    box_rect = pygame.Rect(
        int(top_left[0]),
        int(top_left[1]),
        int(width + 2 * padding),
        int(height + 2 * padding),
    )

    x = box_rect.left + padding
    y = box_rect.top + padding

    cs_rect   = cs_surf.get_rect(topleft=(x, y))
    type_rect = type_surf.get_rect(topleft=(x, cs_rect.bottom + gap))
    sp_rect   = sp_surf.get_rect(topleft=(x, type_rect.bottom + gap))

    if auto_surf is not None:
        auto_rect = auto_surf.get_rect(topleft=(x, sp_rect.bottom + gap))

    screen.blit(cs_surf, cs_rect)
    screen.blit(type_surf, type_rect)
    screen.blit(sp_surf, sp_rect)
    if auto_surf is not None:
        screen.blit(auto_surf, auto_rect)

    return box_rect


def draw_aid_banner_top_center(screen,
                              small_font,
                              big_font,
                              label: str,
                              y: int = 14,
                              fg=TEXT_COLOR):
    """
    Draw centered banner at top:
      small:  'Aid judges:'
      large:  CONFLICT / NON-CONF
    """

    # ----- Line 1: small text -----
    line1 = "AID JUDGES:"
    surf1 = small_font.render(line1, True, fg)
    rect1 = surf1.get_rect(midtop=(SCREEN_WIDTH // 2, y))
    screen.blit(surf1, rect1)

    # ----- Line 2: larger coloured label -----
    label_up = (label or "").upper()
    label_color = fg

    if "NON-CONF" in label_up or "NONCONFLICT" in label_up:
        label_color = CORRECT_COLOR
    elif "CONFLICT" in label_up:
        label_color = INCORRECT_COLOR

    surf2 = big_font.render(label, True, label_color)
    rect2 = surf2.get_rect(
        midtop=(SCREEN_WIDTH // 2, rect1.bottom + 2)
    )
    screen.blit(surf2, rect2)

    return rect2.bottom


def draw_blank_radar(screen, trial: TrialSpec, cx: float, cy: float, border_color=None):
    """Draw background radar + guide cross (no aircraft, no routes)."""
    screen.fill(BG_COLOR)

    # Background circle
    big_radius = SCREEN_HEIGHT // 2
    pygame.draw.circle(
        screen,
        BG_CIRCLE_COLOR,
        (int(cx), int(cy)),
        big_radius,
        0,
    )
    
    # Route lines
    pygame.draw.line(
        screen,
        ROUTE_COLOR,
        (int(trial.route1_start_x), int(trial.route1_start_y)),
        (int(trial.route1_end_x),   int(trial.route1_end_y)),
        1,
    )
    pygame.draw.line(
        screen,
        ROUTE_COLOR,
        (int(trial.route2_start_x), int(trial.route2_start_y)),
        (int(trial.route2_end_x),   int(trial.route2_end_y)),
        1,
    )

    # Optional context border
    if border_color is not None:
        pygame.draw.rect(
            screen,
            border_color,
            screen.get_rect(),
            8
        )

    # Guide cross
    guide_x = int(GUIDE_MARGIN + trial.guide_min_sep)
    guide_y = SCREEN_HEIGHT // 2
    draw_guide_cross(screen, guide_x, guide_y, trial.guide_min_sep)

    if SHOW_DOMS_OVERLAY:
        draw_doms_marker_and_label(
            screen,
            font=pygame.font.Font(None, max(14, ui(20))),
            trial=trial,
            guide_x=guide_x,
            guide_y=guide_y,
            guide_min_sep=trial.guide_min_sep,
            doms_px=trial.min_sep,
            doms_nm=trial.doms_nm,
            color=TEXT_COLOR,
            line_color=(255, 255, 255),
        )
        

def draw_instruction_line(screen, font, line, y, default_color=TEXT_COLOR):
    """
    Draw a single instruction line centred horizontally.
    (Plain: no keyword colouring)
    """
    surf = font.render(str(line), True, default_color)
    rect = surf.get_rect(midtop=(SCREEN_WIDTH // 2, int(y)))
    screen.blit(surf, rect)

def draw_centered_instruction_screen(
    screen,
    title_font,
    body_font,
    bold_font,
    title,
    lines
):
    """
    Draw a centered instruction screen.

    If title == "", the title row is skipped entirely
    so no vertical space is reserved.
    """

    cx = SCREEN_WIDTH // 2
    cy = SCREEN_HEIGHT // 2

    body_line_h = body_font.get_linesize()
    body_spacing = int(body_line_h * 1.35)

    title_line_h = title_font.get_linesize()

    has_title = bool(title.strip())

    # Compute total content height
    content_h = len(lines) * body_spacing

    if has_title:
        content_h += title_line_h + ui(30)

    y = cy - content_h // 2

    # Draw title only if present
    if has_title:
        title_img = title_font.render(title, True, TEXT_COLOR)
        screen.blit(title_img, (cx - title_img.get_width() // 2, y))
        y += title_line_h + ui(30)

    # Draw body lines
    for line in lines:
        if line == "":
            y += body_spacing
            continue

        if line.startswith("Press"):
            font = bold_font
        else:
            font = body_font

        draw_instruction_line(screen, font, line, y)
        y += body_spacing
        
    
def wrap_text_lines(font, text: str, max_width: int) -> List[str]:
    """
    Wrap a block of text to fit within max_width using pygame font metrics.
    Preserves explicit blank lines (paragraph breaks).
    Returns a list of lines, where "" indicates a paragraph break.
    """
    if text is None:
        return []

    # Normalize newlines
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")

    out_lines: List[str] = []
    paragraphs = text.split("\n")

    for p in paragraphs:
        # Preserve explicit blank lines
        if p.strip() == "":
            out_lines.append("")
            continue

        words = p.split()
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_width:
                cur = test
            else:
                if cur:
                    out_lines.append(cur)
                cur = w

        if cur:
            out_lines.append(cur)

    return out_lines
  
  
def block_tag(order_index_1based: int) -> str:
    """Format presentation-order block tag: b01, b02, ..."""
    return f"b{int(order_index_1based):02d}"


def make_base_name(args: argparse.Namespace, run_ts: str) -> str:
    """Base name used in filenames (trial csv base if provided; else timestamp)."""
    trial_csv_path = getattr(args, "trial_csv", None)
    if trial_csv_path:
        return os.path.splitext(os.path.basename(trial_csv_path))[0]
    return str(run_ts)


def wrap_text_to_width(font, text: str, max_width: int) -> List[str]:
    """
    Wrap a single-line string into multiple lines so each line fits max_width (pixels).
    """
    words = str(text).split()
    if not words:
        return [""]

    lines = []
    cur = words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        if font.size(test)[0] <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines
  
  
# ------------------------- Questionnaire screens ------------------------

def run_participant_number_screen(screen, clock, font) -> Dict[str, Any]:
    """
    Initial screen before instructions.
    Requires numeric participant number input before continuing.
    Clickable "Continue" button is disabled until a number is entered.

    Returns:
      {"quit": True}                          on quit/escape
      {"quit": False, "participant": <int>}   on success
    """
    prompt = "Enter participant number:"
    entry = ""
    active = True  # input box focused by default

    base_h = font.get_linesize()
    gap = int(base_h * 1.2)

    # Layout
    input_w = ui(260)
    input_h = ui(52)  # was ~ base_h*1.6; make it stable across font sizes

    btn_w = ui(220)
    btn_h = ui(60)

    cx = SCREEN_WIDTH // 2
    cy = SCREEN_HEIGHT // 2

    prompt_y = cy - 2 * gap
    input_rect = pygame.Rect(cx - input_w // 2, cy - input_h // 2, input_w, input_h)
    btn_rect = pygame.Rect(cx - btn_w // 2, input_rect.bottom + gap, btn_w, btn_h)

    # Simple blink cursor
    blink_period = 0.55
    last_blink = time.perf_counter()
    cursor_on = True

    while True:
        clock.tick(FPS)

        now = time.perf_counter()
        if (now - last_blink) >= blink_period:
            cursor_on = not cursor_on
            last_blink = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button

            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}

                # Allow Enter as a convenience *only if* valid
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if entry.isdigit() and len(entry) > 0:
                        return {"quit": False, "participant": int(entry)}
                    continue

                if active:
                    if event.key == pygame.K_BACKSPACE:
                        entry = entry[:-1]
                    else:
                        # digits only
                        ch = event.unicode
                        if ch.isdigit():
                            entry += ch

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                # click input box toggles focus
                if input_rect.collidepoint(mx, my):
                    active = True
                else:
                    active = False

                # click Continue if enabled
                if btn_rect.collidepoint(mx, my):
                    if entry.isdigit() and len(entry) > 0:
                        return {"quit": False, "participant": int(entry)}

        # --- Draw ---
        screen.fill(BG_COLOR)

        # Prompt
        draw_text(screen, font, prompt, TEXT_COLOR, (cx, prompt_y))

        # Input box
        border_col = TEXT_COLOR if active else (140, 140, 140)
        pygame.draw.rect(screen, border_col, input_rect, max(1, ui(2)))

        # Render entry + cursor
        show = entry
        if active and cursor_on:
            show = entry + "|"

        # keep text inside the box (simple left padding)
        pad_x = ui(10)
        text_surf = font.render(show, True, TEXT_COLOR)
        text_pos = (input_rect.left + pad_x, input_rect.centery - text_surf.get_height() // 2)
        screen.blit(text_surf, text_pos)

        # Continue button (disabled until valid)
        enabled = entry.isdigit() and len(entry) > 0

        # button fill + border (no new colors defined; keep it simple)
        if enabled:
            pygame.draw.rect(screen, (50, 50, 50), btn_rect, 0)
            pygame.draw.rect(screen, TEXT_COLOR, btn_rect, max(1, ui(3)))
            label_col = TEXT_COLOR
        else:
            pygame.draw.rect(screen, (35, 35, 35), btn_rect, 0)
            pygame.draw.rect(screen, (110, 110, 110), btn_rect, max(1, ui(2)))
            label_col = (140, 140, 140)

        draw_text(screen, font, "Continue", label_col, btn_rect.center)

        pygame.display.flip()


def run_likert_question(screen, clock, font, item,
                        scale_min=QUESTION_SCALE_MIN,
                        scale_max=QUESTION_SCALE_MAX,
                        label_font=None,
                        title_font=None,
                        min_show_ms: int = 250):
    """
    Present a single Likert-style question using the same slider-bar style
    as the post-block percentage slider.

    - 5 snapped positions
    - current anchor text shown above the slider
    - Continue button disabled until slider moved at least once
    - returns selected numeric value (e.g., 1..5)
    """
    if label_font is None:
        label_font = font
    if title_font is None:
        title_font = font

    t0 = pygame.time.get_ticks()

    question = str(item["question"])

    valid_values = list(range(scale_min, scale_max + 1))
    anchor_labels = [
        "Strongly disagree",
        "Disagree",
        "Neither agree nor disagree",
        "Agree",
        "Strongly agree",
    ]

    if len(valid_values) != len(anchor_labels):
        raise ValueError("anchor_labels length must match number of scale values")

    # Start in the middle, but this does NOT count as having responded
    current_idx = len(valid_values) // 2
    dragging = False
    slider_moved = False

    # --- Layout ---
    content_w = SCREEN_WIDTH - ui(240)
    content_x = ui(120)
    cx = SCREEN_WIDTH // 2

    # Slider geometry
    track_w = min(ui(760), content_w)
    track_h = max(2, ui(8))
    knob_r  = max(6, ui(12))

    track_x = cx - track_w // 2
    track_y = SCREEN_HEIGHT // 2

    track_rect = pygame.Rect(track_x, track_y, track_w, track_h)

    # 5 snapped positions across the track
    if len(valid_values) == 1:
        tick_xs = [track_x + track_w // 2]
    else:
        tick_xs = [
            track_x + int(round(i * track_w / (len(valid_values) - 1)))
            for i in range(len(valid_values))
        ]

    # Continue button
    btn_w = ui(220)
    btn_h = ui(64)
    btn_rect = pygame.Rect(cx - btn_w // 2, track_y + ui(170), btn_w, btn_h)

    # Question text area above slider
    q_rect = pygame.Rect(content_x, track_y - ui(220), content_w, ui(180))

    def idx_to_value(idx):
        idx = max(0, min(idx, len(valid_values) - 1))
        return valid_values[idx]

    def idx_to_x(idx):
        idx = max(0, min(idx, len(tick_xs) - 1))
        return tick_xs[idx]

    def x_to_idx(mx):
        return min(range(len(tick_xs)), key=lambda i: abs(mx - tick_xs[i]))

    while True:
        clock.tick(FPS)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pass

            if ev.type == pygame.KEYDOWN:
                if is_hard_quit_event(ev):
                    return {"quit": True}

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                elapsed = pygame.time.get_ticks() - t0

                # Continue button
                if btn_rect.collidepoint(mx, my) and slider_moved and elapsed >= min_show_ms:
                    return int(idx_to_value(current_idx))

                # Click on/near track starts dragging
                track_hit = track_rect.inflate(0, ui(40))
                knob_x = idx_to_x(current_idx)
                knob_y = track_y + track_h // 2
                knob_hit = pygame.Rect(
                    knob_x - knob_r - ui(8),
                    knob_y - knob_r - ui(8),
                    2 * (knob_r + ui(8)),
                    2 * (knob_r + ui(8)),
                )

                if track_hit.collidepoint(mx, my) or knob_hit.collidepoint(mx, my):
                    current_idx = x_to_idx(mx)
                    dragging = True
                    slider_moved = True

            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                dragging = False

            if ev.type == pygame.MOUSEMOTION and dragging:
                mx, _ = ev.pos
                current_idx = x_to_idx(mx)
                slider_moved = True

        # --- Draw ---
        screen.fill(BG_COLOR)

        # Wrapped question, centered above slider
        max_w = q_rect.width
        q_lines = wrap_text_lines(font, question, max_w)
        line_h = font.get_linesize()
        line_spacing = int(line_h * 1.35)

        total_q_h = len([ln for ln in q_lines if ln != ""]) * line_spacing
        y = q_rect.y + max(0, (q_rect.height - total_q_h) // 2)

        for line in q_lines:
            if line == "":
                y += line_spacing
                continue
            draw_instruction_line(screen, font, line, y)
            y += line_spacing

        # Current selected anchor above slider
        current_label = anchor_labels[current_idx]
        current_img = title_font.render(current_label, True, TEXT_COLOR)
        screen.blit(current_img, (cx - current_img.get_width() // 2, track_y - ui(70)))

        # Track
        pygame.draw.rect(
            screen,
            (170, 170, 170),
            track_rect,
            border_radius=max(1, ui(6))
        )

        # Fill up to knob
        knob_x = idx_to_x(current_idx)
        fill_w = knob_x - track_x
        if fill_w > 0:
            fill_rect = pygame.Rect(track_x, track_y, fill_w, track_h)
            pygame.draw.rect(
                screen,
                TEXT_COLOR,
                fill_rect,
                border_radius=max(1, ui(6))
            )

        # Tick marks
        for tx in tick_xs:
            pygame.draw.line(
                screen,
                TEXT_COLOR,
                (tx, track_y - ui(10)),
                (tx, track_y + track_h + ui(10)),
                max(1, ui(2))
            )

        # Knob
        knob_y = track_y + track_h // 2
        pygame.draw.circle(screen, TEXT_COLOR, (knob_x, knob_y), knob_r)

        # End labels under the slider
        left_lab = anchor_labels[0]
        right_lab = anchor_labels[-1]

        left_img = label_font.render(left_lab, True, TEXT_COLOR)
        right_img = label_font.render(right_lab, True, TEXT_COLOR)

        labels_y = track_y + ui(26)
        screen.blit(left_img, (track_x, labels_y))
        screen.blit(right_img, (track_x + track_w - right_img.get_width(), labels_y))

        # Hint between slider and button
        hint = "Drag the slider to respond"
        hint_y = track_y + ui(90)
        draw_text(screen, font, hint, TEXT_COLOR, (cx, hint_y))

        # Continue button
        elapsed = pygame.time.get_ticks() - t0
        enabled = slider_moved and elapsed >= min_show_ms

        if enabled:
            pygame.draw.rect(screen, (50, 50, 50), btn_rect, 0, border_radius=ui(8))
            pygame.draw.rect(screen, TEXT_COLOR, btn_rect, max(1, ui(3)), border_radius=ui(8))
            label_col = TEXT_COLOR
        else:
            pygame.draw.rect(screen, (35, 35, 35), btn_rect, 0, border_radius=ui(8))
            pygame.draw.rect(screen, (110, 110, 110), btn_rect, max(1, ui(2)), border_radius=ui(8))
            label_col = (140, 140, 140)

        draw_text(screen, font, "Continue", label_col, btn_rect.center)

        pygame.display.flip()

def run_questionnaire_intro_screen(screen, clock, font, title_font):
    """
    Pre-questionnaire instruction screen (VERTICALLY CENTERED).
    """
    title = "AUTOMATED DECISION AID"
    body = (
        "The following questionnaire relates to your trust in the Automated Decision Aid. "
        "For each item, the scale ranges from strongly disagree to strongly agree. "
        "Please indicate how much you agree or disagree with the following statements "
        "by ticking the appropriate box."
    )
    prompt = "Press any key to continue"

    min_show_s = float(MIN_SCREEN_TIME_MS) / 1000.0
    start_time = time.perf_counter()

    # ---- Wrap body ----
    side_margin = ui(120)
    max_w = max(ui(600), SCREEN_WIDTH - 2 * side_margin)
    body_lines = wrap_text_lines(font, body, max_w)

    # ---- Metrics ----
    title_h = title_font.get_linesize()
    body_h = font.get_linesize()

    line_spacing = int(body_h * 1.5)
    paragraph_gap = int(body_h * 2.5)

    # ---- Compute total height of all content ----
    total_height = 0

    # Title
    total_height += title_h
    total_height += ui(40)  # gap below title

    # Body
    for line in body_lines:
        if line == "":
            total_height += paragraph_gap
        else:
            total_height += line_spacing

    # Gap before prompt
    total_height += paragraph_gap

    # Prompt line
    total_height += line_spacing

    # ---- Compute vertically centered start Y ----
    y = (SCREEN_HEIGHT - total_height) // 2

    showing = True
    while showing:
        clock.tick(FPS)
        screen.fill(BG_COLOR)

        # ---- Title ----
        title_surf = title_font.render(title, True, TEXT_COLOR)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, y + title_h // 2))
        screen.blit(title_surf, title_rect)

        y_body = title_rect.bottom + ui(40)

        # ---- Body ----
        for line in body_lines:
            if line == "":
                y_body += paragraph_gap
                continue

            draw_instruction_line(screen, font, line, y_body)
            y_body += line_spacing

        # ---- Prompt ----
        y_body += paragraph_gap
        draw_instruction_line(screen, font, prompt, y_body)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass
            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}
                if (time.perf_counter() - start_time) >= min_show_s:
                    showing = False

    return {"quit": False}
  
def run_postblock_questionnaire(screen, clock, font, base_name=None, label_font=None):
    """
    Present all post-block QUESTION_ITEMS if enabled.
    """
    if label_font is None:
        label_font = font
    
    if not ENABLE_POSTBLOCK_QUESTIONS or not QUESTION_ITEMS:
        return []

    responses = []
    n_q = len(QUESTION_ITEMS)

    for idx, item in enumerate(QUESTION_ITEMS, start=1):
        resp = run_likert_question(
            screen,
            clock,
            font,
            item,
            scale_min=QUESTION_SCALE_MIN,
            scale_max=QUESTION_SCALE_MAX,
            label_font=label_font,
            title_font=font,
        )

        if isinstance(resp, dict) and resp.get("quit"):
            return {"quit": True}

        responses.append({
            # "block_id": base_name if base_name is not None else "",
            "question_idx": idx,
            "question": item["question"],
            "left_anchor": item["left_anchor"],
            "right_anchor": item["right_anchor"],
            "response": int(resp),
            "scale_min": QUESTION_SCALE_MIN,
            "scale_max": QUESTION_SCALE_MAX,
        })

    return responses

def get_postblock_slider_items(block_name: str):
    """
    Choose which slider questions to show for this block.
    """
    name = str(block_name).strip().upper()

    if name in ("CALIBRATION", "MANUAL"):
        return SLIDER_ITEMS_MANUAL
    if name in ("AUTOMATION1", "AUTOMATION2"):
        return SLIDER_ITEMS_AUTOMATION
    return []

def run_slider_question(screen, clock, font_title, font_body, item,
                        initial_value: int = 50,
                        min_show_ms: int = 250):
    """
    Present one 0-100 slider question.
    User must drag the slider, then click Continue.

    Supports optional anchor labels via item["anchors"], e.g.
        "anchors": [
            (0,   "All incorrect"),
            (50,  "Half correct and half incorrect"),
            (100, "All correct"),
        ]

    Returns:
      int in [0, 100]
      or {"quit": True}
    """
    t0 = pygame.time.get_ticks()

    question = str(item["question"])

    value = int(clamp(int(initial_value), 0, 100))
    dragging = False
    slider_moved = False

    # Optional custom anchors
    anchors = item.get("anchors", None)
    if anchors is None:
        anchors = []

    # --- Layout ---
    content_w = SCREEN_WIDTH - ui(240)
    content_x = ui(120)

    cx = SCREEN_WIDTH // 2

    # Slider geometry
    track_w = min(ui(760), content_w)
    track_h = max(2, ui(8))
    knob_r  = max(6, ui(12))

    track_x = cx - track_w // 2
    track_y = SCREEN_HEIGHT // 2

    track_rect = pygame.Rect(track_x, track_y, track_w, track_h)
    
    # Smaller font for anchor labels
    script_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(script_dir, "fonts", "Roboto-Light.ttf")
    anchor_font = pygame.font.Font(font_path, max(10, ui(18)))

    # Continue button
    btn_w = ui(220)
    btn_h = ui(64)
    btn_rect = pygame.Rect(cx - btn_w // 2, track_y + ui(220), btn_w, btn_h)

    # Question text area above slider
    q_rect = pygame.Rect(content_x, track_y - ui(220), content_w, ui(180))

    def value_to_x(v):
        v = clamp(float(v), 0.0, 100.0)
        return track_x + int(round((v / 100.0) * track_w))

    def x_to_value(mx):
        frac = (mx - track_x) / float(track_w)
        frac = clamp(frac, 0.0, 1.0)
        return int(round(frac * 100.0))

    while True:
        clock.tick(FPS)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pass

            if ev.type == pygame.KEYDOWN:
                if is_hard_quit_event(ev):
                    return {"quit": True}

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                elapsed = pygame.time.get_ticks() - t0

                # Continue button
                if btn_rect.collidepoint(mx, my) and slider_moved and elapsed >= min_show_ms:
                    return int(value)

                # Click on/near track starts dragging
                hit = track_rect.inflate(0, ui(40))
                if hit.collidepoint(mx, my):
                    value = x_to_value(mx)
                    dragging = True
                    slider_moved = True

            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                dragging = False

            if ev.type == pygame.MOUSEMOTION and dragging:
                mx, _ = ev.pos
                value = x_to_value(mx)
                slider_moved = True

        # --- Draw ---
        screen.fill(BG_COLOR)

        # Wrapped question, centered above slider
        max_w = q_rect.width
        q_lines = wrap_text_lines(font_body, question, max_w)
        line_h = font_body.get_linesize()
        line_spacing = int(line_h * 1.35)

        total_q_h = len([ln for ln in q_lines if ln != ""]) * line_spacing
        y = q_rect.y + max(0, (q_rect.height - total_q_h) // 2)

        for line in q_lines:
            if line == "":
                y += line_spacing
                continue
            draw_instruction_line(screen, font_body, line, y)
            y += line_spacing

        # Current value above slider
        val_txt = f"{value}%"
        val_img = font_title.render(val_txt, True, TEXT_COLOR)
        screen.blit(val_img, (cx - val_img.get_width() // 2, track_y - ui(70)))

        # Track
        pygame.draw.rect(
            screen,
            (170, 170, 170),
            track_rect,
            border_radius=max(1, ui(6))
        )

        # Fill up to knob
        fill_w = value_to_x(value) - track_x
        if fill_w > 0:
            fill_rect = pygame.Rect(track_x, track_y, fill_w, track_h)
            pygame.draw.rect(
                screen,
                TEXT_COLOR,
                fill_rect,
                border_radius=max(1, ui(6))
            )

        # Knob
        knob_x = value_to_x(value)
        knob_y = track_y + track_h // 2
        pygame.draw.circle(screen, TEXT_COLOR, (knob_x, knob_y), knob_r)

        # Optional anchor ticks + labels below slider
        if anchors:
            tick_top = track_y - ui(10)
            tick_bot = track_y + track_h + ui(10)
            labels_y = track_y + ui(28)

            for anchor_value, anchor_text in anchors:
                tx = value_to_x(anchor_value)

                pygame.draw.line(
                    screen,
                    TEXT_COLOR,
                    (tx, tick_top),
                    (tx, tick_bot),
                    max(1, ui(2))
                )

                label_surf = anchor_font.render(str(anchor_text), True, TEXT_COLOR)
                label_rect = label_surf.get_rect(midtop=(tx, labels_y))

                # Keep labels on screen
                if label_rect.left < content_x:
                    label_rect.left = content_x
                if label_rect.right > content_x + content_w:
                    label_rect.right = content_x + content_w

                screen.blit(label_surf, label_rect)

            hint_y = track_y + ui(95)
        else:
            # Hint line between slider and button
            hint_y = track_y + ui(38)

        hint = "Drag the slider to respond"
        draw_text(screen, font_body, hint, TEXT_COLOR, (cx, hint_y))

        # Continue button
        elapsed = pygame.time.get_ticks() - t0
        enabled = slider_moved and elapsed >= min_show_ms

        if enabled:
            pygame.draw.rect(screen, (50, 50, 50), btn_rect, 0, border_radius=ui(8))
            pygame.draw.rect(screen, TEXT_COLOR, btn_rect, max(1, ui(3)), border_radius=ui(8))
            label_col = TEXT_COLOR
        else:
            pygame.draw.rect(screen, (35, 35, 35), btn_rect, 0, border_radius=ui(8))
            pygame.draw.rect(screen, (110, 110, 110), btn_rect, max(1, ui(2)), border_radius=ui(8))
            label_col = (140, 140, 140)

        draw_text(screen, font_body, "Continue", label_col, btn_rect.center)

        pygame.display.flip()

def run_postblock_slider_questions(screen, clock, font, block_name: str, title_font=None):
    """
    Run the block-specific post-block slider questions.
    Returns list of dicts, or {"quit": True}.
    """
    if title_font is None:
        title_font = font

    if not ENABLE_POSTBLOCK_SLIDERS:
        return []

    items = get_postblock_slider_items(block_name)
    if not items:
        return []

    responses = []

    for idx, item in enumerate(items, start=1):
        resp = run_slider_question(
            screen,
            clock,
            title_font,
            font,
            item,
            initial_value=50,
            min_show_ms=250,
        )

        if isinstance(resp, dict) and resp.get("quit"):
            return {"quit": True}

        responses.append({
            "slider_idx": idx,
            "slider_key": str(item["key"]),
            "question": str(item["question"]),
            "response": int(resp),
            "scale_min": 0,
            "scale_max": 100,
        })

    return responses
  

def run_preblock_screen(screen, clock, font, block_name: str):
    """
    Show a simple pre-block screen:
      "<BLOCK> BLOCK"
      "Press any key to begin"
    """
    min_show_s = MIN_SCREEN_TIME_MS / 1000.0
    start_time = time.perf_counter()
    
    title = get_block_display_title(block_name)

    prompt = "Press any key to begin"

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button
            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}
                if (time.perf_counter() - start_time) >= min_show_s:
                    return {"quit": False}

        screen.fill(BG_COLOR)

        base_h = font.get_linesize()
        gap = int(base_h * 1.5)

        y0 = SCREEN_HEIGHT // 2 - gap // 2
        draw_text(screen, font, title,  TEXT_COLOR, (SCREEN_WIDTH // 2, y0))
        draw_text(screen, font, prompt, TEXT_COLOR, (SCREEN_WIDTH // 2, y0 + gap))

        pygame.display.flip()


def run_endblock_screen(screen, clock, font, block_name: str):
    """
    End-of-block screen:
      "<BLOCK DISPLAY TITLE> COMPLETE"
      "Press any key to continue"
    """
    min_show_s = MIN_SCREEN_TIME_MS / 1000.0
    start_time = time.perf_counter()

    header = f"{get_block_display_title(block_name)} COMPLETE"
    prompt = "Press any key to continue"

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button
            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}

                if (time.perf_counter() - start_time) >= min_show_s:
                    return {"quit": False}

        screen.fill(BG_COLOR)

        base_h = font.get_linesize()
        gap = int(base_h * 1.5)

        y0 = SCREEN_HEIGHT // 2 - gap // 2
        draw_text(screen, font, header, TEXT_COLOR, (SCREEN_WIDTH // 2, y0))
        draw_text(screen, font, prompt,  TEXT_COLOR, (SCREEN_WIDTH // 2, y0 + gap))

        pygame.display.flip()


def run_experiment_complete_screen(screen, clock, font, performance_score_pct: Optional[float] = None):
    """
    Final screen after the last block:
      "EXPERIMENT COMPLETE"
      "Performance score: X% correct"
      "Please alert the experimenter now"

    Only ESC exits here. Other keys are ignored.
    """
    min_show_s = MIN_SCREEN_TIME_MS / 1000.0
    start_time = time.perf_counter()

    title = "EXPERIMENT COMPLETE"
    prompt = "Please alert the experimenter now"

    if performance_score_pct is None:
        score_line = "Performance score: n/a"
    else:
        score_line = f"Performance score: {performance_score_pct:.1f}% correct"

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button

            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}

                if event.key == pygame.K_ESCAPE:
                    if (time.perf_counter() - start_time) >= min_show_s:
                        return {"quit": True}

        screen.fill(BG_COLOR)

        base_h = font.get_linesize()
        gap = int(base_h * 1.5)

        y0 = SCREEN_HEIGHT // 2 - gap
        draw_text(screen, font, title,      TEXT_COLOR, (SCREEN_WIDTH // 2, y0))
        draw_text(screen, font, score_line, TEXT_COLOR, (SCREEN_WIDTH // 2, y0 + gap))
        draw_text(screen, font, prompt,     TEXT_COLOR, (SCREEN_WIDTH // 2, y0 + 2 * gap))

        pygame.display.flip()



# ---------------- Inter-trial screen ------------------------------------

# TRIAL_FEEDBACK_ON = False   # existing
SHOW_INTERTRIAL_BLANK   = True   # blank "Press any key" screen when outcome is off

def run_intertrial_screen(screen, clock, font, feedback_font,
                          *,
                          outcome: Optional[str],
                          is_conflict: Optional[bool] = None) -> Dict[str, Any]:
    """
    Inter-trial screen with a single keypress to continue.

    If outcome is None -> blank screen with only:
        "Press any key to continue"

    If outcome is "correct"/"incorrect"/"too_slow" -> show the existing feedback text.
    """
    min_show_s = MIN_SCREEN_TIME_MS / 1000.0
    start_time = time.perf_counter()

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button
            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}

                if (time.perf_counter() - start_time) >= min_show_s:
                    return {"quit": False}

        screen.fill(BG_COLOR)

        # ---- Blank variant ----
        if outcome is None:
            draw_text(
                screen,
                font,
                "Press any key to continue",
                TEXT_COLOR,
                (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
            )
            pygame.display.flip()
            continue

        # ---- Outcome variant ----
        if outcome == "too_slow":
            msg = "TOO SLOW"
            msg_color = TOO_SLOW_COLOR
        elif outcome == "correct":
            msg = "CORRECT"
            msg_color = CORRECT_COLOR
        else:
            msg = "INCORRECT"
            msg_color = INCORRECT_COLOR

        prompt = "Press any key to continue"

        # Use font metrics so spacing scales naturally with your font sizes
        msg_h = feedback_font.get_linesize()
        prompt_h = font.get_linesize()
        gap = int(max(6, 0.6 * prompt_h))   # tuned; scales with UI

        # Center the two-line stack vertically
        total_h = msg_h + gap + prompt_h
        top_y = (SCREEN_HEIGHT - total_h) // 2

        # Large feedback word
        draw_text(
            screen,
            feedback_font,
            msg,
            msg_color,
            (SCREEN_WIDTH // 2, top_y + msg_h // 2),
        )

        # Smaller prompt underneath
        draw_text(
            screen,
            font,
            prompt,
            TEXT_COLOR,
            (SCREEN_WIDTH // 2, top_y + msg_h + gap + prompt_h // 2),
        )

        pygame.display.flip()


def run_pretrial_fixation(screen,
                          clock,
                          duration_ms: int = FIXATION_DURATION_MS):
    """
    Show a plain pre-trial fixation cross (no radar, no HUD).
    """
    duration_s = max(0, int(duration_ms)) / 1000.0
    start = time.perf_counter()

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button
            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}
                # ignore other keys

        if (time.perf_counter() - start) >= duration_s:
            break

        # ---- Plain background only ----
        screen.fill(BG_COLOR)

        draw_fixation_cross(
            screen,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
            size=FIX_SIZE,
            thickness=FIX_THICKNESS
        )

        pygame.display.flip()

    return {"quit": False}


def show_block_feedback(screen, clock, font, results: List[Dict[str, Any]], block_name: str):
    """
    Show end-of-block feedback:
      - Overall accuracy (% correct)
      - Mean RT (s)
      - If PM enabled: PM accuracy (% correct PM responses on PM targets)
      - If automation present: observed automation accuracy (% correct automation labels)
    """
    min_show_s = MIN_SCREEN_TIME_MS / 1000.0
    start_time = time.perf_counter()

    # ---------------- Overall accuracy ----------------
    # Count ALL trials as evaluable, and treat timeouts as incorrect.
    n_evaluable = len(results)
    n_correct = 0

    for r in results:
        c = r.get("correct", "")
        if c in (1, "1"):
            n_correct += 1
        # else: includes 0/""/None => incorrect (timeouts included)

    acc_pct = 100.0 * n_correct / n_evaluable if n_evaluable > 0 else 0.0
    
    # ---------------- Trials completed ----------------
    # Count trials that were actually responded to (exclude hard quits)
    n_completed = len(results)

    # ---------------- Mean RT ----------------
    rts = []
    for r in results:
        rt = r.get("rt", float("nan"))
        if isinstance(rt, (int, float)) and not math.isnan(rt):
            rts.append(rt)

    if rts:
        mean_rt = sum(rts) / len(rts)
        mean_rt_text = f"Mean RT: {mean_rt:5.3f} s"
    else:
        mean_rt_text = "Mean RT: n/a"

    # ---------------- PM accuracy (only if any PM targets occurred) ----------------
    pm_targets = 0
    pm_hits = 0

    for r in results:
        try:
            is_pm_int = int(r.get("is_PM", 0))
        except (TypeError, ValueError):
            continue

        if is_pm_int == 1:
            pm_targets += 1
            c = r.get("correct", "")
            if c in (0, 1, "0", "1") and int(c) == 1:
                pm_hits += 1

    pm_line = None
    if pm_targets > 0:
        pm_pct = 100.0 * pm_hits / pm_targets
        pm_line = f"PM accuracy: {pm_pct:5.1f}% ({pm_hits}/{pm_targets})"

    # ---------------- Automation accuracy (if present) ----------------
    def _parse_is_conflict(val) -> Optional[bool]:
        if val is None:
            return None
        s = str(val).strip().lower()
        if s == "":
            return None
        if s in ("1", "true", "t", "yes", "y"):
            return True
        if s in ("0", "false", "f", "no", "n"):
            return False
        return None

    def _parse_auto_label(val) -> Optional[str]:
        if val is None:
            return None
        s = str(val).strip().upper()
        if s == "":
            return None
        # accept a few variants
        if "NON" in s:   # NON-CONF, NONCONFLICT, etc.
            return "NON-CONF"
        if "CONF" in s:  # CONFLICT
            return "CONFLICT"
        return None

    auto_present = any(_parse_auto_label(r.get("automation", None)) is not None for r in results)

    auto_line = None
    if auto_present:
        n_auto = 0
        n_auto_correct = 0

        # optional breakdown
        # counts = {"TP":0, "TN":0, "FP":0, "FN":0}

        for r in results:
            true_is_conf = _parse_is_conflict(r.get("is_conflict", None))
            auto_lbl = _parse_auto_label(r.get("automation", None))
            if true_is_conf is None or auto_lbl is None:
                continue

            true_lbl = "CONFLICT" if true_is_conf else "NON-CONF"
            n_auto += 1
            if auto_lbl == true_lbl:
                n_auto_correct += 1

            # if auto_lbl == "CONFLICT" and true_lbl == "CONFLICT": counts["TP"] += 1
            # if auto_lbl == "NON-CONF" and true_lbl == "NON-CONF": counts["TN"] += 1
            # if auto_lbl == "CONFLICT" and true_lbl == "NON-CONF": counts["FP"] += 1
            # if auto_lbl == "NON-CONF" and true_lbl == "CONFLICT": counts["FN"] += 1

        if n_auto > 0:
            auto_pct = 100.0 * n_auto_correct / n_auto
            # auto_line = f"Automation accuracy: {auto_pct:5.1f}%"
            # auto_line = f"Automation accuracy: {auto_pct:5.1f}% ({n_auto_correct}/{n_auto}) | TP {counts['TP']} TN {counts['TN']} FP {counts['FP']} FN {counts['FN']}"
        else:
            auto_line = "Automation accuracy: n/a"

    # ---------------- Compose lines ----------------
    lines = [
        f"{get_block_display_title(block_name)} COMPLETE",
        # f"Trials completed: {n_completed}",
        # f"Your accuracy: {acc_pct:5.1f}%",
        # mean_rt_text,
    ]

    if pm_line is not None:
        lines.append(pm_line)

    if auto_line is not None:
        lines.append(auto_line)

    lines.append("Press any key to continue")

    # ---------------- Render screen ----------------
    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button
            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return
                if (time.perf_counter() - start_time) >= min_show_s:
                    return

        screen.fill(BG_COLOR)

        base_height  = font.get_linesize()
        line_spacing = int(base_height * 1.5)
        start_y      = SCREEN_HEIGHT // 2 - line_spacing

        for i, text in enumerate(lines):
            y = start_y + i * line_spacing
            draw_text(screen, font, text, TEXT_COLOR, (SCREEN_WIDTH // 2, y))

        pygame.display.flip()



# --------------------------- Trial execution -----------------------------

def run_trial(screen, clock, font, info_font, feedback_font, 
              trial: TrialSpec, trial_idx: int, total_trials: int,
              has_pm_design: bool, drt_enabled: bool,
              aid_label_font=None, aid_font=None,
              intertrial_every: int = INTERTRIAL_QUESTION_EVERY,
              intertrial_item: Dict[str, str] = INTERTRIAL_QUESTION_ITEM,
              run_ts: Optional[str] = None) -> Dict[str, Any]:
    """
    Runs a single trial and returns a result dict.

    BEHAVIOUR:
      - If trial.auto_delay < 0 and trial.automation is not None:
          * Show the automation banner TOP-CENTRE ONLY for abs(auto_delay) seconds
            BEFORE aircraft stimulus onset.
          * RT is always measured from aircraft stimulus onset (not from the pre-cue).
          * During stimulus, automation banner is shown immediately (auto_delay treated as 0.0).
            (If you want it to disappear once stimulus begins, set auto_delay = float("inf") below.)
      - If trial.auto_delay >= 0: unchanged (banner appears after that many seconds from stimulus onset).
    """
    if aid_label_font is None:
        aid_label_font = info_font
    if aid_font is None:
        aid_font = font
        
    # Copy start positions into mutable variables
    x1 = trial.pos1_start_x
    y1 = trial.pos1_start_y
    x2 = trial.pos2_start_x
    y2 = trial.pos2_start_y

    vel1_x, vel1_y = trial.vel1_x, trial.vel1_y
    vel2_x, vel2_y = trial.vel2_x, trial.vel2_y

    fl1 = int(trial.ac1_fl)
    fl2 = int(trial.ac2_fl)
    sp1 = trial.ac1_speed
    sp2 = trial.ac2_speed

    speed_label1 = f"{fl1}>{fl1} {sp1:.0f}"
    speed_label2 = f"{fl2}>{fl2} {sp2:.0f}"

    auto_delay = trial.auto_delay if trial.auto_delay is not None else 0.0

    context_id = trial.context_id
    if context_id == 1:
        border_color = (255, 0, 0)
    elif context_id == 2:
        border_color = (0, 0, 255)
    else:
        border_color = None

    cx = SCREEN_WIDTH / 2
    cy = SCREEN_HEIGHT / 2

    # ---------------- PRE-TRIAL FIXATION ----------------
    if FIXATION_ON and FIXATION_DURATION_MS > 0:
        fx = run_pretrial_fixation(
            screen,
            clock,
            duration_ms=FIXATION_DURATION_MS
        )
        if isinstance(fx, dict) and fx.get("quit"):
            return {"quit": True}

    # ---------------- PRE-STIM AUTOMATION (negative delay) ----------------
    # If auto_delay < 0: show the top-centre banner BEFORE stimulus for abs(auto_delay) seconds.
    if AUTOMATION_ON and (trial.automation is not None) and (auto_delay < 0.0):
        pre_dur = -auto_delay
        pre_start = time.perf_counter()

        while True:
            clock.tick(FPS)
            now = time.perf_counter()
            pre_elapsed = now - pre_start
            if pre_elapsed >= pre_dur:
                break

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pass  # ignore window close button
                if event.type == pygame.KEYDOWN:
                    if is_hard_quit_event(event):
                        return {"quit": True}
                    # Ignore all task responses during pre-cue

            # draw blank radar scaffold (no aircraft)
            draw_blank_radar(screen, trial, cx, cy, border_color=border_color)

            # TOP-CENTRE automation banner
            draw_aid_banner_top_center(
                screen,
                small_font=aid_label_font,
                big_font=aid_font,
                label=str(trial.automation),
                y=ui(20)
            )

            pygame.display.flip()

        # Stimulus onset is NOW; reset RT clock origin
        start_time = time.perf_counter()

        # After pre-cue, show automation immediately during stimulus (explicit)
        auto_delay = 0.0

        # If you instead want it to DISAPPEAR during stimulus, use:
        # auto_delay = float("inf")

    else:
        # Normal case: stimulus onset is now
        start_time = time.perf_counter()

    # ---------------- Trial state ----------------
    responded = False
    response = None  # "conflict" | "nonconflict" | "pm" | None
    rt = None

    running_trial = True

    # ---- Flash scheduler ----
    flashes: List[Dict[str, Any]] = []

    if drt_enabled:
        next_flash_time = sample_drt_flash_interval()
        flash_on = False
        flash_off_time = 0.0
    else:
        next_flash_time = None
        flash_on = False
        flash_off_time = None

    # ---------------- Stimulus loop ----------------
    while running_trial:
        dt_ms = clock.tick(FPS)
        dt = dt_ms / 1000.0
        now_time = time.perf_counter()
        elapsed = now_time - start_time

        # ----- Handle flash scheduling -------------
        if drt_enabled:
            if (not flash_on) and (elapsed >= next_flash_time):
                if flashes:
                    flashes[-1]["window_end"] = elapsed

                flash_on = True
                flash_off_time = elapsed + FLASH_DURATION

                flashes.append({
                    "onset": elapsed,
                    "rt": float("nan"),
                    "responded": False,
                    "key": None,
                    "window_end": None,
                })

            if flash_on and elapsed >= flash_off_time:
                flash_on = False
                next_flash_time = elapsed + sample_drt_flash_interval()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pass  # ignore window close button
            if event.type == pygame.KEYDOWN:
                if is_hard_quit_event(event):
                    return {"quit": True}

                # Flash response key (DRT)
                if drt_enabled and event.key == FLASH_KEY:
                    if flashes:
                        for f in reversed(flashes):
                            onset = f["onset"]
                            window_end = f.get("window_end", None)
                            if elapsed >= onset and (window_end is None or elapsed < window_end):
                                if not f["responded"]:
                                    f["rt"] = elapsed - onset
                                    f["responded"] = True
                                    f["key"] = event.key
                                break
                    continue

                # Main task response (RT is from stimulus onset)
                if not responded:
                    if has_pm_design and event.key in (pygame.K_9, pygame.K_KP9):
                        response = "pm"
                        responded = True
                        rt = elapsed
                    elif event.key == KEY_CONFLICT:
                        response = "conflict"
                        responded = True
                        rt = elapsed
                    elif event.key == KEY_NONCONFLICT:
                        response = "nonconflict"
                        responded = True
                        rt = elapsed

        # Update positions
        x1 += vel1_x * dt
        y1 += vel1_y * dt
        x2 += vel2_x * dt
        y2 += vel2_y * dt

        screen.fill(BG_COLOR)

        big_radius = SCREEN_HEIGHT // 2
        pygame.draw.circle(
            screen,
            BG_CIRCLE_COLOR,
            (int(cx), int(cy)),
            big_radius,
            0,
        )

        pygame.draw.line(
            screen,
            ROUTE_COLOR,
            (int(trial.route1_start_x), int(trial.route1_start_y)),
            (int(trial.route1_end_x),   int(trial.route1_end_y)),
            1,
        )

        pygame.draw.line(
            screen,
            ROUTE_COLOR,
            (int(trial.route2_start_x), int(trial.route2_start_y)),
            (int(trial.route2_end_x),   int(trial.route2_end_y)),
            1,
        )

        if border_color is not None:
            pygame.draw.rect(
                screen,
                border_color,
                screen.get_rect(),
                8
            )

        if drt_enabled and flash_on:
            pygame.draw.circle(
                screen,
                FLASH_COLOR,
                (int(cx), int(cy)),
                big_radius,
                12
            )

        guide_x = int(GUIDE_MARGIN + trial.guide_min_sep)
        guide_y = SCREEN_HEIGHT // 2
        draw_guide_cross(screen, guide_x, guide_y, trial.guide_min_sep)

        if SHOW_DOMS_OVERLAY:
            draw_doms_marker_and_label(
                screen,
                info_font,
                trial=trial,
                guide_x=guide_x,
                guide_y=guide_y,
                guide_min_sep=trial.guide_min_sep,
                doms_px=trial.min_sep,
                doms_nm=trial.doms_nm,
                color=TEXT_COLOR,
                line_color=(255, 255, 255),
            )

        pygame.draw.circle(
            screen,
            AC1_CIRCLE_COLOR,
            (int(x1), int(y1)),
            CIRCLE_RADIUS,
            ui(1),
        )
        pygame.draw.circle(
            screen,
            AC2_CIRCLE_COLOR,
            (int(x2), int(y2)),
            CIRCLE_RADIUS,
            ui(1),
        )

        future_dt = 60.0
        f1_x = x1 + vel1_x * future_dt
        f1_y = y1 + vel1_y * future_dt
        f2_x = x2 + vel2_x * future_dt
        f2_y = y2 + vel2_y * future_dt

        pygame.draw.line(
            screen,
            AC1_CIRCLE_COLOR,
            (int(x1), int(y1)),
            (int(f1_x), int(f1_y)),
            ui(1),
        )
        pygame.draw.line(
            screen,
            AC2_CIRCLE_COLOR,
            (int(x2), int(y2)),
            (int(f2_x), int(f2_y)),
            ui(1),
        )

        tip_radius = ui(2)
        pygame.draw.circle(
            screen,
            (255, 255, 255),
            (int(f1_x), int(f1_y)),
            tip_radius,
            0,
        )
        pygame.draw.circle(
            screen,
            (255, 255, 255),
            (int(f2_x), int(f2_y)),
            tip_radius,
            0,
        )

        # Info boxes + connectors
        box_offset = ui(80)
        diag = box_offset / math.sqrt(2.0)

        box1_tl = (x1 + diag, y1 - diag)
        box2_tl = (x2 + diag, y2 - diag)

        auto_label1 = None
        auto_label2 = None
        if AUTOMATION_ON and AUTOMATION_IN_INFOBOX and (trial.automation is not None) and (elapsed >= auto_delay):
            auto_label1 = str(trial.automation)
            auto_label2 = str(trial.automation)

        box1_rect = draw_info_box(
            screen,
            info_font,
            trial.callsign1,
            speed_label1,
            box1_tl,
            auto_text=auto_label1,
            fg=INFOBOX_COLOR,
        )

        box2_rect = draw_info_box(
            screen,
            info_font,
            trial.callsign2,
            speed_label2,
            box2_tl,
            auto_text=auto_label2,
            fg=INFOBOX_COLOR,
        )

        def draw_middle_connector(color, circle_pos, box_rect):
            x0, y0 = circle_pos
            x1c, y1c = box_rect.topleft   # anchor to top-left corner of the info box

            vx = x1c - x0
            vy = y1c - y0
            dist = math.hypot(vx, vy)

            if dist <= 1e-6:
                return

            ux = vx / dist
            uy = vy / dist

            # scaled padding away from the aircraft circle and box corner
            start_pad = ui(16)
            end_pad   = ui(16)

            start_x = x0 + ux * start_pad
            start_y = y0 + uy * start_pad
            end_x   = x1c - ux * end_pad
            end_y   = y1c - uy * end_pad

            pygame.draw.line(
                screen,
                color,
                (int(start_x), int(start_y)),
                (int(end_x), int(end_y)),
                max(1, ui(1)),
            )
    
        circle1_pos = (x1, y1)
        circle2_pos = (x2, y2)

        draw_middle_connector(AC1_CIRCLE_COLOR, circle1_pos, box1_rect)
        draw_middle_connector(AC2_CIRCLE_COLOR, circle2_pos, box2_rect)

        # --- Aid banner (top-centre) ---
        if AUTOMATION_ON and (trial.automation is not None) and (elapsed >= auto_delay):
            # Normal AUTOMATION blocks (unchanged)
            draw_aid_banner_top_center(
                screen,
                small_font=aid_label_font,
                big_font=aid_font,
                label=str(trial.automation),
                y=ui(20)
            )

        elif MASKED_AID_BANNER_ON:
            # MANUAL masked banner (drawing-only; does not touch trial.automation)
            draw_aid_banner_top_center(
                screen,
                small_font=aid_label_font,
                big_font=aid_font,
                label=str(MASKED_AID_BANNER_TEXT),
                y=ui(MASKED_AID_BANNER_Y)
            )

        # Progress counter
        corner_pad = ui(16)
        header_text = f"Trial {trial_idx + 1}/{total_trials}"
        header_surf = font.render(header_text, True, TEXT_COLOR)
        header_rect = header_surf.get_rect()
        header_rect.topright = (SCREEN_WIDTH - corner_pad, corner_pad)
        screen.blit(header_surf, header_rect)

        # Countdown timer
        remaining = max(0.0, trial.deadline - elapsed)
        timer_text = f"{remaining:4.1f}s"
        timer_surf = font.render(timer_text, True, TEXT_COLOR)
        timer_rect = timer_surf.get_rect()
        timer_rect.topleft = (corner_pad, corner_pad)
        screen.blit(timer_surf, timer_rect)

        pygame.display.flip()

        if responded or elapsed >= trial.deadline:
            running_trial = False

    # ----------------- Compute outcome & feedback -------------------------

    if response is None:
        response = "TIMEOUT"
        outcome = "too_slow"
        correct = None
    else:
        if has_pm_design and trial.is_PM is not None:
            if trial.is_PM:
                correct = (response == "pm")
            else:
                if response == "pm":
                    correct = False
                else:
                    if trial.is_conflict and response == "conflict":
                        correct = True
                    elif (not trial.is_conflict) and response == "nonconflict":
                        correct = True
                    else:
                        correct = False
        else:
            if trial.is_conflict and response == "conflict":
                correct = True
            elif (not trial.is_conflict) and response == "nonconflict":
                correct = True
            else:
                correct = False

        outcome = "correct" if correct else "incorrect"

    # Feedback column (only when post-trial feedback is enabled)
    feedback_text = ""
    if TRIAL_FEEDBACK_ON:
        if outcome == "too_slow":
            feedback_text = "TOO SLOW"
        elif outcome == "correct":
            feedback_text = "CORRECT"
        else:
            feedback_text = "INCORRECT"
            
    # ---------------- Inter-trial outcome / blank screen ------------------

    if TRIAL_FEEDBACK_ON:
        it = run_intertrial_screen(
            screen, clock, font, feedback_font,
            outcome=outcome,
            is_conflict=bool(trial.is_conflict),
        )
        if isinstance(it, dict) and it.get("quit"):
            return {"quit": True}

    elif SHOW_INTERTRIAL_BLANK:
        it = run_intertrial_screen(
            screen, clock, font, feedback_font,
            outcome=None,
            is_conflict=None,
        )
        if isinstance(it, dict) and it.get("quit"):
            return {"quit": True}


    # --------- Optional inter-trial question ---------------
    
    intertrial_shown = False
    intertrial_resp  = None
    
    if intertrial_every > 0:
        if ((trial_idx + 1) % intertrial_every) == 0:
            resp = run_likert_question(
                screen,
                clock,
                font,
                intertrial_item,
                scale_min=QUESTION_SCALE_MIN,
                scale_max=QUESTION_SCALE_MAX,
                label_font=font,
                title_font=font,
            )

            if isinstance(resp, dict) and resp.get("quit"):
                return {"quit": True}

            intertrial_shown = True
            intertrial_resp  = int(resp)

            waiting = True
            while waiting:
                clock.tick(FPS)

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pass  # ignore window close button
                    if event.type == pygame.KEYDOWN:
                        if is_hard_quit_event(event):
                            return {"quit": True}
                        waiting = False

                screen.fill(BG_COLOR)
                draw_text(
                    screen,
                    font,
                    "Press any key to continue",
                    TEXT_COLOR,
                    (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
                )
                pygame.display.flip()

    # ---- Summarise flash data for this trial -----------------------------
    if drt_enabled and flashes:
        flash_onsets = ";".join(f"{f['onset']:.3f}" for f in flashes)
        flash_rts = ";".join(
            ("NA" if (not f["responded"] or math.isnan(f["rt"]))
             else f"{f['rt']:.3f}")
            for f in flashes
        )
    else:
        flash_onsets = ""
        flash_rts = ""

    result: Dict[str, Any] = {
        "run_timestamp": run_ts,
        "trial_idx": trial_idx + 1,
        "stimulus": trial.conflict_status,
        "is_conflict": int(trial.is_conflict),
        "response": response if response is not None else "",
        "rt_s": "" if rt is None else rt,
        "rt_ms": round(rt * 1000, 2) if rt is not None else "",
        "correct": "" if correct is None else int(correct),
        "outcome": outcome,
        "feedback": feedback_text,
        "deadline_s": trial.deadline,
        "doms_thresh_px": trial.guide_min_sep,
        "doms_px": trial.min_sep,
        "doms_thresh_nm": DOMS_THRESHOLD_NM,
        "DOMS": trial.doms_nm,
        "TTMS": trial.ttms,
        "angle_deg": trial.angle,
        "theta1_deg": round(math.degrees(trial.theta1), 3) if trial.theta1 is not None else "",
        "theta2_deg": round(math.degrees(trial.theta2), 3) if trial.theta2 is not None else "",
        "OOP": trial.OOP,
        "TCOP1": trial.TCOP1,
        "TCOP2": trial.TCOP2,
        "ac1_speed": trial.ac1_speed,
        "ac2_speed": trial.ac2_speed,
        "callsign1": trial.callsign1,
        "callsign2": trial.callsign2,
        "aid_onset_s": trial.auto_delay if trial.auto_delay is not None else 0.0,
        "aid_onset_ms": round(auto_delay * 1000, 0) if auto_delay is not None else "",
        "flash_onsets": flash_onsets,
        "flash_rts": flash_rts,
        "intertrial_q_shown": int(intertrial_shown),
        "intertrial_q_resp": "" if intertrial_resp is None else intertrial_resp,
        "stair_update_idx": "" if trial.stair_update_idx is None else int(trial.stair_update_idx),
    }

    # Staircase diagnostics (if present)
    if getattr(trial, "stair_gap_nm", None) is not None:
        result["stair_gap_nm"] = float(trial.stair_gap_nm)
    if getattr(trial, "stair_step_nm", None) is not None:
        result["stair_step_nm"] = float(trial.stair_step_nm)
    # Per-class mean params used to generate DOMS
    if getattr(trial, "doms_mu_low", None) is not None:
        result["doms_mu_low"] = float(trial.doms_mu_low)
    if getattr(trial, "doms_mu_high", None) is not None:
        result["doms_mu_high"] = float(trial.doms_mu_high)
    # Per-class SD params used to generate DOMS
    if getattr(trial, "doms_sd_low", None) is not None:
        result["doms_sd_low"] = float(trial.doms_sd_low)
    if getattr(trial, "doms_sd_high", None) is not None:
        result["doms_sd_high"] = float(trial.doms_sd_high)
    # SD actually used this trial
    if getattr(trial, "doms_sd", None) is not None:
        result["doms_sd"] = float(trial.doms_sd)

    # PM
    if has_pm_design:
        if trial.is_PM is not None:
            result["is_PM"] = int(trial.is_PM)
        if trial.pm_prop is not None:
            result["PM_prop"] = trial.pm_prop
    
    # Automation
    if trial.automation is not None:
        result["automation"] = trial.automation
    if trial.automation is not None:
        result["aid_label"] = trial.automation
    if trial.auto_fail is not None:
        result["aid_correct"] = 1 - int(trial.auto_fail)
    if trial.auto_fail is not None:
        result["auto_fail"] = int(trial.auto_fail)
    if trial.automation is not None:
        result["aid_accuracy_setting"] = AUTOMATION_ACC
    if trial.automation is not None:
        # record the nominal failure probability of the aid
        result["auto_fail_prop"] = (
            float(trial.auto_fail_prop)
            if trial.auto_fail_prop is not None
            else (1.0 - float(AUTOMATION_ACC))
        )
    
    # Context
    if trial.context_id is not None:
        result["context_id"] = int(trial.context_id)

    if trial_idx == 0:
        print("Result keys for first trial:", list(result.keys()))

    # --- Formatting / rounding for CSV cleanliness ---
    result["auto_fail_prop"] = _round_or_blank(result.get("auto_fail_prop", ""), 3)

    # staircase + bounds: 3–4 dp is plenty
    for k in (
        "stair_gap_nm", "stair_step_nm",
        "doms_mu_low", "doms_mu_high",
        "doms_sd_low", "doms_sd_high",
        "doms_sd",
    ):
        if k in result:
            result[k] = _round_or_blank(result.get(k, ""), 5)

    return result


# ------------------------------ App class --------------------------------

class ATCLabApp:
    """
    Wrapper class to hold Pygame state and the high-level flow:
    instructions -> trials -> feedback -> questionnaires -> save.
    """
    def __init__(self, has_pm_design: bool, args: argparse.Namespace, drt_enabled: bool, fullscreen: bool = False):
        self.run_ts = time.strftime("%Y%m%d_%H%M%S")
        self.has_pm_design = has_pm_design
        self.args = args
        self.drt_enabled = drt_enabled
        self.staircase = DomGapStaircase(on=STAIRCASE_ON, target_acc=TARGET_ACC)
        self.reset_staircase(on=STAIRCASE_ON, target_acc=TARGET_ACC)
        self.doms_stats: Dict[str, Any] = {}
        self.calib_doms_params: Optional[Dict[str, float]] = None
        self.key_conflict_label: str = ""
        self.key_nonconf_label: str = ""
        self.key_pm_label: str = ""
        self.postblock_slider_responses: List[Dict[str, Any]] = []
        self.all_postblock_slider_responses: List[Dict[str, Any]] = []

        # pygame.init() already called in main(), but calling again is harmless
        pygame.display.set_caption("ATC Lab")

        if fullscreen:
            flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
            # IMPORTANT on macOS: (0,0) lets SDL choose the true fullscreen backbuffer size
            self.screen = pygame.display.set_mode((0, 0), flags, vsync=1)

            # Now that the display exists, recompute UI scaling from the REAL surface size
            configure_scaling_from_surface(self.screen)

            print(f"[DISPLAY] {SCREEN_WIDTH}x{SCREEN_HEIGHT} UI_SCALE={UI_SCALE:.3f} GEOM_SCALE={GEOM_SCALE:.3f}")
        else:
            flags = pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags, vsync=1)
            
        self.clock = pygame.time.Clock()

        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(script_dir, "fonts", "Roboto-Light.ttf")

        self.font = pygame.font.Font(font_path, max(14, ui(24)))
        self.font_bold = pygame.font.Font(font_path, max(14, ui(24)))
        self.font_bold.set_bold(True)
        self.aid_label_font = pygame.font.Font(font_path, max(12, ui(20)))
        self.aid_font = pygame.font.Font(font_path, max(18, ui(32)))
        self.aid_font.set_bold(True)

        self.info_font = pygame.font.Font(font_path, max(10, ui(16)))
        self.title_font = pygame.font.Font(font_path, max(18, ui(36)))
        self.feedback_font = pygame.font.Font(font_path, max(18, ui(36)))
        self.feedback_font.set_bold(False)
        self.label_font = pygame.font.Font(font_path, max(10, ui(20)))  

        # participant id (set in run() before instructions)
        self.participant_id: Optional[int] = None
        self.participant_tag: str = "pXXX"

        self.results: List[Dict[str, Any]] = []
        self.all_results: List[Dict[str, Any]] = []
        self.postblock_responses: List[Dict[str, Any]] = []
        self.all_postblock_responses: List[Dict[str, Any]] = []

        # optional uniqueness
        self.used_callsigns = set()

    def base_with_participant(self) -> str:
        base = make_base_name(self.args, self.run_ts)
        return f"{self.participant_tag}_{base}"

    def reset_staircase(self, *, on: bool, target_acc: float):
        # preserve starting params from globals
        self.staircase = DomGapStaircase(
            on=bool(on),
            target_acc=float(target_acc),
        )

    def compute_doms_summary(
        self,
        exclude_first_trials: int = STAIRCASE_BURNIN,
        summary_last_n: Optional[int] = CALIB_SUMMARY_LAST_N
    ) -> Dict[str, Any]:
        """
        Compute realised DOMS mean/sd separately for conflict vs non-conflict.

        Rules:
          - exclude PM trials
          - exclude the first `exclude_first_trials` burn-in trials of THIS BLOCK
          - from the remaining eligible trials, optionally keep only the last
            `summary_last_n` trials (across both classes combined)
        """
        def _is_pm_row(r: Dict[str, Any]) -> bool:
            try:
                return int(r.get("is_PM", 0)) == 1
            except Exception:
                return False

        def _get_trial(r: Dict[str, Any]) -> Optional[int]:
            v = r.get("trial_idx", "")
            if v in ("", None):
                return None
            try:
                return int(v)  # 1-based
            except Exception:
                return None

        def _get_doms(r: Dict[str, Any]) -> Optional[float]:
            v = r.get("DOMS", None)
            if v is None or v == "":
                return None
            try:
                x = float(v)
                if math.isnan(x):
                    return None
                return x
            except Exception:
                return None

        def _get_is_conflict(r: Dict[str, Any]) -> Optional[bool]:
            try:
                return int(r.get("is_conflict", 0)) == 1
            except Exception:
                return None

        # ---------- collect eligible trials first ----------
        eligible_rows = []

        for r in self.results:
            if _is_pm_row(r):
                continue

            ti = _get_trial(r)
            if ti is None:
                continue
            if ti <= int(exclude_first_trials):
                continue

            doms = _get_doms(r)
            if doms is None:
                continue

            is_conf = _get_is_conflict(r)
            if is_conf is None:
                continue

            eligible_rows.append({
                "trial_idx": ti,
                "DOMS": doms,
                "is_conflict": is_conf,
            })

        # keep chronological order, then take last N if requested
        eligible_rows.sort(key=lambda x: x["trial_idx"])

        last_n_setting = None if summary_last_n is None else int(summary_last_n)
        if last_n_setting is not None and last_n_setting > 0:
            eligible_rows = eligible_rows[-last_n_setting:]

        n_trials_summarised = len(eligible_rows)

        xs_conf = [r["DOMS"] for r in eligible_rows if r["is_conflict"]]
        xs_non  = [r["DOMS"] for r in eligible_rows if not r["is_conflict"]]
        xs_abs  = [abs(r["DOMS"] - DOMS_THRESHOLD_NM) for r in eligible_rows]

        def _mean_sd(xs: List[float]) -> tuple[float, float, int]:
            n = len(xs)
            if n == 0:
                return (float("nan"), float("nan"), 0)
            m = sum(xs) / n
            if n < 2:
                return (m, float("nan"), n)
            var = sum((x - m) ** 2 for x in xs) / (n - 1)
            return (m, math.sqrt(var), n)

        _, _, n_c = _mean_sd(xs_conf)
        _, _, n_n = _mean_sd(xs_non)

        mean_absdiff, sd_absdiff, n_abs = _mean_sd(xs_abs)

        mean_conflict = float("nan")
        mean_nonconflict = float("nan")

        if n_abs > 0 and not math.isnan(mean_absdiff):
            mean_conflict = DOMS_THRESHOLD_NM - mean_absdiff
            mean_nonconflict = DOMS_THRESHOLD_NM + mean_absdiff

        return {
            "exclude_first_trials": int(exclude_first_trials),
            "summary_last_n_setting": "" if last_n_setting is None else int(last_n_setting),
            "n_trials_summarised": int(n_trials_summarised),

            # keep class counts for diagnostics / sanity checks
            "n_conflict": int(n_c),
            "n_nonconflict": int(n_n),

            # symmetric calibration summary
            "mean_absdiff": mean_absdiff,
            "sd_absdiff": sd_absdiff,

            "mean_conflict": mean_conflict,
            "sd_conflict": sd_absdiff,
            "mean_nonconflict": mean_nonconflict,
            "sd_nonconflict": sd_absdiff,
        }

    def save_doms_summary_csv(self, *, block_order: int, block_name: str) -> Optional[str]:
        if not getattr(self, "doms_stats", None):
            return None

        os.makedirs(RESULTS_DIR, exist_ok=True)

        base = self.base_with_participant()
        tag = block_tag(block_order)
        bname = str(block_name).upper()

        out_path = os.path.join(RESULTS_DIR, f"results_{base}_{tag}_{bname}_DOMS_SUMMARY.csv")

        fieldnames = [
            "participant_id",
            "exclude_first_trials",
            "summary_last_n_setting",
            "n_trials_summarised",
            "n_conflict",
            "n_nonconflict",
            "mean_absdiff",
            "sd_absdiff",
            "mean_conflict",
            "sd_conflict",
            "mean_nonconflict",
            "sd_nonconflict",
        ]

        row = dict(self.doms_stats)
        row["participant_id"] = "" if self.participant_id is None else int(self.participant_id)

        for k in (
            "mean_absdiff", "sd_absdiff",
            "mean_conflict", "sd_conflict",
            "mean_nonconflict", "sd_nonconflict"
        ):
            if k in row and isinstance(row[k], (int, float)) and not math.isnan(row[k]):
                row[k] = round(float(row[k]), 5)

        write_header = not os.path.exists(out_path)
        with open(out_path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                w.writeheader()
            w.writerow(row)

        print(f"DOMS summary saved to: {out_path}")
        return out_path

    def compute_final_performance_score(self) -> float:
        """
        Overall accuracy across MANUAL, AUTOMATION1, and AUTOMATION2 blocks only.
        Timeouts and missing responses count as incorrect.
        """
        score_blocks = {"MANUAL", "AUTOMATION1", "AUTOMATION2"}

        rows = [
            r for r in self.all_results
            if str(r.get("block", "")).strip().upper() in score_blocks
        ]

        n_total = len(rows)
        if n_total == 0:
            return 0.0

        n_correct = 0
        for r in rows:
            c = r.get("correct", "")
            if c in (1, "1"):
                n_correct += 1
            # everything else counts as incorrect, including timeout blanks

        return 100.0 * n_correct / n_total
  
    def show_instructions(self):

        conf_letter = pygame.key.name(KEY_CONFLICT).upper()
        nonconf_letter = pygame.key.name(KEY_NONCONFLICT).upper()

        key_line_1 = f"Press {conf_letter} if you think the aircraft will pass within 5nm (CONFLICT)"
        key_line_2 = f"Press {nonconf_letter} if you think the aircraft will not pass within 5nm (NON-CONFLICT)"

        if self.has_pm_design:
            instructions = [
                "As a reminder, on each trial you will see two aircraft moving on converging flight paths ",
                "toward a central crossing point. You’ll be shown a similar number of ",
                "conflict and non-conflict pairs. You must judge whether you think each ",
                "pair will conflict or not at any point during their flights.",

                "",

                key_line_1,
                key_line_2,

                "",

                "On some trials a special PROSPECTIVE MEMORY event will occur.",
                "On those trials press '9' instead of D/J",

                "",

                "Try to respond as quickly and accurately as possible",
            ]
        else:
            instructions = [
                "As a reminder, on each trial you will see two aircraft moving on converging flight paths ",
                "toward a central crossing point. You’ll be shown a similar number of ",
                "conflict and non-conflict pairs. You must judge whether you think each ",
                "pair will conflict or not at any point during their flights.",

                "",

                key_line_1,
                key_line_2,

                "",

                "Try to respond as quickly and accurately as possible",
            ]

        btn_w = ui(220)
        btn_h = ui(64)
        btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
        btn_rect.centerx = SCREEN_WIDTH // 2
        btn_rect.bottom = SCREEN_HEIGHT - ui(90)

        min_show_s = float(MIN_SCREEN_TIME_MS) / 1000.0
        start_time = time.perf_counter()

        showing_instructions = True

        while showing_instructions:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pass

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_rect.collidepoint(event.pos):
                        if (time.perf_counter() - start_time) >= min_show_s:
                            showing_instructions = False

                if event.type == pygame.KEYDOWN:
                    if is_hard_quit_event(event):
                        pygame.quit()
                        raise SystemExit

            self.screen.fill(BG_COLOR)

            draw_centered_instruction_screen(
                screen=self.screen,
                title_font=self.title_font,
                body_font=self.font,
                bold_font=self.font_bold,
                title="CONFLICT DETECTION TASK",
                lines=instructions
            )

            enabled = (time.perf_counter() - start_time) >= min_show_s

            if enabled:
                pygame.draw.rect(self.screen, (50, 50, 50), btn_rect, 0, border_radius=ui(8))
                pygame.draw.rect(self.screen, TEXT_COLOR, btn_rect, max(1, ui(3)), border_radius=ui(8))
                label_col = TEXT_COLOR
            else:
                pygame.draw.rect(self.screen, (35, 35, 35), btn_rect, 0, border_radius=ui(8))
                pygame.draw.rect(self.screen, (110, 110, 110), btn_rect, max(1, ui(2)), border_radius=ui(8))
                label_col = (140, 140, 140)

            draw_text(self.screen, self.font, "Continue", label_col, btn_rect.center)

            pygame.display.flip()

    def show_block_instructions(self, block_name: str):

        key = str(block_name).strip().upper()
        slides = BLOCK_INSTRUCTIONS.get(key, None)

        if not slides:
            return {"quit": False}

        # Backward compatibility
        if isinstance(slides, dict):
            slides = [slides]

        btn_w = ui(220)
        btn_h = ui(64)

        btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
        btn_rect.centerx = SCREEN_WIDTH // 2
        btn_rect.bottom = SCREEN_HEIGHT - ui(90)

        for slide in slides:

            title = str(slide.get("title", f"{key} BLOCK")).strip()
            body = str(slide.get("body", "")).strip()

            side_margin = ui(120)
            max_w = max(ui(600), SCREEN_WIDTH - 2 * side_margin)
            body_lines = wrap_text_lines(self.font, body, max_w)

            min_show_s = float(MIN_SCREEN_TIME_MS) / 1000.0
            start_time = time.perf_counter()

            showing = True
            while showing:
                self.clock.tick(FPS)

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pass

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if btn_rect.collidepoint(event.pos):
                            if (time.perf_counter() - start_time) >= min_show_s:
                                showing = False

                    if event.type == pygame.KEYDOWN:
                        if is_hard_quit_event(event):
                            return {"quit": True}

                self.screen.fill(BG_COLOR)

                draw_centered_instruction_screen(
                    screen=self.screen,
                    title_font=self.title_font,
                    body_font=self.font,
                    bold_font=self.font_bold,
                    title=title,
                    lines=body_lines
                )

                # Continue button in the same style as questionnaire screens
                enabled = (time.perf_counter() - start_time) >= min_show_s

                if enabled:
                    pygame.draw.rect(self.screen, (50, 50, 50), btn_rect, 0, border_radius=ui(8))
                    pygame.draw.rect(self.screen, TEXT_COLOR, btn_rect, max(1, ui(3)), border_radius=ui(8))
                    label_col = TEXT_COLOR
                else:
                    pygame.draw.rect(self.screen, (35, 35, 35), btn_rect, 0, border_radius=ui(8))
                    pygame.draw.rect(self.screen, (110, 110, 110), btn_rect, max(1, ui(2)), border_radius=ui(8))
                    label_col = (140, 140, 140)

                draw_text(self.screen, self.font, "Continue", label_col, btn_rect.center)

                pygame.display.flip()

        return {"quit": False}
  
    def run_trials(self, n_trials: int, block_name: str, block_idx: int):
        total_trials = n_trials

        # ------------------ DOMS generation parameters for THIS block ------------------
        # Defaults (used for TRAINING + CALIBRATION unless overrided elsewhere)
        mu_low_start  = 2.5   # conflict mean (<=5)
        mu_high_start = 7.5   # non-conflict mean (>=5)
        doms_sd       = 0.5   # fallback SD if per-class SD not provided
        doms_sd_low   = None  # conflict SD (optional)
        doms_sd_high  = None  # non-conflict SD (optional)

        # If this is MANUAL or AUTOMATION, and we cached CALIBRATION realised mean/sd, use them.
        # self.calib_doms_params should look like:
        #   {"mu_low_start": ..., "mu_high_start": ..., "doms_sd_low": ..., "doms_sd_high": ...}
        if str(block_name).upper() in ("MANUAL", "AUTOMATION1", "AUTOMATION2"):
            params = None

            # 1) Prefer in-memory cached calibration from THIS run
            if self.calib_doms_params:
                params = dict(self.calib_doms_params)

            # 2) Fallback to most recent CALIBRATION summary on disk
            if params is None:
                params = load_latest_calibration_doms_params(
                    results_dir=RESULTS_DIR,
                    participant_tag=self.participant_tag  # e.g. "p007"
                )
                
                if params is not None:
                    print(f"[{block_name}] Loaded CALIBRATION DOMS params from disk:", params)

            # 3) Apply if we got something
            if params is not None:
                mu_low_start  = float(params["mu_low_start"])
                mu_high_start = float(params["mu_high_start"])
                doms_sd_low   = float(params["doms_sd_low"])
                doms_sd_high  = float(params["doms_sd_high"])

        print(
            f"[{block_name}] DOMS params: "
            f"mu_low={mu_low_start:.3f}, sd_low={('NA' if doms_sd_low is None else f'{doms_sd_low:.3f}')}; "
            f"mu_high={mu_high_start:.3f}, sd_high={('NA' if doms_sd_high is None else f'{doms_sd_high:.3f}')}"
        )

        # ------------------ Trial loop ------------------
        for i in range(total_trials):
            trial = build_atc_trial(
                x_dim=SCREEN_WIDTH,
                aspect_ratio=SCREEN_HEIGHT / SCREEN_WIDTH,
                angle_deg=90.0,
                speed_range=(400, 650),

                # Use block-specific params
                mu_low_start=mu_low_start,
                mu_high_start=mu_high_start,
                doms_sd=doms_sd,
                doms_sd_low=doms_sd_low,
                doms_sd_high=doms_sd_high,

                doms_low_bounds=(0.0, DOMS_THRESHOLD_NM - DOMS_EPS_NM),
                doms_high_bounds=(DOMS_THRESHOLD_NM + DOMS_EPS_NM, 10.0),

                ttms_range=(140, 210),
                flight_level=370,
                default_deadline=DEADLINE_SEC,
                callsigns=None,  # or provide a pool list
                enforce_unique_callsigns=True,
                used_callsigns=self.used_callsigns,
                pm_prop=self.args.pm_prop,
                staircase=self.staircase,
            )
 
            res = run_trial(
                screen=self.screen,
                clock=self.clock,
                font=self.font,
                info_font=self.info_font,
                feedback_font=self.feedback_font,
                trial=trial,
                trial_idx=i,
                total_trials=total_trials,
                has_pm_design=self.has_pm_design,
                drt_enabled=self.drt_enabled,
                aid_label_font=self.aid_label_font,
                aid_font=self.aid_font,
                run_ts=self.run_ts,
            )

            res["block"] = block_name
            res["block_idx"] = int(block_idx)
            res["participant_id"] = "" if self.participant_id is None else int(self.participant_id)
            res["key_conflict"] = self.key_conflict_label
            res["key_nonconf"] = self.key_nonconf_label
            res["key_pm"] = self.key_pm_label if self.has_pm_design else ""

            if "quit" in res and res["quit"]:
                break

            self.results.append(res)

            # Staircase update (exclude PM targets)
            if self.staircase.on:
                is_pm_trial = bool(getattr(trial, "is_PM", False))
                c = res.get("correct", "")
                if not is_pm_trial:
                    if c in (0, 1, "0", "1"):
                        self.staircase.update(correct=bool(int(c)))
                    else:
                        # Treat timeout / missing response as incorrect
                        self.staircase.update(correct=False)

    def save_results_csv(self, *, block_order: int, block_name: str):
        if not getattr(self, "results", None):
            print("No results to save.")
            return None

        os.makedirs(RESULTS_DIR, exist_ok=True)

        base = self.base_with_participant()
        tag = block_tag(block_order)
        bname = str(block_name).upper()

        out_path = os.path.join(RESULTS_DIR, f"results_{base}_{tag}_{bname}.csv")

        fieldnames = list(ALL_RESULT_FIELDS)
        rows = [normalize_result_row(r, fieldnames) for r in self.results]

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        print(f"Results saved to: {out_path}")
        return out_path

    def save_combined_results_csv(self, suffix: str = "b00_ALL"):
        if not getattr(self, "all_results", None):
            print("No combined results to save.")
            return None

        os.makedirs(RESULTS_DIR, exist_ok=True)

        base = self.base_with_participant()
        out_path = os.path.join(RESULTS_DIR, f"results_{base}_{suffix}.csv")

        fieldnames = list(ALL_RESULT_FIELDS)
        rows = [normalize_result_row(r, fieldnames) for r in self.all_results]

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
  
        print(f"Combined results saved to: {out_path}")
        return out_path

    def save_postblock_slider_results(self, *, block_order: int, block_name: str, block_idx: int):
        """
        Save ONLY the post-block slider responses for this block.
        """
        if not self.postblock_slider_responses:
            return

        os.makedirs(RESULTS_DIR, exist_ok=True)

        base = self.base_with_participant()
        tag = block_tag(block_order)
        bname = str(block_name).upper()

        out_path = os.path.join(RESULTS_DIR, f"results_{base}_{tag}_{bname}_POSTBLOCK_SLIDERS.csv")

        fieldnames = [
            "participant_id",
            "block",
            "block_idx",
            "slider_idx",
            "slider_key",
            "question",
            "response",
            "scale_min",
            "scale_max",
        ]

        rows = []
        pid = "" if self.participant_id is None else int(self.participant_id)

        for r in self.postblock_slider_responses:
            rr = dict(r)
            rr["participant_id"] = pid
            rr["block"] = str(block_name)
            rr["block_idx"] = int(block_idx)
            rows.append(rr)

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        print(f"Saved {len(rows)} post-block slider responses to {out_path}")

    def save_postblock_slider_all_results(self):
        """
        Save all post-block slider responses across blocks into one CSV.
        """
        os.makedirs(RESULTS_DIR, exist_ok=True)

        base = self.base_with_participant()
        out_path = os.path.join(RESULTS_DIR, f"results_{base}_b00_POSTBLOCK_SLIDERS_ALL.csv")

        fieldnames = [
            "participant_id",
            "block",
            "block_idx",
            "slider_idx",
            "slider_key",
            "question",
            "response",
            "scale_min",
            "scale_max",
        ]

        rows_src = getattr(self, "all_postblock_slider_responses", None)
        if rows_src is None:
            rows_src = []

        rows = []
        for r in rows_src:
            rr = dict(r)
            for k in fieldnames:
                if k not in rr or rr[k] is None:
                    rr[k] = ""
            rows.append(rr)

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            if rows:
                writer.writerows(rows)

        print(f"Combined post-block slider responses saved to: {out_path} (n_rows={len(rows)})")
        return out_path
  
    def save_postblock_results(self, *, block_order: int, block_name: str, block_idx: int):
        """
        Saves ONLY the post-block questionnaire responses for this block.
        Includes: participant_id, block, block_idx
        """
        if not self.postblock_responses:
            return

        os.makedirs(RESULTS_DIR, exist_ok=True)

        base = self.base_with_participant()
        tag = block_tag(block_order)
        bname = str(block_name).upper()

        q_path = os.path.join(RESULTS_DIR, f"results_{base}_{tag}_{bname}_POSTBLOCK.csv")

        q_fieldnames = [
            "participant_id",
            "block",
            "block_idx",
            "question_idx",
            "question",
            "left_anchor",
            "right_anchor",
            "response",
            "scale_min",
            "scale_max",
        ]

        write_header = not os.path.exists(q_path)

        pid = "" if self.participant_id is None else int(self.participant_id)

        rows = []
        for r in self.postblock_responses:
            rr = dict(r)
            rr["participant_id"] = pid
            rr["block"] = str(block_name)
            rr["block_idx"] = int(block_idx)
            rows.append(rr)

        with open(q_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=q_fieldnames, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerows(rows)

        print(f"Saved {len(rows)} post-block responses to {q_path}")

    def save_postblock_all_results(self):
        """
        Save ALL post-block questionnaire rows across blocks into one CSV.
        Filename ends with: POSTBLOCK_ALL.csv
        Always writes the file (even if zero rows), so you reliably get the header.
        """
        os.makedirs(RESULTS_DIR, exist_ok=True)

        base = self.base_with_participant()
        out_path = os.path.join(RESULTS_DIR, f"results_{base}_b00_POSTBLOCK_ALL.csv")

        q_fieldnames = [
            "participant_id",
            "block",
            "block_idx",
            "question_idx",
            "question",
            "left_anchor",
            "right_anchor",
            "response",
            "scale_min",
            "scale_max",
        ]

        rows_src = getattr(self, "all_postblock_responses", None)
        if rows_src is None:
            rows_src = []

        rows = []
        for r in rows_src:
            rr = dict(r)
            for k in q_fieldnames:
                if k not in rr or rr[k] is None:
                    rr[k] = ""
            rows.append(rr)

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=q_fieldnames, extrasaction="ignore")
            writer.writeheader()
            if rows:
                writer.writerows(rows)

        print(f"Combined post-block responses saved to: {out_path} (n_rows={len(rows)})")
        return out_path

    def run(self):
        # ---- Participant number screen (required) ----
        pid_res = run_participant_number_screen(self.screen, self.clock, self.font)
        if isinstance(pid_res, dict) and pid_res.get("quit"):
            pygame.quit()
            return

        self.participant_id = int(pid_res["participant"])
        self.participant_tag = f"p{self.participant_id:03d}"

        # ---- Counterbalanced key mapping ----
        m = counterbalanced_key_mapping(self.participant_id)

        global KEY_CONFLICT, KEY_NONCONFLICT
        KEY_CONFLICT = m["conflict_key"]
        KEY_NONCONFLICT = m["nonconflict_key"]

        # Store human-readable key names
        self.key_conflict_label = pygame.key.name(KEY_CONFLICT).upper()
        self.key_nonconf_label = pygame.key.name(KEY_NONCONFLICT).upper()
        self.key_pm_label = pygame.key.name(pygame.K_9).upper()

        print(
            f"[CB-KEYS] {self.key_conflict_label}=CONFLICT, "
            f"{self.key_nonconf_label}=NON-CONFLICT, "
            f"{self.key_pm_label}=PM"
        )

        # ---- Optional single-block selection via CLI ----
        def _norm_block_name(s: Optional[str]) -> Optional[str]:
            if s is None:
                return None
            s = str(s).strip()
            if s == "":
                return None
            # tolerate "--block -calibration"
            s = s.lstrip("-").strip()
            return s.upper()

        requested = _norm_block_name(getattr(self.args, "block", None))

        def _find_block(name_upper: str):
            for i, b in enumerate(BLOCKS):
                bname = str(b.get("name", f"BLOCK{i+1}")).strip().upper()
                if bname == name_upper:
                    return (i, b)
            return None

        if requested is None:
            # ---- Counterbalanced MANUAL/AUTOMATION1/AUTOMATION2 order after TRAINING+CALIBRATION ----
            # training    = _find_block("TRAINING")
            calibration = _find_block("CALIBRATION")
            manual      = _find_block("MANUAL")
            auto1       = _find_block("AUTOMATION1")
            auto2       = _find_block("AUTOMATION2")

            missing = [n for n, x in [
                # ("TRAINING", training),
                ("CALIBRATION", calibration),
                ("MANUAL", manual),
                ("AUTOMATION1", auto1),
                ("AUTOMATION2", auto2),
            ] if x is None]
            if missing:
                raise SystemExit(f"[BLOCKS] Missing block(s) in BLOCKS: {', '.join(missing)}")

            (order_names, order_id) = counterbalanced_block_ordering(self.participant_id)
            name_to_block = {
                "MANUAL": manual,
                "AUTOMATION1": auto1,
                "AUTOMATION2": auto2,
            }

            # blocks_to_run = [training, calibration] + [name_to_block[n] for n in order_names]
            blocks_to_run = [calibration] + [name_to_block[n] for n in order_names]
            print(f"[CB-BLOCKS] participant_id={self.participant_id} => ordering #{order_id}: {order_names}")

        else:
            found = _find_block(requested)
            if found is None:
                valid = ", ".join(str(b.get("name", f"BLOCK{i+1}")) for i, b in enumerate(BLOCKS))
                raise SystemExit(f"[CLI] Unknown --block {requested!r}. Valid block names: {valid}")

            blocks_to_run = [found]

        # ---- Run selected blocks ----
        for loop_idx, (b_idx, block) in enumerate(blocks_to_run):
            is_last_block = (loop_idx == len(blocks_to_run) - 1)

            name = str(block.get("name", f"BLOCK{b_idx+1}"))
            n_trials = int(block.get("N_TRIALS", N_TRIALS))

            # ---- General task instructions before every block ----
            self.show_instructions()

            # ---- Block-specific instruction screen ----
            bi = self.show_block_instructions(name)
            if isinstance(bi, dict) and bi.get("quit"):
                pygame.quit()
                return

            # ---- Generic pre-block screen ----
            pre = run_preblock_screen(self.screen, self.clock, self.font, name)
            if isinstance(pre, dict) and pre.get("quit"):
                pygame.quit()
                return

            # Apply block-level toggles (automation, fixation, staircase, questionnaires, etc.)
            apply_block_settings(block)
            
            # ---- Per-block DRT toggle ----
            # Block flag overrides CLI --drt for that block.
            self.drt_enabled = bool(block.get("DRT_ON", self.args.drt))
            print(f"[{name}] DRT_ON={self.drt_enabled}")

            # Reset staircase if requested
            reset_st = bool(block.get("RESET_STAIRCASE", True))
            if reset_st:
                self.reset_staircase(on=STAIRCASE_ON, target_acc=TARGET_ACC)
            else:
                self.staircase.on = bool(STAIRCASE_ON)
                self.staircase.target_acc = float(TARGET_ACC)

            # Reset per-block buffers
            self.results = []
            self.postblock_slider_responses = []
            self.postblock_responses = []

            presented_order = loop_idx + 1  # <-- THIS is the order shown in the session: b01, b02, ...

            # Run trials and save per-block trial csv
            self.run_trials(n_trials=n_trials, block_name=name, block_idx=presented_order)
            self.save_results_csv(block_order=presented_order, block_name=name)

            # Append into across-block buffer (used for all-blocks save)
            self.all_results.extend([dict(r) for r in self.results])

            # Compute and save per-block DOMS summary
            exclude_n = int(STAIRCASE_BURNIN) if bool(STAIRCASE_ON) else 0
            if str(name).upper() in ("MANUAL", "AUTOMATION1", "AUTOMATION2"):
                exclude_n = 0

            summary_last_n = CALIB_SUMMARY_LAST_N if str(name).upper() == "CALIBRATION" else None

            self.doms_stats = self.compute_doms_summary(
                exclude_first_trials=exclude_n,
                summary_last_n=summary_last_n
            )
            
            self.save_doms_summary_csv(block_order=presented_order, block_name=name)

            # Cache CALIBRATION DOMS params for later blocks
            if str(name).upper() == "CALIBRATION":
                ds = dict(self.doms_stats or {})

                def _ok(x):
                    return isinstance(x, (int, float)) and (not math.isnan(x)) and math.isfinite(x)

                if (ds.get("n_conflict", 0) >= 5 and ds.get("n_nonconflict", 0) >= 5
                    and _ok(ds.get("mean_conflict")) and _ok(ds.get("sd_conflict"))
                    and _ok(ds.get("mean_nonconflict")) and _ok(ds.get("sd_nonconflict"))):

                    self.calib_doms_params = {
                        "mu_low_start": float(ds["mean_conflict"]),
                        "mu_high_start": float(ds["mean_nonconflict"]),
                        "doms_sd_low": max(1e-6, float(ds["sd_conflict"])),
                        "doms_sd_high": max(1e-6, float(ds["sd_nonconflict"])),
                    }

                    print("[CALIBRATION] Cached DOMS params for later blocks:", self.calib_doms_params)
                else:
                    self.calib_doms_params = None
                    print("[CALIBRATION] DOMS stats insufficient; not caching for later blocks.")

            # Optional immediate block feedback (per-block switch)
            disp = get_block_display_title(name)
            show_fb = bool(block.get("SHOW_BLOCK_FEEDBACK", False))
            did_show_fb = False
            if show_fb and self.results:
                show_block_feedback(self.screen, self.clock, self.font, self.results, block_name=name)
                did_show_fb = True
                
            # Post-block slider questions
            if ENABLE_POSTBLOCK_SLIDERS:
                s_res = run_postblock_slider_questions(
                    self.screen,
                    self.clock,
                    self.font,
                    block_name=name,
                    title_font=self.title_font
                )
                if isinstance(s_res, dict) and s_res.get("quit"):
                    pygame.quit()
                    return

                self.postblock_slider_responses = s_res if isinstance(s_res, list) else []

                self.save_postblock_slider_results(
                    block_order=presented_order,
                    block_name=name,
                    block_idx=presented_order
                )

                pid = "" if self.participant_id is None else int(self.participant_id)
                for r in self.postblock_slider_responses:
                    rr = dict(r)
                    rr["participant_id"] = pid
                    rr["block"] = str(name)
                    rr["block_idx"] = int(presented_order)
                    self.all_postblock_slider_responses.append(rr)
        
            # Post-block questionnaire (only if enabled by this block's settings)
            if ENABLE_POSTBLOCK_QUESTIONS:
                intro = run_questionnaire_intro_screen(
                    self.screen, self.clock, self.font, self.title_font
                )
                if isinstance(intro, dict) and intro.get("quit"):
                    pygame.quit()
                    return

                q_res = run_postblock_questionnaire(
                    self.screen, self.clock, self.font, base_name=name, label_font=self.label_font
                )
                if isinstance(q_res, dict) and q_res.get("quit"):
                    pygame.quit()
                    return

                self.postblock_responses = q_res if isinstance(q_res, list) else []

                # save per-block postblock
                self.save_postblock_results(
                    block_order=presented_order,
                    block_name=name,
                    block_idx=presented_order
                )

                # append into across-block buffer (with required columns)
                pid = "" if self.participant_id is None else int(self.participant_id)
                for r in self.postblock_responses:
                    rr = dict(r)
                    rr["participant_id"] = pid
                    rr["block"] = str(name)
                    rr["block_idx"] = int(presented_order)
                    self.all_postblock_responses.append(rr)

            # ---- End-of-block vs experiment-complete screen ----
            if is_last_block:
                # SAVE COMBINED FILES BEFORE FINAL ESC-TO-EXIT SCREEN
                if len(blocks_to_run) > 1:
                    self.save_combined_results_csv(suffix="b00_ALL")

                self.save_postblock_all_results()
                self.save_postblock_slider_all_results()

                final_score_pct = self.compute_final_performance_score()
                done = run_experiment_complete_screen(
                    self.screen,
                    self.clock,
                    self.font,
                    performance_score_pct=final_score_pct
                )
                pygame.quit()
                return
            else:
                # If we already showed the accuracy feedback screen, don't show the generic block-complete screen.
                if did_show_fb:
                    continue

                if str(name).upper() not in ("MANUAL", "AUTOMATION1", "AUTOMATION2"):
                    done = run_endblock_screen(self.screen, self.clock, self.font, name)
                    if isinstance(done, dict) and done.get("quit"):
                        pygame.quit()
                        return


# ------------------------------ Main / CLI -------------------------------

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=SCREEN_WIDTH)
    parser.add_argument("--height", type=int, default=SCREEN_HEIGHT)
    parser.add_argument("--n-trials", type=int, default=N_TRIALS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--drt", action="store_true")
    parser.add_argument("--pm-prop", dest="pm_prop", type=float, default=0.0,
                        help="Probability each trial is a PM trial (0..1).")

    parser.add_argument(
        "--automation-on",
        type=str2bool,
        default=AUTOMATION_ON,
        help="Enable/disable automation overlay (TRUE/FALSE)."
    )
    parser.add_argument("--automation-acc", type=float, default=AUTOMATION_ACC)
    parser.add_argument("--automation-delay", type=float, default=AUTOMATION_DELAY_SEC,
                        help="Seconds after stimulus onset to show automation. Negative shows it BEFORE stimulus for abs(value).")
    parser.add_argument("--trial-csv", type=str, default=None,
                        help="Optional path to an input trials CSV (if not generating trials on the fly).")
    parser.add_argument(
        "--block",
        type=str,
        default=None,
        help="Run only a single block by name (TRAINING/CALIBRATION/MANUAL/AUTOMATION1/AUTOMATION2)."
             "Example: --block CALIBRATION (leading '-' tolerated: --block -calibration)."
    )
    parser.add_argument("--fullscreen", action="store_true", default=True,
                    help="Run in fullscreen at the display's native resolution.")
    return parser.parse_args()


def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT
    global AUTOMATION_ON, AUTOMATION_ACC, AUTOMATION_DELAY_SEC

    args = parse_args()

    # Minimal init so we can query display resolution
    pygame.init()

    # Configure resolution + UI scale + scaled globals
    # Only pre-compute scaling for WINDOWED mode.
    # Fullscreen sizing must be finalized after set_mode() (macOS/Retina).
    configure_display_and_scaling(
        fullscreen=False if bool(args.fullscreen) else False,
        requested_w=int(args.width),
        requested_h=int(args.height),
    )

    AUTOMATION_ON = bool(args.automation_on)
    AUTOMATION_ACC = float(args.automation_acc)
    AUTOMATION_DELAY_SEC = float(args.automation_delay)

    print(f"[DISPLAY] {SCREEN_WIDTH}x{SCREEN_HEIGHT} UI_SCALE={UI_SCALE:.3f} GEOM_SCALE={GEOM_SCALE:.3f}")
    print(f"[CLI] AUTOMATION_ON={AUTOMATION_ON} AUTOMATION_ACC={AUTOMATION_ACC} AUTOMATION_DELAY_SEC={AUTOMATION_DELAY_SEC}")

    if args.seed is not None:
        random.seed(args.seed)

    has_pm_design = (args.pm_prop is not None and args.pm_prop > 0.0)
    app = ATCLabApp(has_pm_design, args, drt_enabled=args.drt, fullscreen=bool(args.fullscreen))
    app.run()


if __name__ == "__main__":
    main()

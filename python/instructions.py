import os
import sys
import math
import random
import pygame

import atclab as task


# =========================================================
# Config
# =========================================================

FULLSCREEN = True
REQUESTED_W = 1280
REQUESTED_H = 720
EXPORT_FINISHED_SLIDES = False
EXPORT_DIR = "instruction_slide_images"

random.seed(12345)

HUD_TEXT_COLOR = (255, 255, 255)
CALL_OUT_BG = (30, 30, 30)
CALL_OUT_BORDER = (255, 255, 255)
AID_WHITE = (255, 255, 255)
GUIDE_COLOR       = (255, 255, 0)     # pure yellow, super bright
DEBUG_TEXT = False


# =========================================================
# Init display + scaling
# =========================================================

pygame.init()
pygame.display.set_caption("ATC Instructions")

task.configure_display_and_scaling(
    fullscreen=FULLSCREEN,
    requested_w=REQUESTED_W,
    requested_h=REQUESTED_H,
)

if FULLSCREEN:
    screen = pygame.display.set_mode(
        (0, 0),
        pygame.FULLSCREEN | pygame.DOUBLEBUF,
        vsync=1,
    )
else:
    screen = pygame.display.set_mode(
        (REQUESTED_W, REQUESTED_H),
        pygame.DOUBLEBUF,
        vsync=1,
    )

task.configure_scaling_from_surface(screen)
clock = pygame.time.Clock()


# =========================================================
# Fonts
# =========================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.dirname(os.path.abspath(task.__file__))

font_candidates = [
    os.path.join(SCRIPT_DIR, "python", "fonts", "Roboto-Light.ttf"),
    os.path.join(SCRIPT_DIR, "fonts", "Roboto-Light.ttf"),
    os.path.join(TASK_DIR, "fonts", "Roboto-Light.ttf"),
]

base_font_path = next((p for p in font_candidates if os.path.exists(p)), None)


def make_font(px, bold=False):
    px = max(10, int(px))
    if base_font_path and os.path.exists(base_font_path):
        f = pygame.font.Font(base_font_path, px)
    else:
        f = pygame.font.SysFont("arial", px)
    if bold:
        f.set_bold(True)
    return f


font = make_font(task.ui(24), bold=False)
title_font = make_font(task.ui(36), bold=False)
small_body_font = make_font(task.ui(30), bold=False)
aid_label_font = make_font(task.ui(20), bold=False)
aid_font = make_font(task.ui(32), bold=True)
info_font = make_font(task.ui(16), bold=False)
label_font = make_font(task.ui(18), bold=False)
callout_title_font = make_font(task.ui(26), bold=False)
callout_font = make_font(task.ui(22), bold=False)

# =========================================================
# Slides
# =========================================================

SLIDES = [
    {
        "kind": "text",
        "title": "CONFLICT DETECTION TASK",
        "center_title": True,
        "small_body": True,
        "body": (
            "In this study, you will take on the role of an air traffic controller. "
            "Your task is to detect conflicts, that is, judge whether aircraft will get "
            "too close to each other or not. \n\n"
            "On each trial you will see two aircraft moving on converging flight paths toward a central crossing point. "
            "You’ll be shown a similar number of conflict and non-conflict pairs. "
            "You must judge whether you think each pair will conflict or not at any point during their flights.\n\n"
            "The following screens will help you get familiar with the task"
        ),
    },
    {
        "kind": "black_text",
        "body": "TASK DISPLAY",
    },
    {"kind": "display_focus", "title": "", "focus": "airspace"},
    {"kind": "display_focus", "title": "", "focus": "aircraft"},
    {"kind": "display_focus", "title": "", "focus": "route_lines"},
    {"kind": "display_focus", "title": "", "focus": "info_block"},
    {"kind": "display_focus", "title": "", "focus": "airspeed"},
    {"kind": "display_focus", "title": "", "focus": "probe_vector"},
    {"kind": "display_focus", "title": "", "focus": "guide_cross1"},
    {"kind": "display_focus", "title": "", "focus": "guide_cross2_center"},
    {"kind": "display_focus", "title": "", "focus": "guide_cross2_arm"},
    {"kind": "display_focus", "title": "", "focus": "guide_cross3"},
    {"kind": "display_focus", "title": "", "focus": "countdown_timer"},
    {"kind": "display_focus", "title": "", "focus": "masked_aid_banner"},
    {"kind": "display_focus", "title": "", "focus": "progress_counter"},
    # {"kind": "display_focus", "title": "", "focus": "callsign"},
    # {"kind": "display_focus", "title": "", "focus": "type"},
    # {"kind": "display_focus", "title": "", "focus": "flight_level"},
    {
        "kind": "black_text",
        "body": "WHAT IS A CONFLICT?",
    },
    {
        "kind": "conflict_1",
        "title": "WHAT IS A CONFLICT?",
        "body": (
            "When aircraft get closer than 5 nautical miles laterally from each other, "
            "they are in conflict"
        ),
    },
    {
        "kind": "conflict_2",
        "title": "WHAT IS A CONFLICT?",
        "body": (
            "These aircraft will conflict if this distance\n"
            "gets smaller than 5nm at any point\n"
            "during their flights"
        ),
    },
    {
        "kind": "conflict_3",
        "title": "WHAT IS A CONFLICT?",
        "body": (
            "These circles show the\n"
            "aircraft part way through their flights"
        ),
    },
    {
        "kind": "conflict_4",
        "title": "WHAT IS A CONFLICT?",
        "body": (
            "These yellow circles show where the\n"
            "aircraft will be at minimum separation\n\n"
            "In this example, that distance is smaller\n"
            "than 5nm, so these aircraft are in conflict"
        ),
    },
    {
        "kind": "conflict_5",
        "title": "WHAT IS A CONFLICT?",
        "body": (
            "In the experiment, on each trial you'll \nsee two aircraft moving on \n"
            "converging flight paths toward a \ncentral crossing point\n\n"
            "You must judge whether you think each \npair will conflict or not at any point\n"
            "during their flights"
        ),
    },
    {
        "kind": "black_text",
        "body": "AUTOMATED DECISION AID",
    },
    {
        "kind": "automation_intro_1",
        "title": "AUTOMATED DECISION AID",
        "hide_title": True,
        "body": (
            "In some parts of this study you will be assisted\n"
            "by an Automated Decision Aid"
        ),
    },
    {
        "kind": "automation_intro_2",
        "title": "AUTOMATED DECISION AID",
        "hide_title": True,
        "body": (
            "The automation will recommend a classification\n"
            "(either conflict or non-conflict)\n"
            "for each aircraft pair"
        ),
    },
    {
        "kind": "automation_example",
        "title": "AUTOMATED DECISION AID",
        "hide_title": True,
        "body": (
            "In this example, the automated decision\n"
            "aid is recommending that you classify the\n"
            "aircraft pair as a conflict"
        ),
        "automation_label": "CONFLICT",
    },
    {
        "kind": "automation_example",
        "title": "AUTOMATED DECISION AID",
        "hide_title": True,
        "body": (
            "In this example, the automated decision\n"
            "aid is recommending that you classify the\n"
            "aircraft pair as a non-conflict"
        ),
        "automation_label": "NON-CONF",
    },
    {
        "kind": "text",
        "title": "PERFORMANCE",
        "center_title": True,
        "small_body": True,
        "body": (
            "We will keep an ongoing tally of your performance. "
            "At the end of the experiment you will receive a point-based bonus, up to $25, based on your performance score.\n\n"
            "You will have up to 10 seconds to respond per trial. "
            "Incorrect responses and responses not made before the deadline will reduce your performance score, so try "
            "to respond as quickly and accurately as possible.\n\n"
            "You may take short breaks at any time between trials\n\n"
        ),
    },
    {
        "kind": "text",
        "title": "INSTRUCTIONS COMPLETE",
        "center_title": True,
        "small_body": True,
        "body": (
            "You will now begin your first block of trials\n\n"
            "Please let the experimenter know if you have any questions"
        ),
    },
]


# =========================================================
# Buttons
# =========================================================

def draw_nav_button(surface, rect, label, enabled=True):
    if enabled:
        pygame.draw.rect(surface, (50, 50, 50), rect, 0, border_radius=task.ui(8))
        pygame.draw.rect(surface, HUD_TEXT_COLOR, rect, max(1, task.ui(3)), border_radius=task.ui(8))
        label_col = HUD_TEXT_COLOR
    else:
        pygame.draw.rect(surface, (35, 35, 35), rect, 0, border_radius=task.ui(8))
        pygame.draw.rect(surface, (110, 110, 110), rect, max(1, task.ui(2)), border_radius=task.ui(8))
        label_col = (140, 140, 140)

    text_surf = font.render(label, True, label_col)
    text_rect = text_surf.get_rect(center=rect.center)
    surface.blit(text_surf, text_rect)


# =========================================================
# Text helpers
# =========================================================

def wrap_text_lines(font_obj, text, max_width):
    words = str(text).split()
    if not words:
        return [""]

    lines = []
    cur = words[0]
    for word in words[1:]:
        test = f"{cur} {word}"
        if font_obj.size(test)[0] <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def draw_wrapped_centered_block(surface, font_obj, text, rect, color=None, line_gap=None):
    if color is None:
        color = HUD_TEXT_COLOR
    if line_gap is None:
        line_gap = int(font_obj.get_linesize() * 0.35)

    x, y, w, h = rect
    paragraphs = str(text).split("\n")

    lines = []
    for para in paragraphs:
        if para.strip() == "":
            lines.append("")
        else:
            lines.extend(wrap_text_lines(font_obj, para, w))

    heights = []
    for line in lines:
        if line == "":
            heights.append(font_obj.get_linesize())
        else:
            heights.append(font_obj.get_linesize() + line_gap)

    total_h = sum(heights)
    yy = y + max(0, (h - total_h) // 2)

    for line in lines:
        if line == "":
            yy += font_obj.get_linesize()
            continue
        surf = font_obj.render(line, True, color)
        rr = surf.get_rect(center=(x + w // 2, yy + surf.get_height() // 2))
        surface.blit(surf, rr)
        yy += font_obj.get_linesize() + line_gap


def draw_title(surface, title):
    if not title:
        return
    surf = title_font.render(title, True, HUD_TEXT_COLOR)
    rect = surf.get_rect(center=(task.SCREEN_WIDTH // 2, task.ui(45)))
    surface.blit(surf, rect)


def draw_guide_cross_instructions(surface, trial,
                                  color=GUIDE_COLOR,
                                  thickness=1,
                                  tick_len=None):
    """
    Instruction version of the task guide cross.
    Uses the exact same geometry as the task implementation.
    """
    if tick_len is None:
        tick_len = task.ui(8)

    center_x = int(task.GUIDE_MARGIN + trial.guide_min_sep)
    center_y = task.SCREEN_HEIGHT // 2

    min_sep = trial.guide_min_sep

    h_half = min_sep
    v_half = min_sep * 2

    pygame.draw.line(
        surface,
        color,
        (center_x - h_half, center_y),
        (center_x + h_half, center_y),
        thickness,
    )

    pygame.draw.line(
        surface,
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
            surface,
            color,
            (x_left, center_y - tick_len / 2.0),
            (x_left, center_y + tick_len / 2.0),
            1,
        )
        pygame.draw.line(
            surface,
            color,
            (x_right, center_y - tick_len / 2.0),
            (x_right, center_y + tick_len / 2.0),
            1,
        )

    long_tick = tick_len * 2.0
    for x_end in (center_x - h_half, center_x + h_half):
        pygame.draw.line(
            surface,
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
            surface,
            color,
            (center_x - tick_len / 2.0, y_up),
            (center_x + tick_len / 2.0, y_up),
            1,
        )
        pygame.draw.line(
            surface,
            color,
            (center_x - tick_len / 2.0, y_down),
            (center_x + tick_len / 2.0, y_down),
            1,
        )

    for y_end in (center_y - v_half, center_y + v_half):
        pygame.draw.line(
            surface,
            color,
            (center_x - long_tick / 2.0, y_end),
            (center_x + long_tick / 2.0, y_end),
            1,
        )

    return {
        "guide_x": center_x,
        "guide_y": center_y,
        "guide_min_sep": int(min_sep),
        "guide_full_w": int(2 * h_half),
        "guide_full_h": int(2 * v_half),
    }
    
    
# =========================================================
# Example trial generation
# =========================================================

def make_example_trial(conflict=True, automation=None):
    for _ in range(500):
        trial = task.build_atc_trial(
            x_dim=task.SCREEN_WIDTH,
            aspect_ratio=task.SCREEN_HEIGHT / task.SCREEN_WIDTH,
            angle_deg=90.0,
            speed_range=(400, 650),
            mu_low_start=2.0,
            mu_high_start=8.0,
            doms_sd=0.25,
            doms_sd_low=0.25,
            doms_sd_high=0.25,
            doms_low_bounds=(0.0, 5.0),
            doms_high_bounds=(5.0, 10.0),
            ttms_range=(170, 190),
            flight_level=370,
            default_deadline=10.0,
            callsigns=None,
            enforce_unique_callsigns=False,
            used_callsigns=None,
            pm_prop=0.0,
            staircase=None,
        )

        if bool(trial.is_conflict) == bool(conflict):
            trial.automation = automation
            if automation is not None:
                trial.auto_delay = 0.0
                trial.auto_fail_prop = None
                true_lbl = "CONFLICT" if trial.is_conflict else "NON-CONF"
                trial.auto_fail = (str(automation).upper() != true_lbl)
            return trial

    raise RuntimeError("Could not generate requested example trial.")


DISPLAY_TRIAL = make_example_trial(conflict=False, automation=None)
CONFLICT_TRIAL = make_example_trial(conflict=True, automation=None)
AUTO_INTRO_TRIAL = make_example_trial(conflict=False, automation=None)
AUTO_CONFLICT_TRIAL = make_example_trial(conflict=True, automation="CONFLICT")
AUTO_NONCONF_TRIAL = make_example_trial(conflict=False, automation="NON-CONF")


# =========================================================
# Custom ATC snapshot drawing
# =========================================================

def draw_info_box_custom(surface, callsign, speed_label, topleft,
                         text_color=(255, 255, 255),
                         box_color=None,
                         border_color=None):

    pad_x = task.ui(1)
    pad_y = task.ui(1)
    line_gap = task.ui(4)

    cs_surf = info_font.render(str(callsign), True, text_color)
    type_surf = info_font.render("B737", True, text_color)
    sp_surf = info_font.render(str(speed_label), True, text_color)

    content_w = max(cs_surf.get_width(), type_surf.get_width(), sp_surf.get_width())
    content_h = (
        cs_surf.get_height()
        + line_gap
        + type_surf.get_height()
        + line_gap
        + sp_surf.get_height()
    )

    rect = pygame.Rect(
        int(topleft[0]),
        int(topleft[1]),
        content_w + 2 * pad_x,
        content_h + 2 * pad_y,
    )

    # line 1: callsign
    cs_rect = cs_surf.get_rect(topleft=(rect.left + pad_x, rect.top + pad_y))

    # line 2: aircraft type
    type_rect = type_surf.get_rect(topleft=(rect.left + pad_x, cs_rect.bottom + line_gap))

    # line 3: flight level / speed
    sp_rect = sp_surf.get_rect(topleft=(rect.left + pad_x, type_rect.bottom + line_gap))

    surface.blit(cs_surf, cs_rect)
    surface.blit(type_surf, type_rect)
    surface.blit(sp_surf, sp_rect)

    return rect


def draw_masked_aid_banner_custom(surface, y):
    label_up = str(task.MASKED_AID_BANNER_TEXT)

    surf1 = aid_label_font.render("AID JUDGES:", True, HUD_TEXT_COLOR)
    rect1 = surf1.get_rect(midtop=(task.SCREEN_WIDTH // 2, int(y)))
    surface.blit(surf1, rect1)

    surf2 = aid_font.render(label_up, True, HUD_TEXT_COLOR)
    rect2 = surf2.get_rect(midtop=(task.SCREEN_WIDTH // 2, rect1.bottom + task.ui(4)))
    surface.blit(surf2, rect2)

    return {
        "label_rect": rect1,
        "value_rect": rect2,
    }
    
    
def draw_aid_banner_custom(surface, label, y):
    label_up = str(label).upper()

    if label_up == "CONFLICT":
        label_color = task.INCORRECT_COLOR
    elif label_up in ("NON-CONF", "NONCONFLICT", "NON-CONFLICT"):
        label_color = task.CORRECT_COLOR
    else:
        label_color = HUD_TEXT_COLOR

    surf1 = aid_label_font.render("AID JUDGES:", True, AID_WHITE)
    rect1 = surf1.get_rect(midtop=(task.SCREEN_WIDTH // 2, int(y)))
    surface.blit(surf1, rect1)

    surf2 = aid_font.render(label_up, True, label_color)
    rect2 = surf2.get_rect(midtop=(task.SCREEN_WIDTH // 2, rect1.bottom + task.ui(4)))
    surface.blit(surf2, rect2)

    return {
        "label_rect": rect1,
        "value_rect": rect2,
    }


def draw_blank_radar_instructions(surface, trial, cx, cy, border_color=None, draw_guide=False):
    """Instruction-only radar background."""
    surface.fill(task.BG_COLOR)

    # Background circle
    big_radius = task.SCREEN_HEIGHT // 2
    pygame.draw.circle(
        surface,
        task.BG_CIRCLE_COLOR,
        (int(cx), int(cy)),
        big_radius,
        0,
    )

    # Route lines
    pygame.draw.line(
        surface,
        task.ROUTE_COLOR,
        (int(trial.route1_start_x), int(trial.route1_start_y)),
        (int(trial.route1_end_x),   int(trial.route1_end_y)),
        max(1, task.ui(1)),
    )
    pygame.draw.line(
        surface,
        task.ROUTE_COLOR,
        (int(trial.route2_start_x), int(trial.route2_start_y)),
        (int(trial.route2_end_x),   int(trial.route2_end_y)),
        max(1, task.ui(1)),
    )

    # Optional context border
    if border_color is not None:
        pygame.draw.rect(
            surface,
            border_color,
            surface.get_rect(),
            max(1, task.ui(8)),
        )

    # Optional guide cross
    if draw_guide:
        draw_guide_cross_instructions(surface, trial, color=GUIDE_COLOR)
        
        
def draw_trial_snapshot(surface, trial, *, timer_text="9.8s", trial_text="Trial 1/40",
                        show_aid_banner=True, masked_banner=False):
    surface.fill(task.BG_COLOR)
    surface.set_clip(None)

    cx = task.SCREEN_WIDTH / 2
    cy = task.SCREEN_HEIGHT / 2

    draw_blank_radar_instructions(surface, trial, cx, cy, border_color=None, draw_guide=False)
    surface.set_clip(None)

    guide_meta = draw_guide_cross_instructions(surface, trial, color=GUIDE_COLOR)

    guide_x = guide_meta["guide_x"]
    guide_y = guide_meta["guide_y"]

    sep_arm = guide_meta["guide_min_sep"]
    sep_full_w = guide_meta["guide_full_w"]
    sep_full_h = guide_meta["guide_full_h"]

    bar_x1 = guide_x - sep_arm
    bar_x2 = guide_x + sep_arm
    bar_y = guide_y

    x1 = int(trial.pos1_start_x)
    y1 = int(trial.pos1_start_y)
    x2 = int(trial.pos2_start_x)
    y2 = int(trial.pos2_start_y)

    pygame.draw.circle(surface, task.AC1_CIRCLE_COLOR, (x1, y1), task.CIRCLE_RADIUS, max(1, task.ui(1)))
    pygame.draw.circle(surface, task.AC2_CIRCLE_COLOR, (x2, y2), task.CIRCLE_RADIUS, max(1, task.ui(1)))

    future_dt = 60.0
    f1_x = int(x1 + trial.vel1_x * future_dt)
    f1_y = int(y1 + trial.vel1_y * future_dt)
    f2_x = int(x2 + trial.vel2_x * future_dt)
    f2_y = int(y2 + trial.vel2_y * future_dt)

    pygame.draw.line(surface, task.AC1_CIRCLE_COLOR, (x1, y1), (f1_x, f1_y), max(1, task.ui(1)))
    pygame.draw.line(surface, task.AC2_CIRCLE_COLOR, (x2, y2), (f2_x, f2_y), max(1, task.ui(1)))

    pygame.draw.circle(surface, (255, 255, 255), (f1_x, f1_y), task.ui(2), 0)
    pygame.draw.circle(surface, (255, 255, 255), (f2_x, f2_y), task.ui(2), 0)

    fl1 = int(trial.ac1_fl)
    fl2 = int(trial.ac2_fl)
    sp1 = trial.ac1_speed
    sp2 = trial.ac2_speed

    speed_label1 = f"{fl1}>{fl1} {sp1:.0f}"
    speed_label2 = f"{fl2}>{fl2} {sp2:.0f}"

    box_offset = task.ui(80)
    diag = box_offset / math.sqrt(2.0)

    box1_tl = (x1 + diag, y1 - diag)
    box2_tl = (x2 + diag, y2 - diag)

    box1_rect = draw_info_box_custom(surface, trial.callsign1, speed_label1, box1_tl)
    box2_rect = draw_info_box_custom(surface, trial.callsign2, speed_label2, box2_tl)

    def draw_middle_connector(color, circle_pos, box_rect):
        x0, y0 = circle_pos
        x1c, y1c = box_rect.topleft

        vx = x1c - x0
        vy = y1c - y0
        dist = math.hypot(vx, vy)

        if dist <= 1e-6:
            return

        ux = vx / dist
        uy = vy / dist

        start_pad = task.ui(16)
        end_pad   = task.ui(16)

        start_x = x0 + ux * start_pad
        start_y = y0 + uy * start_pad
        end_x   = x1c - ux * end_pad
        end_y   = y1c - uy * end_pad

        pygame.draw.line(
            surface,
            color,
            (int(start_x), int(start_y)),
            (int(end_x), int(end_y)),
            max(1, task.ui(1)),
        )

    draw_middle_connector(task.AC1_CIRCLE_COLOR, (x1, y1), box1_rect)
    draw_middle_connector(task.AC2_CIRCLE_COLOR, (x2, y2), box2_rect)

    surface.set_clip(None)

    corner_pad = task.ui(16)

    timer_surf = font.render(timer_text, True, HUD_TEXT_COLOR)
    timer_rect = timer_surf.get_rect(topleft=(corner_pad, corner_pad))
    surface.blit(timer_surf, timer_rect)

    header_surf = font.render(trial_text, True, HUD_TEXT_COLOR)
    header_rect = header_surf.get_rect(topright=(task.SCREEN_WIDTH - corner_pad, corner_pad))
    surface.blit(header_surf, header_rect)

    aid_meta = None

    if masked_banner:
        aid_meta = draw_masked_aid_banner_custom(
            surface,
            task.ui(task.MASKED_AID_BANNER_Y),
        )
    elif show_aid_banner and trial.automation is not None:
        aid_meta = draw_aid_banner_custom(surface, str(trial.automation), task.ui(20))

    if DEBUG_TEXT:
        dbg = font.render("DEBUG TEXT", True, (255, 0, 0))
        surface.blit(dbg, (task.ui(200), task.ui(200)))
        pygame.draw.rect(surface, (255, 0, 0), pygame.Rect(task.ui(190), task.ui(190), task.ui(250), task.ui(60)), 2)

    meta = {
        "timer_rect": timer_rect,
        "header_rect": header_rect,
        "airspace_center": (int(cx), int(cy)),
        "airspace_radius": task.SCREEN_HEIGHT // 2,
        "aircraft1": (x1, y1),
        "aircraft2": (x2, y2),
        "probe1": (f1_x, f1_y),
        "probe2": (f2_x, f2_y),
        "box1_rect": box1_rect,
        "box2_rect": box2_rect,
        "guide_x": guide_x,
        "guide_y": guide_y,
        "guide_min_sep": int(trial.guide_min_sep),   # 5 nm arm length from centre
        "guide_full_w": sep_full_w,                  # 10 nm total horizontal width
        "guide_full_h": sep_full_h,                  # 20 nm total vertical height
        "sep_bar_start": (bar_x1, bar_y),
        "sep_bar_end": (bar_x2, bar_y),
        "sep_bar_mid": ((bar_x1 + bar_x2) // 2, bar_y),
        "aid_meta": aid_meta,
    }
    return meta


def draw_trial_snapshot_muted(surface, trial, *, timer_text="9.8s", trial_text="Trial 1/40",
                              aircraft_color=(120, 120, 120),
                              route_color=(100, 100, 100),
                              probe_dot_color=(150, 150, 150),
                              text_color=(130, 130, 130),
                              connector_color=(110, 110, 110)):
    surface.fill(task.BG_COLOR)
    surface.set_clip(None)

    cx = task.SCREEN_WIDTH / 2
    cy = task.SCREEN_HEIGHT / 2

    draw_blank_radar_instructions(surface, trial, cx, cy, border_color=None, draw_guide=False)
    surface.set_clip(None)

    draw_guide_cross_instructions(surface, trial, color=GUIDE_COLOR)

    x1 = int(trial.pos1_start_x)
    y1 = int(trial.pos1_start_y)
    x2 = int(trial.pos2_start_x)
    y2 = int(trial.pos2_start_y)

    pygame.draw.circle(surface, aircraft_color, (x1, y1), task.CIRCLE_RADIUS, max(1, task.ui(1)))
    pygame.draw.circle(surface, aircraft_color, (x2, y2), task.CIRCLE_RADIUS, max(1, task.ui(1)))

    future_dt = 60.0
    f1_x = int(x1 + trial.vel1_x * future_dt)
    f1_y = int(y1 + trial.vel1_y * future_dt)
    f2_x = int(x2 + trial.vel2_x * future_dt)
    f2_y = int(y2 + trial.vel2_y * future_dt)

    pygame.draw.line(surface, route_color, (x1, y1), (f1_x, f1_y), max(1, task.ui(1)))
    pygame.draw.line(surface, route_color, (x2, y2), (f2_x, f2_y), max(1, task.ui(1)))

    pygame.draw.circle(surface, probe_dot_color, (f1_x, f1_y), task.ui(2), 0)
    pygame.draw.circle(surface, probe_dot_color, (f2_x, f2_y), task.ui(2), 0)

    fl1 = int(trial.ac1_fl)
    fl2 = int(trial.ac2_fl)
    sp1 = trial.ac1_speed
    sp2 = trial.ac2_speed

    speed_label1 = f"{fl1}>{fl1} {sp1:.0f}"
    speed_label2 = f"{fl2}>{fl2} {sp2:.0f}"

    box_offset = task.ui(80)
    diag = box_offset / math.sqrt(2.0)

    box1_tl = (x1 + diag, y1 - diag)
    box2_tl = (x2 + diag, y2 - diag)

    box1_rect = draw_info_box_custom(surface, trial.callsign1, speed_label1, box1_tl, text_color=text_color)
    box2_rect = draw_info_box_custom(surface, trial.callsign2, speed_label2, box2_tl, text_color=text_color)

    def draw_middle_connector(color, circle_pos, box_rect):
        x0, y0 = circle_pos
        x1c, y1c = box_rect.topleft

        vx = x1c - x0
        vy = y1c - y0
        dist = math.hypot(vx, vy)

        if dist <= 1e-6:
            return

        ux = vx / dist
        uy = vy / dist

        start_pad = task.ui(16)
        end_pad   = task.ui(16)

        start_x = x0 + ux * start_pad
        start_y = y0 + uy * start_pad
        end_x   = x1c - ux * end_pad
        end_y   = y1c - uy * end_pad

        pygame.draw.line(
            surface,
            color,
            (int(start_x), int(start_y)),
            (int(end_x), int(end_y)),
            max(1, task.ui(1)),
        )

    draw_middle_connector(connector_color, (x1, y1), box1_rect)
    draw_middle_connector(connector_color, (x2, y2), box2_rect)

    corner_pad = task.ui(16)

    timer_surf = font.render(timer_text, True, text_color)
    timer_rect = timer_surf.get_rect(topleft=(corner_pad, corner_pad))
    surface.blit(timer_surf, timer_rect)

    header_surf = font.render(trial_text, True, text_color)
    header_rect = header_surf.get_rect(topright=(task.SCREEN_WIDTH - corner_pad, corner_pad))
    surface.blit(header_surf, header_rect)

    return {
        "timer_rect": timer_rect,
        "header_rect": header_rect,
        "airspace_center": (int(cx), int(cy)),
        "airspace_radius": task.SCREEN_HEIGHT // 2,
        "aircraft1": (x1, y1),
        "aircraft2": (x2, y2),
        "probe1": (f1_x, f1_y),
        "probe2": (f2_x, f2_y),
        "box1_rect": box1_rect,
        "box2_rect": box2_rect,
    }
  
  
# =========================================================
# Callouts / overlays
# =========================================================

def draw_automation_callout(surface, meta, text, side="left", title=None):
    if not meta.get("aid_meta") or not meta["aid_meta"].get("value_rect"):
        return

    target = meta["aid_meta"]["value_rect"].midbottom

    if side == "right":
        box_topleft = (task.ui(760), task.ui(120))
    else:
        box_topleft = (task.ui(80), task.ui(120))

    draw_callout(
        surface,
        text,
        box_topleft,
        target,
        align="left",
        title=title,
    )
    
    
def draw_callout_box(surface, text, topleft, align="center", title=None):
    pad_x = task.ui(10)
    pad_y = task.ui(7)
    line_gap = task.ui(3)
    title_body_gap = task.ui(6)

    body_lines = str(text).split("\n")
    body_surfs = [callout_font.render(line, True, HUD_TEXT_COLOR) for line in body_lines]

    title_surf = None
    if title:
        title_surf = callout_title_font.render(str(title), True, HUD_TEXT_COLOR)

    text_w = 0
    if title_surf:
        text_w = max(text_w, title_surf.get_width())
    if body_surfs:
        text_w = max(text_w, max(s.get_width() for s in body_surfs))

    text_h = 0
    if title_surf:
        text_h += title_surf.get_height()
        if body_surfs:
            text_h += title_body_gap

    if body_surfs:
        text_h += sum(s.get_height() for s in body_surfs)
        text_h += max(0, len(body_surfs) - 1) * line_gap

    box = pygame.Rect(
        int(topleft[0]),
        int(topleft[1]),
        text_w + 2 * pad_x,
        text_h + 2 * pad_y,
    )

    pygame.draw.rect(surface, CALL_OUT_BG, box, border_radius=task.ui(6))
    pygame.draw.rect(surface, CALL_OUT_BORDER, box, max(1, task.ui(1)), border_radius=task.ui(6))

    yy = box.top + pad_y

    # title: always left-justified
    if title_surf:
        title_rect = title_surf.get_rect(topleft=(box.left + pad_x, yy))
        surface.blit(title_surf, title_rect)
        yy += title_surf.get_height()
        if body_surfs:
            yy += title_body_gap

    # body
    for surf in body_surfs:
        if align == "left":
            rect = surf.get_rect(topleft=(box.left + pad_x, yy))
        else:
            rect = surf.get_rect(midtop=(box.centerx, yy))
        surface.blit(surf, rect)
        yy += surf.get_height() + line_gap

    return box
  
  
def draw_callout_multi(surface, text, box_topleft, targets, align="center", title=None):
    box = draw_callout_box(surface, text, box_topleft, align=align, title=title)

    for target_xy in targets:
        start = _nearest_box_anchor(box, target_xy)

        sx, sy = start
        tx, ty = target_xy
        vx = tx - sx
        vy = ty - sy
        dist = math.hypot(vx, vy)

        if dist < 1:
            continue

        ux = vx / dist
        uy = vy / dist

        gap_from_target = task.ui(14)
        end_x = tx - ux * gap_from_target
        end_y = ty - uy * gap_from_target

        line_w = max(1, task.ui(1))
        pygame.draw.line(
            surface,
            HUD_TEXT_COLOR,
            (int(sx), int(sy)),
            (int(end_x), int(end_y)),
            line_w,
        )

        head_len = task.ui(5)
        head_w = task.ui(3)

        bx = end_x - ux * head_len
        by = end_y - uy * head_len

        px = -uy
        py = ux

        left = (bx + px * head_w, by + py * head_w)
        right = (bx - px * head_w, by - py * head_w)

        pygame.draw.polygon(
            surface,
            HUD_TEXT_COLOR,
            [
                (int(tx), int(ty)),
                (int(left[0]), int(left[1])),
                (int(right[0]), int(right[1])),
            ],
        )
        
        
def draw_callout(surface, text, box_topleft, target_xy, align="center", title=None):
    box = draw_callout_box(surface, text, box_topleft, align=align, title=title)

    start = _nearest_box_anchor(box, target_xy)

    sx, sy = start
    tx, ty = target_xy
    vx = tx - sx
    vy = ty - sy
    dist = math.hypot(vx, vy)

    if dist < 1:
        return

    ux = vx / dist
    uy = vy / dist

    gap_from_target = task.ui(14)
    end_x = tx - ux * gap_from_target
    end_y = ty - uy * gap_from_target

    line_w = max(1, task.ui(1))
    pygame.draw.line(
        surface,
        HUD_TEXT_COLOR,
        (int(sx), int(sy)),
        (int(end_x), int(end_y)),
        line_w,
    )

    head_len = task.ui(5)
    head_w = task.ui(3)

    bx = end_x - ux * head_len
    by = end_y - uy * head_len

    px = -uy
    py = ux

    left = (bx + px * head_w, by + py * head_w)
    right = (bx - px * head_w, by - py * head_w)

    pygame.draw.polygon(
        surface,
        HUD_TEXT_COLOR,
        [
            (int(tx), int(ty)),
            (int(left[0]), int(left[1])),
            (int(right[0]), int(right[1])),
        ],
    )


def _nearest_box_anchor(box, target_xy):
    anchors = {
        "top": box.midtop,
        "bottom": box.midbottom,
        "left": box.midleft,
        "right": box.midright,
    }
    tx, ty = target_xy
    best_pt = None
    best_d2 = None
    for pt in anchors.values():
        dx = pt[0] - tx
        dy = pt[1] - ty
        d2 = dx * dx + dy * dy
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best_pt = pt
    return best_pt


def draw_display_focus(surface, meta, focus):
    cx, cy = meta["airspace_center"]
    radius = meta["airspace_radius"]
    if focus == "airspace":
        theta = math.radians(225)  # upper-left point on circumference
        target = (
            int(cx + radius * math.cos(theta)),
            int(cy + radius * math.sin(theta)),
        )
        draw_callout(
            surface,
            "This circular area\n is the airspace",
            (task.ui(80), task.ui(120)),
            target,
            align="left",
            title="Airspace",
        )
    elif focus == "countdown_timer":
        draw_callout(
            surface,
            "The countdown timer shows how many \nseconds remain in the trial",
            (task.ui(80), task.ui(80)),
            meta["timer_rect"].midbottom,
            align="left",
            title="Timer",
        )
    elif focus == "progress_counter":
        draw_callout(
            surface,
            "The progress counter shows\nwhich trial you are currently on",
            (task.ui(780), task.ui(80)),
            meta["header_rect"].midbottom,
            align="left",
            title="Progress counter",
        )
    elif focus == "guide_cross1":
        guide_box_topleft = (task.ui(120), task.ui(300))
        cross_center = (
            meta["guide_x"],
            meta["guide_y"],
        )
        draw_callout(
            surface,
            "The guide cross indicates distance\nIt is 10 nautical miles (nm) wide \nand 20 nm tall",
            guide_box_topleft,
            cross_center,
            align="left",
            title="Guide cross",
        )

    elif focus == "guide_cross2_center":
        guide_box_topleft = (task.ui(120), task.ui(300))
        cross_center = (
            meta["guide_x"],
            meta["guide_y"],
        )
        draw_callout(
            surface,
            "From the centre, the length of \neach horizontal arm equals the \n5nm minimum separation distance",
            guide_box_topleft,
            cross_center,
            align="left",
            title="Guide cross",
        )

    elif focus == "guide_cross2_arm":
        guide_box_topleft = (task.ui(120), task.ui(300))
        right_arm_end = (
            meta["guide_x"] + meta["guide_min_sep"],
            meta["guide_y"],
        )
        draw_callout(
            surface,
            "From the centre, the length of \neach horizontal arm equals the \n5nm minimum separation distance",
            guide_box_topleft,
            right_arm_end,
            align="left",
            title="Guide cross",
        )

    elif focus == "guide_cross3":
        guide_box_topleft = (task.ui(120), task.ui(300))
        cross_center = (
            meta["guide_x"],
            meta["guide_y"],
        )
        right_arm_end = (
            meta["guide_x"] + meta["guide_min_sep"],
            meta["guide_y"],
        )
        draw_callout_multi(
            surface,
            "This minimum separation distance \ndefines whether aircraft are in conflict or not",
            guide_box_topleft,
            [
                cross_center,   # arrow to centre
                right_arm_end,  # arrow to end of right horizontal arm
            ],
            align="left",
            title="Guide cross",
        )
    elif focus == "masked_aid_banner":
        if meta.get("aid_meta") and meta["aid_meta"].get("value_rect"):
            draw_callout(
                surface,
                "In automation blocks, the aid's\nrecommendation appears here",
                (task.ui(80), task.ui(90)),
                meta["aid_meta"]["value_rect"].midbottom,
                align="left",
                title="Automated decision aid",
            )
    elif focus == "aircraft":
        draw_callout_multi(
            surface,
            "Circular icons show the \nlocation of the aircraft",
            (task.ui(80), task.ui(300)),
            [meta["aircraft1"], meta["aircraft2"]],
            align="left",
            title="Aircraft stimuli",
        )
    elif focus == "route_lines":

        # distance behind aircraft along route line
        back = task.ui(30)

        # normalize velocity vectors
        v1_mag = math.hypot(DISPLAY_TRIAL.vel1_x, DISPLAY_TRIAL.vel1_y)
        v2_mag = math.hypot(DISPLAY_TRIAL.vel2_x, DISPLAY_TRIAL.vel2_y)

        if v1_mag > 0:
            ux1 = DISPLAY_TRIAL.vel1_x / v1_mag
            uy1 = DISPLAY_TRIAL.vel1_y / v1_mag
        else:
            ux1 = uy1 = 0

        if v2_mag > 0:
            ux2 = DISPLAY_TRIAL.vel2_x / v2_mag
            uy2 = DISPLAY_TRIAL.vel2_y / v2_mag
        else:
            ux2 = uy2 = 0

        # points slightly behind each aircraft circle
        route_target1 = (
            int(meta["aircraft1"][0] - ux1 * back),
            int(meta["aircraft1"][1] - uy1 * back),
        )

        route_target2 = (
            int(meta["aircraft2"][0] - ux2 * back),
            int(meta["aircraft2"][1] - uy2 * back),
        )

        draw_callout_multi(
            surface,
            "Route lines show the \nflight paths of the aircraft",
            (task.ui(80), task.ui(300)),
            [route_target1, route_target2],
            align="left",
            title="Route lines",
        )
    elif focus == "info_block":
        draw_callout_multi(
            surface,
            "Info blocks show information \nabout the aircraft, including:\n\nCALLSIGN (e.g., KZB238)\nAIRCRAFT TYPE (e.g., B737)\nFLIGHT LEVEL (e.g., 370>370)\nAIRSPEED (e.g., 588 knots)",
            (task.ui(700), task.ui(200)),
            [meta["box1_rect"].midright, meta["box2_rect"].midright],
            align="left",
            title="Info block",
        )
    # elif focus == "callsign":
    #     draw_callout(
    #         surface,
    #         "Callsign",
    #         (task.ui(620), task.ui(200)),
    #         (meta["box2_rect"].left + task.ui(40), meta["box2_rect"].top + task.ui(12)),
    #         align="left",
    #     )
    # elif focus == "type":
    #     draw_callout(
    #         surface,
    #         "Aircraft type",
    #         (task.ui(620), task.ui(200)),
    #         (meta["box2_rect"].left + task.ui(40), meta["box2_rect"].top + task.ui(12)),
    #         align="left",
    #     )
    # elif focus == "flight_level":
    #     draw_callout(
    #         surface,
    #         "Flight level",
    #         (task.ui(620), task.ui(200)),
    #         (meta["box2_rect"].left + task.ui(40), meta["box2_rect"].top + task.ui(12)),
    #         align="left",
    #     )
    elif focus == "airspeed":
        draw_callout(
            surface,
            "This aircraft is travelling at \n588 knots (nautical miles per hour)",
            (task.ui(620), task.ui(200)),
            (
                meta["box2_rect"].right - task.ui(10),
                meta["box2_rect"].bottom - task.ui(8) - info_font.get_height() // 2,
            ),
            align="left",
            title="Airspeed",
        )
    elif focus == "probe_vector":
        probe_target1 = meta["probe1"]
        probe_target2 = meta["probe2"]

        draw_callout_multi(
            surface,
            "Probe vector lines indicate\n the aircraft's projected position\n in 60 seconds",
            (task.ui(100), task.ui(360)),
            [probe_target1, probe_target2],
            align="left",
            title="Probe vector",
        )


def draw_dashed_line(surface, color, start, end, width=1, dash_len=10, gap_len=6):
    x1, y1 = start
    x2, y2 = end

    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)

    if dist <= 0:
        return

    ux = dx / dist
    uy = dy / dist

    step = dash_len + gap_len
    n_steps = int(dist // step) + 1

    for i in range(n_steps):
        seg_start_dist = i * step
        seg_end_dist = min(seg_start_dist + dash_len, dist)

        if seg_start_dist >= dist:
            break

        sx = x1 + ux * seg_start_dist
        sy = y1 + uy * seg_start_dist
        ex = x1 + ux * seg_end_dist
        ey = y1 + uy * seg_end_dist

        pygame.draw.line(
            surface,
            color,
            (int(sx), int(sy)),
            (int(ex), int(ey)),
            width,
        )
        
        
def draw_conflict_overlay_from_points(surface, p1, p2):
    x1, y1 = p1
    x2, y2 = p2

    line_w = max(1, task.ui(2))
    draw_dashed_line(
        surface,
        GUIDE_COLOR,
        (x1, y1),
        (x2, y2),
        width=line_w,
        dash_len=task.ui(12),
        gap_len=task.ui(8),
    )

    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)

    if dist > 0:
        ux = dx / dist
        uy = dy / dist

        head_len = task.ui(18)
        head_w = task.ui(5)

        px = -uy
        py = ux

        bx1 = x1 + ux * head_len
        by1 = y1 + uy * head_len
        left1 = (bx1 + px * head_w, by1 + py * head_w)
        right1 = (bx1 - px * head_w, by1 - py * head_w)

        pygame.draw.polygon(
            surface,
            GUIDE_COLOR,
            [
                (int(x1), int(y1)),
                (int(left1[0]), int(left1[1])),
                (int(right1[0]), int(right1[1])),
            ],
        )

        bx2 = x2 - ux * head_len
        by2 = y2 - uy * head_len
        left2 = (bx2 + px * head_w, by2 + py * head_w)
        right2 = (bx2 - px * head_w, by2 - py * head_w)

        pygame.draw.polygon(
            surface,
            GUIDE_COLOR,
            [
                (int(x2), int(y2)),
                (int(left2[0]), int(left2[1])),
                (int(right2[0]), int(right2[1])),
            ],
        )

    midx = (x1 + x2) // 2
    midy = (y1 + y2) // 2

    return {
        "min_sep_mid": (midx, midy),
        "min_sep_endpoints": ((x1, y1), (x2, y2)),
    }

    
# =========================================================
# Slide rendering
# =========================================================
def draw_text_slide(surface, slide):
    surface.fill(task.BG_COLOR)

    title = slide.get("title", "")
    body = slide.get("body", "")
    show_title = bool(title) and not slide.get("hide_title", False)

    body_font = small_body_font if slide.get("small_body", False) else font

    content_w = task.SCREEN_WIDTH - task.ui(300)
    content_x = task.ui(150)

    title_gap = task.ui(40)   # gap between title and body text

    # --- Wrap body first so we know its height ---
    body_paras = str(body).split("\n")
    body_lines = []
    for para in body_paras:
        if para.strip() == "":
            body_lines.append("")
        else:
            body_lines.extend(wrap_text_lines(body_font, para, content_w))

    body_line_gap = int(body_font.get_linesize() * 0.35)
    body_heights = []
    for line in body_lines:
        if line == "":
            body_heights.append(body_font.get_linesize())
        else:
            body_heights.append(body_font.get_linesize() + body_line_gap)
    body_h = sum(body_heights)

    # --- Title height ---
    title_h = 0
    title_surf = None
    if show_title:
        title_surf = title_font.render(title, True, HUD_TEXT_COLOR)
        title_h = title_surf.get_height()

    total_h = title_h + (title_gap if show_title else 0) + body_h

    # Vertically centre title+body together
    start_y = (task.SCREEN_HEIGHT - total_h) // 2

    # Slight upward bias if you want the whole block a touch higher:
    start_y -= task.ui(20)

    # --- Draw title ---
    body_top = start_y
    if show_title:
        title_rect = title_surf.get_rect(center=(task.SCREEN_WIDTH // 2, start_y + title_h // 2))
        surface.blit(title_surf, title_rect)
        body_top = title_rect.bottom + title_gap

    # --- Draw body ---
    body_rect = pygame.Rect(
        content_x,
        body_top,
        content_w,
        body_h,
    )
    draw_wrapped_centered_block(surface, body_font, body, body_rect, color=HUD_TEXT_COLOR)


def draw_display_focus_slide(surface, slide):
    focus = slide["focus"]

    show_masked_banner = (focus == "masked_aid_banner")

    meta = draw_trial_snapshot(
        surface,
        DISPLAY_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        show_aid_banner=False,
        masked_banner=show_masked_banner,
    )
    if not slide.get("hide_title", False):
        draw_title(surface, slide["title"])
    draw_display_focus(surface, meta, focus)


def draw_black_text_slide(surface, slide):
    surface.fill((0, 0, 0))

    rect = pygame.Rect(
        task.ui(120),
        task.ui(120),
        task.SCREEN_WIDTH - task.ui(240),
        task.SCREEN_HEIGHT - task.ui(240),
    )
    draw_wrapped_centered_block(surface, title_font, slide["body"], rect, color=(255, 255, 255))
    
    
def draw_conflict_1_slide(surface, slide):
    meta = draw_trial_snapshot(
        surface,
        CONFLICT_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        show_aid_banner=False,
        masked_banner=False,
    )

    conflict_meta = draw_conflict_overlay_from_points(
        surface,
        meta["aircraft1"],
        meta["aircraft2"],
    )

    draw_callout(
        surface,
        "A conflict occurs when aircraft get closer\n"
        "than 5 nautical miles laterally from\n"
        "each other",
        (task.ui(200), task.ui(360)),
        conflict_meta["min_sep_mid"],
        align="left",
        title="Conflict",
    )

def draw_conflict_2_slide(surface, slide):
    meta = draw_trial_snapshot(
        surface,
        CONFLICT_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        show_aid_banner=False,
        masked_banner=False,
    )

    conflict_meta = draw_conflict_overlay_from_points(
        surface,
        meta["aircraft1"],
        meta["aircraft2"],
    )

    draw_callout(
        surface,
        slide["body"],
        (task.ui(200), task.ui(360)),
        conflict_meta["min_sep_mid"],
        align="left",
        title="Conflict",
    )
    
    
def draw_conflict_3_slide(surface, slide):
    meta = draw_trial_snapshot_muted(
        surface,
        CONFLICT_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        aircraft_color=(120, 120, 120),
        route_color=(100, 100, 100),
        probe_dot_color=(150, 150, 150),
        text_color=(130, 130, 130),
        connector_color=(110, 110, 110),
    )

    cpa_meta = compute_cpa(CONFLICT_TRIAL)
    half_t = cpa_meta["t_cpa"] / 2.0
    half_meta = compute_positions_at_time(CONFLICT_TRIAL, half_t)

    ghost_meta = draw_projected_ghost_aircraft(
        surface,
        CONFLICT_TRIAL,
        half_meta,
        ghost_color=HUD_TEXT_COLOR,
    )

    draw_callout_multi(
        surface,
        slide["body"],
        (task.ui(120), task.ui(280)),
        [ghost_meta["ghost1"], ghost_meta["ghost2"]],
        align="left",
        title="Conflict",
    )
    
    
def draw_conflict_4_slide(surface, slide):
    meta = draw_trial_snapshot_muted(
        surface,
        CONFLICT_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        aircraft_color=(120, 120, 120),
        route_color=(100, 100, 100),
        probe_dot_color=(150, 150, 150),
        text_color=(130, 130, 130),
        connector_color=(110, 110, 110),
    )

    cpa_meta = compute_cpa(CONFLICT_TRIAL)
    ghost_meta = draw_projected_ghost_aircraft(
        surface,
        CONFLICT_TRIAL,
        cpa_meta,
        ghost_color=GUIDE_COLOR,   # yellow ghost aircraft
    )

    draw_callout_multi(
        surface,
        slide["body"],
        (task.ui(120), task.ui(280)),
        [ghost_meta["ghost1"], ghost_meta["ghost2"]],
        align="left",
        title="Conflict",
    )
    

def draw_conflict_5_slide(surface, slide):
    meta = draw_trial_snapshot_muted(
        surface,
        CONFLICT_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        aircraft_color=(120, 120, 120),
        route_color=(100, 100, 100),
        probe_dot_color=(150, 150, 150),
        text_color=(130, 130, 130),
        connector_color=(110, 110, 110),
    )

    cpa_meta = compute_cpa(CONFLICT_TRIAL)
    draw_projected_ghost_aircraft(
        surface,
        CONFLICT_TRIAL,
        cpa_meta,
        ghost_color=GUIDE_COLOR,
    )

    draw_callout_box(
        surface,
        slide["body"],
        (task.ui(120), task.ui(280)),
        align="left",
        title="Conflict",
    )
    
    
def draw_automation_intro_1_slide(surface, slide):
    meta = draw_trial_snapshot(
        surface,
        AUTO_INTRO_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        show_aid_banner=False,
        masked_banner=True,
    )

    target = meta["aid_meta"]["value_rect"].midbottom

    draw_callout(
        surface,
        slide["body"],
        (task.ui(80), task.ui(120)),  # left side
        target,
        align="left",
        title="Automated decision aid",
    )


def draw_automation_intro_2_slide(surface, slide):
    meta = draw_trial_snapshot(
        surface,
        AUTO_INTRO_TRIAL,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        show_aid_banner=False,
        masked_banner=True,
    )

    target = meta["aid_meta"]["value_rect"].midbottom

    draw_callout(
        surface,
        slide["body"],
        (task.ui(760), task.ui(120)),
        target,
        align="left",
        title="Automated decision aid",
    )
    

def draw_automation_example_slide(surface, slide):
    trial = AUTO_CONFLICT_TRIAL if slide["automation_label"] == "CONFLICT" else AUTO_NONCONF_TRIAL

    meta = draw_trial_snapshot(
        surface,
        trial,
        timer_text="9.8s",
        trial_text="Trial 1/40",
        show_aid_banner=True,
        masked_banner=False,
    )

    side = "right" if slide["automation_label"] == "NON-CONF" else "left"
    draw_automation_callout(
        surface,
        meta,
        slide["body"],
        side=side,
        title="Recommendation",
    )


def draw_slide(surface, idx):
    slide = SLIDES[idx]
    kind = slide["kind"]

    if kind == "text":
        draw_text_slide(surface, slide)
    elif kind == "black_text":
        draw_black_text_slide(surface, slide)
    elif kind == "display_focus":
        draw_display_focus_slide(surface, slide)
    elif kind == "conflict_1":
        draw_conflict_1_slide(surface, slide)
    elif kind == "conflict_2":
        draw_conflict_2_slide(surface, slide)
    elif kind == "conflict_3":
        draw_conflict_3_slide(surface, slide)
    elif kind == "conflict_4":
        draw_conflict_4_slide(surface, slide)
    elif kind == "conflict_5":
        draw_conflict_5_slide(surface, slide)
    elif kind == "automation_intro_1":
        draw_automation_intro_1_slide(surface, slide)
    elif kind == "automation_intro_2":
        draw_automation_intro_2_slide(surface, slide)
    elif kind == "automation_example":
        draw_automation_example_slide(surface, slide)
    else:
        raise ValueError(f"Unknown slide kind: {kind}")


def compute_positions_at_time(trial, t):
    """
    Compute aircraft positions at time t seconds from trial start.
    """
    x1 = float(trial.pos1_start_x)
    y1 = float(trial.pos1_start_y)
    x2 = float(trial.pos2_start_x)
    y2 = float(trial.pos2_start_y)

    vx1 = float(trial.vel1_x)
    vy1 = float(trial.vel1_y)
    vx2 = float(trial.vel2_x)
    vy2 = float(trial.vel2_y)

    p1 = (
        int(round(x1 + vx1 * t)),
        int(round(y1 + vy1 * t)),
    )
    p2 = (
        int(round(x2 + vx2 * t)),
        int(round(y2 + vy2 * t)),
    )

    return {
        "t": t,
        "p1": p1,
        "p2": p2,
    }
    
    
def compute_cpa(trial, max_t=None):
    """
    Compute time of closest point of approach (CPA) in seconds, based on
    current positions and velocity vectors in screen coordinates.

    If max_t is provided, clamp to [0, max_t].
    """
    x1 = float(trial.pos1_start_x)
    y1 = float(trial.pos1_start_y)
    x2 = float(trial.pos2_start_x)
    y2 = float(trial.pos2_start_y)

    vx1 = float(trial.vel1_x)
    vy1 = float(trial.vel1_y)
    vx2 = float(trial.vel2_x)
    vy2 = float(trial.vel2_y)

    rx = x2 - x1
    ry = y2 - y1
    rvx = vx2 - vx1
    rvy = vy2 - vy1

    rv2 = rvx * rvx + rvy * rvy
    if rv2 <= 1e-12:
        t_cpa = 0.0
    else:
        t_cpa = - (rx * rvx + ry * rvy) / rv2

    if max_t is None:
        t_cpa = max(0.0, t_cpa)
    else:
        t_cpa = max(0.0, min(float(max_t), t_cpa))

    p1 = (
        int(round(x1 + vx1 * t_cpa)),
        int(round(y1 + vy1 * t_cpa)),
    )
    p2 = (
        int(round(x2 + vx2 * t_cpa)),
        int(round(y2 + vy2 * t_cpa)),
    )

    return {
        "t_cpa": t_cpa,
        "p1": p1,
        "p2": p2,
    }


def draw_projected_ghost_aircraft(surface, trial, pos_meta, ghost_color=GUIDE_COLOR):
    """
    Draw ghost aircraft at supplied positions, with their own probe vector lines.
    """
    p1 = pos_meta["p1"]
    p2 = pos_meta["p2"]

    ghost_r = task.CIRCLE_RADIUS
    ghost_w = max(1, task.ui(1))
    dot_r = max(2, task.ui(2))
    line_w = max(1, task.ui(1))

    future_dt = 60.0

    gp1_x = int(round(p1[0] + trial.vel1_x * future_dt))
    gp1_y = int(round(p1[1] + trial.vel1_y * future_dt))
    gp2_x = int(round(p2[0] + trial.vel2_x * future_dt))
    gp2_y = int(round(p2[1] + trial.vel2_y * future_dt))

    # ghost probe vectors
    pygame.draw.line(surface, ghost_color, p1, (gp1_x, gp1_y), line_w)
    pygame.draw.line(surface, ghost_color, p2, (gp2_x, gp2_y), line_w)

    # ghost probe endpoints
    pygame.draw.circle(surface, ghost_color, (gp1_x, gp1_y), dot_r, 0)
    pygame.draw.circle(surface, ghost_color, (gp2_x, gp2_y), dot_r, 0)

    # ghost aircraft outlines
    pygame.draw.circle(surface, ghost_color, p1, ghost_r, ghost_w)
    pygame.draw.circle(surface, ghost_color, p2, ghost_r, ghost_w)

    return {
        "ghost1": p1,
        "ghost2": p2,
        "ghost_mid": ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2),
        "ghost_probe1": (gp1_x, gp1_y),
        "ghost_probe2": (gp2_x, gp2_y),
    }
    
    
# =========================================================
# Optional export of finished slides
# =========================================================

def export_finished_slides():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for i in range(len(SLIDES)):
        surf = pygame.Surface((task.SCREEN_WIDTH, task.SCREEN_HEIGHT))
        draw_slide(surf, i)
        out_path = os.path.join(EXPORT_DIR, f"slide_{i+1:02d}.png")
        pygame.image.save(surf, out_path)


if EXPORT_FINISHED_SLIDES:
    export_finished_slides()


# =========================================================
# Main loop
# =========================================================

def main():
    slide_idx = 0

    back_rect = pygame.Rect(
        task.ui(80),
        task.SCREEN_HEIGHT - task.ui(80),
        task.ui(180),
        task.ui(52),
    )
    next_rect = pygame.Rect(
        task.SCREEN_WIDTH - task.ui(260),
        task.SCREEN_HEIGHT - task.ui(80),
        task.ui(180),
        task.ui(52),
    )

    while True:
        clock.tick(task.FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if task.is_hard_quit_event(event) or event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                    if slide_idx < len(SLIDES) - 1:
                        slide_idx += 1
                    else:
                        pygame.quit()
                        sys.exit()

                if event.key == pygame.K_LEFT and slide_idx > 0:
                    slide_idx -= 1

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if back_rect.collidepoint(event.pos) and slide_idx > 0:
                    slide_idx -= 1
                elif next_rect.collidepoint(event.pos):
                    if slide_idx < len(SLIDES) - 1:
                        slide_idx += 1
                    else:
                        pygame.quit()
                        sys.exit()

        draw_slide(screen, slide_idx)

        draw_nav_button(screen, back_rect, "BACK", enabled=(slide_idx > 0))

        # Change label on final slide
        if slide_idx == len(SLIDES) - 1:
            next_label = "DONE"
        else:
            next_label = "NEXT"

        draw_nav_button(screen, next_rect, next_label, enabled=True)

        pygame.display.flip()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
atc_extremes_plot.py

Standalone script to:
  1) Enumerate "range corner" extreme cases implied by your ATC geometry equations
     (speed min/max, TTMS min/max, DOMS min/max, OOP +/-).
  2) Identify the cases that:
       - maximize starting radius (off-screen risk)
       - minimize starting radius (too-close-to-centre risk)
       - minimize TCOP1 / TCOP2 (sanity)
  3) Render those extreme cases as overlays on a radar-style display,
     and save a single-page PDF.
  4) Monte-Carlo sample N aircraft pairs from the given ranges and plot
     their start positions as dots:
       - white if the *pair* is within safe bounds (both aircraft OK)
       - red otherwise.
  5) For each sampled pair, rotate BOTH start points by a random angle
     about the centre so the sampled cloud is not constrained to one heading line.
"""

import argparse
import itertools
import math
import random
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List

import matplotlib.pyplot as plt


# ---------------------- Visual style --------------------------------------

BG_COLOR = (20 / 255.0, 20 / 255.0, 20 / 255.0)
BG_CIRCLE_COLOR = (30 / 255.0, 30 / 255.0, 30 / 255.0)


# ---------------------- Geometry: exact equations -------------------------

def atc_dists_nm(
    doms_nm: float,
    ttms_s: float,
    sp1_kn: float,
    sp2_kn: float,
    angle_deg: float,
    oop_sign: int,
) -> Optional[Tuple[float, float, float, float, float, float, float]]:
    """
    Returns:
      dist1_nm, dist2_nm, TCOP1_s, TCOP2_s, v1_nmps, v2_nmps, M_s
    using your exact equations.
    """
    v1 = sp1_kn / 3600.0
    v2 = sp2_kn / 3600.0
    rad = math.radians(angle_deg)

    A = v1 * v1 + v2 * v2 - 2.0 * v1 * v2 * math.cos(rad)
    Y = v1 * v2 * math.sin(rad)
    W = v2 - v1 * math.cos(rad)

    if abs(Y) < 1e-12 or abs(A) < 1e-12:
        return None

    absM = doms_nm * math.sqrt(A) / Y
    M = float(oop_sign) * absM

    TCOP1 = ttms_s - (v2 * M * W) / A
    TCOP2 = TCOP1 + M

    dist1 = TCOP1 * v1
    dist2 = TCOP2 * v2

    return dist1, dist2, TCOP1, TCOP2, v1, v2, M


def scale_about_center(x: float, y: float, cx: float, cy: float, s: float) -> Tuple[float, float]:
    return (cx + (x - cx) * s, cy + (y - cy) * s)


def positions_from_dists(
    dist1_nm: float,
    dist2_nm: float,
    theta1_deg: float,
    angle_deg: float,
    W: int,
    H: int,
    geom_scale: float,
) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    cx = 0.5 * W
    cy = 0.5 * H

    th1 = math.radians(theta1_deg)
    th2 = th1 + math.radians(angle_deg)

    raw1x = cx + math.cos(th1) * dist1_nm
    raw1y = cy + math.sin(th1) * dist1_nm
    raw2x = cx + math.cos(th2) * dist2_nm
    raw2y = cy + math.sin(th2) * dist2_nm

    p1x, p1y = scale_about_center(raw1x, raw1y, cx, cy, geom_scale)
    p2x, p2y = scale_about_center(raw2x, raw2y, cx, cy, geom_scale)

    def toward_center(px, py, length=70.0):
        vx = cx - px
        vy = cy - py
        n = math.hypot(vx, vy)
        if n < 1e-9:
            return (px, py)
        ux, uy = vx / n, vy / n
        return (px + ux * length, py + uy * length)

    return (p1x, p1y), (p2x, p2y), toward_center(p1x, p1y), toward_center(p2x, p2y)


def rotate_about_center(px: float, py: float, cx: float, cy: float, ang_rad: float) -> Tuple[float, float]:
    dx = px - cx
    dy = py - cy
    ca = math.cos(ang_rad)
    sa = math.sin(ang_rad)
    return (cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)


# ---------------------- Case selection + diagnostics ----------------------

@dataclass
class Case:
    label: str
    doms: float
    ttms: float
    sp1: float
    sp2: float
    oop: int
    dist1: float
    dist2: float
    tcop1: float
    tcop2: float
    v1: float
    v2: float
    M: float


def enumerate_corner_cases(
    speed_min: float,
    speed_max: float,
    ttms_min: float,
    ttms_max: float,
    doms_min: float,
    doms_max: float,
    angle_deg: float,
) -> List[Case]:
    speeds = [float(speed_min), float(speed_max)]
    ttmss = [float(ttms_min), float(ttms_max)]
    domss = [float(doms_min), float(doms_max)]
    oops = [-1, 1]

    cases: List[Case] = []
    for doms, ttms, sp1, sp2, oop in itertools.product(domss, ttmss, speeds, speeds, oops):
        out = atc_dists_nm(doms, ttms, sp1, sp2, angle_deg, oop)
        if out is None:
            continue
        d1, d2, tc1, tc2, v1, v2, M = out
        cases.append(
            Case(
                label="corner",
                doms=doms,
                ttms=ttms,
                sp1=sp1,
                sp2=sp2,
                oop=oop,
                dist1=d1,
                dist2=d2,
                tcop1=tc1,
                tcop2=tc2,
                v1=v1,
                v2=v2,
                M=M,
            )
        )
    return cases


def select_extremes(cases: List[Case]) -> Dict[str, Case]:
    if not cases:
        raise SystemExit("No valid cases generated.")

    def max_abs_dist(c: Case):
        return max(abs(c.dist1), abs(c.dist2))

    def min_abs_dist(c: Case):
        return min(abs(c.dist1), abs(c.dist2))

    raw = {
        "MAX_RADIUS": max(cases, key=max_abs_dist),
        "MIN_RADIUS": min(cases, key=min_abs_dist),
        "MIN_TCOP1": min(cases, key=lambda c: c.tcop1),
        "MIN_TCOP2": min(cases, key=lambda c: c.tcop2),
    }

    out = {}
    for k, c in raw.items():
        out[k] = Case(k, c.doms, c.ttms, c.sp1, c.sp2, c.oop,
                      c.dist1, c.dist2, c.tcop1, c.tcop2, c.v1, c.v2, c.M)
    return out


# ----------------------------- Plotting ----------------------------------

def draw_radar(ax, W: int, H: int):
    cx, cy = 0.5 * W, 0.5 * H

    # background
    ax.add_patch(plt.Rectangle((0, 0), W, H, facecolor=BG_COLOR, edgecolor="none"))

    # --- full screen border (exact screen dimensions) ---
    screen_border = plt.Rectangle(
        (0, 0),
        W,
        H,
        fill=False,
        edgecolor="white",
        linewidth=1.5,
        linestyle="-",
        alpha=1.0,
        zorder=10,
    )
    ax.add_patch(screen_border)

    radar_radius = 0.5 * H

    # inside circle fill
    fill_circle = plt.Circle(
        (cx, cy),
        radar_radius,
        facecolor=BG_CIRCLE_COLOR,
        edgecolor="none",
        zorder=0,
    )
    ax.add_patch(fill_circle)

    # circle outline
    radar_circle = plt.Circle(
        (cx, cy),
        radar_radius,
        fill=False,
        edgecolor="white",
        linewidth=1.0,
        alpha=0.95,
    )
    ax.add_patch(radar_circle)

    ax.plot([cx], [cy], marker="+", markersize=21, color="white")

    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def analytic_max_start_radius_px(
    *,
    speed_min_kn: float,
    speed_max_kn: float,
    ttms_max_s: float,
    doms_max_nm: float,
    angle_deg: float,
    geom_scale: float,
) -> float:
    vmin = speed_min_kn / 3600.0
    vmax = speed_max_kn / 3600.0
    th = math.radians(angle_deg)

    sinth = abs(math.sin(th))
    if sinth < 1e-9:
        return float("inf")

    M_max = doms_max_nm * (2.0 * vmax) / (vmin * vmin * sinth)
    W_max = vmax * (1.0 + abs(math.cos(th)))
    A_min = 2.0 * vmin * vmin * (1.0 - math.cos(th))
    term_max = (vmax * M_max * W_max) / A_min

    tc1 = ttms_max_s + term_max
    tc2 = tc1 + M_max

    return vmax * max(tc1, tc2) * geom_scale


def plot_case(
    ax,
    c: Case,
    W: int,
    H: int,
    geom_scale: float,
    angle_deg: float,
    theta1_deg: float,
    circle_radius: float,
    r_max: float,
    r_min: float,
    *,
    color: str = "white",
    jitter_deg: float = 0.0,   # NEW
):
    cx, cy = 0.5 * W, 0.5 * H

    p1, p2, p1h, p2h = positions_from_dists(
        c.dist1, c.dist2, theta1_deg, angle_deg, W, H, geom_scale
    )

    # Rotate this entire extreme-case pair by a small angle
    if abs(jitter_deg) > 1e-12:
        phi = math.radians(jitter_deg)
        p1  = rotate_about_center(p1[0],  p1[1],  cx, cy, phi)
        p2  = rotate_about_center(p2[0],  p2[1],  cx, cy, phi)
        p1h = rotate_about_center(p1h[0], p1h[1], cx, cy, phi)
        p2h = rotate_about_center(p2h[0], p2h[1], cx, cy, phi)

    r1 = math.hypot(p1[0] - cx, p1[1] - cy)
    r2 = math.hypot(p2[0] - cx, p2[1] - cy)

    offscreen = max(r1, r2) > r_max
    too_close = min(r1, r2) < r_min
    neg_tcop = (c.tcop1 <= 0) or (c.tcop2 <= 0)

    lw = 1.2 if (offscreen or too_close or neg_tcop) else 0.7

    for (px, py), (hx, hy) in [(p1, p1h), (p2, p2h)]:
        ax.add_patch(
            plt.Circle((px, py), circle_radius, fill=False,
                       linewidth=lw, edgecolor=color)
        )
        ax.plot([px, hx], [py, hy], linewidth=lw, color=color)

    # ---- RIGHT SIDE INFO BLOCKS ----
    text = (
        f"{c.label}\n"
        f"doms={c.doms:g}, ttms={c.ttms:g}, oop={c.oop:+d}\n"
        f"sp1={c.sp1:g}, sp2={c.sp2:g}\n"
        f"TCOP1={c.tcop1:.2f}s, TCOP2={c.tcop2:.2f}s\n"
        f"r1={r1:.1f}px, r2={r2:.1f}px"
    )

    pad_right = 12
    y_map = {
        "MAX_RADIUS": 40,
        "MIN_RADIUS": 190,
        "MIN_TCOP1": 340,
        "MIN_TCOP2": 490,
    }

    ax.text(
        W - pad_right,
        y_map.get(c.label, 40),
        text,
        fontsize=9,
        family="monospace",
        color=color,        # match the case color
        va="top",
        ha="right",
    )

    return {"offscreen": offscreen, "too_close": too_close, "neg_tcop": neg_tcop}


def sample_and_plot_pairs(
    ax,
    *,
    n_samples: int,
    seed: Optional[int],
    speed_min: float,
    speed_max: float,
    ttms_min: float,
    ttms_max: float,
    doms_min: float,
    doms_max: float,
    angle_deg: float,
    theta1_deg: float,
    W: int,
    H: int,
    geom_scale: float,
    r_max: float,
    r_min: float,
) -> Dict[str, int]:
    rng = random.Random(seed)
    cx, cy = 0.5 * W, 0.5 * H

    xs_safe, ys_safe = [], []
    xs_bad, ys_bad = [], []

    n_safe = 0
    n_bad = 0
    n_valid = 0

    for _ in range(n_samples):
        doms = rng.uniform(doms_min, doms_max)
        ttms = rng.uniform(ttms_min, ttms_max)
        sp1 = rng.uniform(speed_min, speed_max)
        sp2 = rng.uniform(speed_min, speed_max)
        oop = rng.choice([-1, 1])

        out = atc_dists_nm(doms, ttms, sp1, sp2, angle_deg, oop)
        if out is None:
            continue

        d1, d2, tc1, tc2, *_ = out
        n_valid += 1

        p1, p2, _, _ = positions_from_dists(d1, d2, theta1_deg, angle_deg, W, H, geom_scale)

        phi = rng.uniform(0, 2 * math.pi)
        p1 = rotate_about_center(p1[0], p1[1], cx, cy, phi)
        p2 = rotate_about_center(p2[0], p2[1], cx, cy, phi)

        r1 = math.hypot(p1[0] - cx, p1[1] - cy)
        r2 = math.hypot(p2[0] - cx, p2[1] - cy)

        safe = (
            tc1 > 0 and tc2 > 0 and
            r1 <= r_max and r2 <= r_max and
            r1 >= r_min and r2 >= r_min
        )

        if safe:
            n_safe += 1
            xs_safe.extend([p1[0], p2[0]])
            ys_safe.extend([p1[1], p2[1]])
        else:
            n_bad += 1
            xs_bad.extend([p1[0], p2[0]])
            ys_bad.extend([p1[1], p2[1]])

    if xs_bad:
        ax.scatter(xs_bad, ys_bad, s=10, c="red", alpha=0.25, linewidths=0, zorder=1)
    if xs_safe:
        ax.scatter(xs_safe, ys_safe, s=10, c="white", alpha=0.25, linewidths=0, zorder=1)

    return {
        "requested": n_samples,
        "valid": n_valid,
        "pairs_safe": n_safe,
        "pairs_unsafe": n_bad,
        "dots_safe": len(xs_safe),
        "dots_unsafe": len(xs_bad),
    }


# ----------------------------- Main --------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--geom-scale", type=float, default=8.0)
    ap.add_argument("--circle-radius", type=float, default=10.0)

    ap.add_argument("--speed-min", type=float, required=True)
    ap.add_argument("--speed-max", type=float, required=True)
    ap.add_argument("--ttms-min", type=float, required=True)
    ap.add_argument("--ttms-max", type=float, required=True)

    ap.add_argument("--doms-min", type=float, default=0.0)
    ap.add_argument("--doms-max", type=float, default=10.0)
    ap.add_argument("--angle", type=float, default=90.0)

    ap.add_argument("--margin-px", type=float, default=10.0)
    ap.add_argument("--min-start-px", type=float, default=100.0)
    ap.add_argument("--theta1-deg", type=float, default=30.0)

    ap.add_argument("--n-samples", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=None)

    ap.add_argument("--out", type=str, default="atc_extremes.pdf")
    args = ap.parse_args()

    W, H = args.width, args.height
    cx, cy = 0.5 * W, 0.5 * H

    r_max = 0.5 * min(W, H) - (args.circle_radius + args.margin_px)
    r_min = args.min_start_px

    case_styles = {
        "MAX_RADIUS": dict(color="cyan",    jitter_deg=-6),
        "MIN_RADIUS": dict(color="yellow",  jitter_deg=-2),
        "MIN_TCOP1":  dict(color="magenta", jitter_deg=+2),
        "MIN_TCOP2":  dict(color="lime",    jitter_deg=+6),
    }

    cases = enumerate_corner_cases(
        args.speed_min, args.speed_max,
        args.ttms_min, args.ttms_max,
        args.doms_min, args.doms_max,
        args.angle,
    )
    extremes = select_extremes(cases)

    fig = plt.figure(figsize=(11, 6.5))
    fig.patch.set_facecolor(BG_COLOR)
    ax = fig.add_subplot(111)
    ax.set_facecolor(BG_COLOR)

    draw_radar(ax, W, H)

    stats = sample_and_plot_pairs(
        ax,
        n_samples=args.n_samples,
        seed=args.seed,
        speed_min=args.speed_min,
        speed_max=args.speed_max,
        ttms_min=args.ttms_min,
        ttms_max=args.ttms_max,
        doms_min=args.doms_min,
        doms_max=args.doms_max,
        angle_deg=args.angle,
        theta1_deg=args.theta1_deg,
        W=W, H=H,
        geom_scale=args.geom_scale,
        r_max=r_max,
        r_min=r_min,
    )

    r_env_px = analytic_max_start_radius_px(
        speed_min_kn=args.speed_min,
        speed_max_kn=args.speed_max,
        ttms_max_s=args.ttms_max,
        doms_max_nm=args.doms_max,
        angle_deg=args.angle,
        geom_scale=args.geom_scale,
    )

    ax.add_patch(plt.Circle((cx, cy), r_env_px, fill=False,
                            linewidth=2, color="white", alpha=0.9))

    ax.add_patch(plt.Circle((cx, cy), r_max, fill=False,
                            linestyle="--", linewidth=1.2, color="white", alpha=0.7))
    ax.add_patch(plt.Circle((cx, cy), r_min, fill=False,
                            linestyle=":", linewidth=1.2, color="white", alpha=0.7))

    # ---- LEFT INFO TEXT ----
    info_lines = [
        f"Samples: requested={stats['requested']}, valid={stats['valid']}",
        f"Pairs safe={stats['pairs_safe']}, unsafe={stats['pairs_unsafe']}",
        f"Dots plotted: safe={stats['dots_safe']}, unsafe={stats['dots_unsafe']}",
        "",  # <- one blank line requested
        f"Safe outer radius r_max={r_max:.1f}px",
        f"Safe inner radius r_min={r_min:.1f}px",
        f"GEOM_SCALE={args.geom_scale:g}",
        f"Analytic envelope: r_env={r_env_px:.1f}px",
    ]

    ax.text(
        10, 10,
        "\n".join(info_lines),
        fontsize=10,
        family="monospace",
        color="white",
        va="top",
    )

    flags_summary = []
    for key in ["MAX_RADIUS", "MIN_RADIUS", "MIN_TCOP1", "MIN_TCOP2"]:
        style = case_styles.get(key, {})
        flags_summary.append(
            (key, plot_case(
                ax,
                extremes[key],
                W, H,
                args.geom_scale,
                args.angle,
                args.theta1_deg,
                args.circle_radius,
                r_max,
                r_min,
                **style,  
            ))
        )


    def flag_txt(f):
        t = []
        if f["offscreen"]:
            t.append("OFFSCREEN")
        if f["too_close"]:
            t.append("TOO_CLOSE")
        if f["neg_tcop"]:
            t.append("NEG_TCOP")
        return "OK" if not t else ",".join(t)

    status = ["Flags:"]
    for k, f in flags_summary:
        status.append(f"  {k:10s}: {flag_txt(f)}")

    ax.text(
        10,
        H - 10,
        "\n".join(status),
        fontsize=10,
        family="monospace",
        color="white",
        va="bottom",
    )

    title = (
        "ATC geometry extreme cases (range corners)\n"
        f"speed=[{args.speed_min:g},{args.speed_max:g}] kn, "
        f"TTMS=[{args.ttms_min:g},{args.ttms_max:g}] s, "
        f"DOMS=[{args.doms_min:g},{args.doms_max:g}] nm, angle={args.angle:g}°"
    )
    ax.set_title(title, fontsize=12, color="white")

    fig.tight_layout()
    fig.savefig(args.out)
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()

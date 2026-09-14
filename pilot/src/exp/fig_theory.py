"""The active error-rate interval of Theorem 2, drawn from the closed forms.

Unlike every panel in ``figures.py`` this one reads no archived JSON: it is
the analytical illustration of the exponential--linear family at constants
the caption states as illustrative.  Nothing in the text quotes a number
from it, so it cannot disagree with the frozen table.  The closed-form
budget is still verified here against a brute-force grid argmin of J(b)
before anything is drawn.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np

from .figures import FIG_FONT_PT, TOL, _new_fig, _save

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FamilyParams:
    """Illustrative constants for the exponential--linear family.

    Time unit is one generation round (G = 1); tau0 = 0 so H = G.
    b_max = 3 matches the prototype's three coverage classes.
    """
    G: float = 1.0
    tau0: float = 0.0
    p_bar: float = 0.95
    alpha: float = 0.9
    beta: float = 0.05
    C_t: float = 1.0
    b_max: float = 3.0


def _lambert_w0_from_log(L: np.ndarray) -> np.ndarray:
    """Solve w + ln w = L for w > 0, i.e. w = W0(e^L).

    Working from ln(theta) avoids overflowing e^L, which happens whenever
    -alpha*c0/c1 is large -- the common case in the active region.
    """
    L = np.asarray(L, dtype=float)
    w = np.where(L > 1.0, L - np.log(np.maximum(L, 1.1)),
                 np.exp(np.clip(L, -700.0, 1.0)))
    for _ in range(80):
        f = w + np.log(w) - L
        step = f * w / (w + 1.0)
        w_new = w - step
        w = np.where(w_new > 0, w_new, w * 0.5)
    return w


def q_interval(R: float, fp: FamilyParams) -> Tuple[float, float]:
    """Active-interval endpoints (q-, q+) of Theorem 2; (nan, nan) if none."""
    H = fp.G + fp.tau0
    delta = fp.beta / (fp.p_bar * fp.alpha)
    disc = (R - H) ** 2 - 4.0 * R * delta
    if R <= H or disc <= 0:
        return (float("nan"), float("nan"))
    root = float(np.sqrt(disc))
    return ((R - H - root) / (2.0 * R), (R - H + root) / (2.0 * R))


def b_star_unbounded(q: np.ndarray, R: float, fp: FamilyParams) -> np.ndarray:
    """Closed-form unbounded optimum b*_inf(q) (Corollary 1); 0 if inactive."""
    q = np.asarray(q, dtype=float)
    C_v = R * fp.C_t
    H = fp.G + fp.tau0
    c0 = fp.alpha * ((q - 1.0) * C_v + H * fp.C_t) + fp.beta * fp.C_t
    c1 = fp.alpha * fp.beta * fp.C_t
    K = fp.beta * fp.C_t * (1.0 - q * fp.p_bar)
    # ln(theta), assembled in log space to survive large -alpha*c0/c1.
    logL = (np.log(fp.alpha * K) - np.log(q * fp.p_bar * c1)
            - fp.alpha * c0 / c1)
    b = -c0 / c1 - _lambert_w0_from_log(logL) / fp.alpha
    q_lo, q_hi = q_interval(R, fp)
    active = np.isfinite(q_lo) & (q > q_lo) & (q < q_hi)
    return np.where(active, np.maximum(b, 0.0), 0.0)


def _objective(b: np.ndarray, q: float, R: float,
               fp: FamilyParams) -> np.ndarray:
    """J(b) = C_v V(b) + C_t E[T(b)] for the family, C_t = fp.C_t."""
    p = fp.p_bar * (1.0 - np.exp(-fp.alpha * b))
    denom = 1.0 - q * p
    V = q * (1.0 - p) / denom
    ET = (fp.G + fp.tau0 + fp.beta * b) / denom
    return R * fp.C_t * V + fp.C_t * ET


def _check_closed_form(fp: FamilyParams, Rs: Tuple[float, ...],
                       tol: float = 2e-2) -> float:
    """Compare the Lambert-W budget with a grid argmin of J; raise on gap."""
    grid = np.linspace(0.0, 12.0, 12001)
    worst = 0.0
    for R in Rs:
        for q in np.linspace(0.02, 0.95, 15):
            b_closed = float(b_star_unbounded(np.array([q]), R, fp)[0])
            b_grid = float(grid[np.argmin(_objective(grid, q, R, fp))])
            worst = max(worst, abs(b_closed - b_grid))
    if worst > tol:
        raise ValueError(f"closed form disagrees with grid argmin by {worst}")
    logger.info("closed form vs grid argmin: max |diff| = %.2e", worst)
    return worst


def active_interval(out_base: Path,
                    fp: FamilyParams = FamilyParams(),
                    R_below: float = 1.4,
                    R_mid: float = 3.0,
                    R_high: float = 8.0) -> Dict[str, Any]:
    """Optimal budget against error rate q for three risk prices.

    One panel carries the three analytic facts: participation (below F_min
    the budget is identically zero), the active interval with strictly
    unimodal interior budget, and the b_max clipping that flattens the top.
    """
    worst = _check_closed_form(fp, (R_below, R_mid, R_high))

    q = np.linspace(0.001, 0.999, 2000)
    fig, ax = _new_fig(height_mm=48.0)
    fs = FIG_FONT_PT

    c_high, c_mid, c_low = TOL[0], TOL[1], TOL[5]

    # The paper's title object gets a visual body, not just boundary lines:
    # a light fill under the moderate curve over exactly (q-, q+).
    q_lo, q_hi = q_interval(R_mid, fp)
    b_mid = b_star_unbounded(q, R_mid, fp)
    inside = (q > q_lo) & (q < q_hi)
    ax.fill_between(q[inside], 0.0, b_mid[inside], color=c_mid, alpha=0.10,
                    linewidth=0, zorder=1)
    ax.annotate(r"active interval $(q_-,\,q_+)$",
                xy=((q_lo + q_hi) / 2, 0.95), fontsize=fs, color=c_mid,
                ha="center", va="center", alpha=0.9)

    # Clipping made literal: the region above b_max is physically
    # unavailable, so it is dimmed rather than implied by one dotted line.
    top = 5.25
    ax.fill_between([0.0, 1.0], fp.b_max, top, color="0.5", alpha=0.07,
                    linewidth=0, zorder=0)
    # Anchored at the left spine: centered text at 8 pt ran past it.
    ax.annotate(r"unavailable: clipped at $b_{\max}$", xy=(0.015, top - 0.12),
                fontsize=fs, color="0.45", ha="left", va="top")

    # R below the participation floor: identically zero.  Drawn wider than
    # the other two because all three curves sit on y=0 outside their own
    # active intervals; at 1.2 the higher-zorder green and indigo hid this
    # one entirely at both ends of the axis.
    ax.plot(q, np.zeros_like(q), color=c_low, linewidth=2.0, zorder=3)

    # Moderate R: interior unimodal optimum, never clipped.
    ax.plot(q, b_mid, color=c_mid, linewidth=1.2, zorder=4)

    # High R: clipped at b_max, unbounded optimum continued dashed.
    b_high = b_star_unbounded(q, R_high, fp)
    ax.plot(q, np.minimum(b_high, fp.b_max), color=c_high, linewidth=1.2,
            zorder=4)
    over = b_high > fp.b_max
    ax.plot(q[over], b_high[over], color=c_high, linewidth=0.9,
            linestyle="--", alpha=0.65, zorder=3)

    ax.axhline(fp.b_max, color="0.5", linewidth=0.6, linestyle=":", zorder=2)
    ax.annotate(r"$b_{\max}$", xy=(0.985, fp.b_max), xytext=(0, 2),
                textcoords="offset points", fontsize=fs, color="0.35",
                ha="right", va="bottom")

    # Name the endpoints of the moderate curve's active interval.  q- sits
    # against the left spine, so its label goes to the right of the line.
    for qq, name, ha in ((q_lo, r"$q_-$", "left"), (q_hi, r"$q_+$", "center")):
        ax.vlines(qq, 0.0, 1.05, color=c_mid, linewidth=0.9,
                  linestyle=":", alpha=0.95, zorder=2)
        ax.annotate(name, xy=(qq, 1.05), xytext=(2 if ha == "left" else 0, 2),
                    textcoords="offset points", fontsize=fs, color=c_mid,
                    ha=ha, va="bottom")

    peak_mid = float(b_mid.max())
    peak_high = float(b_high.max())
    ax.annotate(rf"$R={R_high:g}$ (clipped)", xy=(0.62, fp.b_max),
                xytext=(0, 3), textcoords="offset points", fontsize=fs,
                color=c_high, ha="center", va="bottom")
    ax.annotate(rf"$b^\star_\infty$", color=c_high, fontsize=fs, alpha=0.8,
                xy=(float(q[np.argmax(b_high)]), peak_high),
                xytext=(0, 2), textcoords="offset points", ha="center",
                va="bottom")
    ax.annotate(rf"$R={R_mid:g}$", xy=(float(q[np.argmax(b_mid)]), peak_mid),
                xytext=(2, 3), textcoords="offset points", fontsize=fs,
                color=c_mid, ha="left", va="bottom")
    # The label belongs to the flat-zero rose line.  Below the line there is
    # no room -- the text ran into the line above and off the axis below -- so
    # it sits just over it, inside the pale fill and well under the dome.
    ax.annotate(rf"$R={R_below:g}<F_{{\min}}$: never verify",
                xy=(0.335, 0.10), fontsize=fs, color=c_low,
                ha="center", va="bottom")

    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(-0.18, top)
    ax.set_xlabel(r"Conditioned plan error rate $q$")
    ax.set_ylabel(r"Optimal budget $b^\star$")
    ax.grid(True, linewidth=0.3, alpha=0.35)
    fig.tight_layout(pad=0.3)
    _save(fig, out_base, width="single", height_mm=48)

    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"params": vars(fp) | {"R": [R_below, R_mid, R_high]},
            "q_interval_mid": [round(q_lo, 4), round(q_hi, 4)],
            "q_interval_high": [round(v, 4)
                                for v in q_interval(R_high, fp)],
            "peak_mid": round(peak_mid, 3),
            "peak_high_unbounded": round(peak_high, 3),
            "closed_form_check_max_diff": worst}


__all__ = ["FamilyParams", "active_interval", "b_star_unbounded",
           "q_interval"]

"""Paper figures built from archived result JSON.

Every figure reads a file produced by a runner; none recomputes anything, so
a figure can never disagree with the numbers in the text.

IEEE column widths differ slightly from the journal specs pubfig ships
(88.9/181.9 mm rather than 89/183), and IEEEtran sets Times, so an ``ieee``
spec is registered rather than borrowing ``nature``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pubfig
from pubfig import FigureSpec

logger = logging.getLogger(__name__)

IEEE = FigureSpec(name="ieee", font_family="Times New Roman", design_dpi=96,
                  single_column_mm=88.9, double_column_mm=181.9,
                  default_raster_dpi=600, background_color="#FFFFFF")


def ensure_ieee_spec() -> None:
    """Register the IEEE column geometry once."""
    if "ieee" not in pubfig.list_figure_specs():
        pubfig.register_figure_spec("ieee", IEEE)


MM_PER_IN = 25.4

# Paul Tol muted palette as used by Science; colorblind-safe and
# grayscale-distinguishable.  New figures draw from this list.
TOL = ["#332288", "#117733", "#44AA99", "#88CCEE",
       "#DDCC77", "#CC6677", "#AA4499", "#882255"]

# IEEE body text is 10 pt; figure text must stay legible at column width
# without overpowering the panel.
RC = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "font.size": 7,
    "axes.labelsize": 7,
    "axes.titlesize": 7,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.minor.width": 0.4,
    "ytick.minor.width": 0.4,
    "lines.linewidth": 1.0,
    "mathtext.fontset": "stix",
}


def _new_fig(width_mm: float = IEEE.single_column_mm,
             height_mm: float = 62.0):
    """A figure created at its FINAL physical size.

    Building at matplotlib's default size and rescaling on export enlarges
    every glyph by the same factor, which is why an otherwise correct panel
    comes out with labels dominating the plot area.
    """
    plt.rcParams.update(RC)
    return plt.subplots(figsize=(width_mm / MM_PER_IN,
                                 height_mm / MM_PER_IN))


def _save(fig: Any, base: Path, width: str = "single",
          height_mm: Optional[float] = None) -> None:
    ensure_ieee_spec()
    base.parent.mkdir(parents=True, exist_ok=True)
    # PDF for LaTeX inclusion, PNG so the figure can be eyeballed quickly.
    pubfig.batch_export(fig, str(base), formats=("pdf", "png"), spec="ieee",
                        width=width, height_mm=height_mm, dpi=600)
    logger.info("wrote %s.{pdf,png}", base)


# --------------------------------------------------------------------------
# Figure 1: verification cost against topology size
# --------------------------------------------------------------------------

def tau_scaling(costbench_json: Path, out_base: Path,
                series: Sequence[Tuple[str, str, int, str]] = (
                    ("smt", "prefix", 1, "SMT, $b{=}1$"),
                    ("smt", "prefix", 3, "SMT, $b{=}3$"),
                    ("twin", "prefix", 1, "Twin, $b{=}1$"),
                    ("twin", "prefix", 3, "Twin, $b{=}3$"),
                )) -> Dict[str, Any]:
    """Verification time versus node count, log-log, one line per profile.

    Log-log because both axes span more than a decade: hiding that on linear
    axes would flatten the very growth the cost model is about.
    """
    data = json.loads(costbench_json.read_text())
    by_net = {r["network"]: r for r in data["results"] if "skipped" not in r}
    nets = sorted(by_net, key=lambda n: by_net[n]["n_nodes"])
    xs = np.array([by_net[n]["n_nodes"] for n in nets], dtype=float)

    fig, ax = _new_fig(height_mm=62.0)
    colors = pubfig.get_palette("default")
    markers = ["o", "s", "^", "D", "v", "*"]

    exponents: Dict[str, float] = {}
    grid = np.linspace(np.log(xs.min()), np.log(xs.max()), 50)
    for i, (mode, e, b, label) in enumerate(series):
        ys = np.array([
            next((r["tau_envelope_ms"] for r in by_net[n]["rows"]
                  if r["mode"] == mode and r["e"] == e and r["b"] == b),
                 np.nan) for n in nets], dtype=float)
        c = colors[i % len(colors)]
        # Points, not a polyline: these are 26 independent networks, and
        # joining them would draw a trajectory that does not exist. The
        # vertical spread at equal node count is real -- cost tracks
        # topology density, not node count alone.
        ax.scatter(xs, ys, s=9, marker=markers[i % len(markers)], color=c,
                   alpha=0.85, linewidths=0, zorder=3)
        ok = np.isfinite(ys)
        slope, intercept = np.polyfit(np.log(xs[ok]), np.log(ys[ok]), 1)
        exponents[f"{mode}/b{b}"] = float(slope)
        ax.plot(np.exp(grid), np.exp(intercept + slope * grid), "-",
                color=c, linewidth=0.9, alpha=0.8,
                label=rf"{label}  ($\propto N^{{{slope:.2f}}}$)")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Network size (nodes)")
    ax.set_ylabel(r"Verification time $\tau$ (ms)")
    ax.legend(frameon=False, loc="upper left", handlelength=1.6,
              borderaxespad=0.3, labelspacing=0.25)
    ax.grid(True, which="major", linewidth=0.3, alpha=0.35)
    fig.tight_layout(pad=0.3)
    _save(fig, out_base, width="single", height_mm=62)
    plt.close(fig)
    return {"n_networks": len(nets),
            "node_range": [float(xs.min()), float(xs.max())],
            "fitted_exponents": {k: round(v, 3)
                                 for k, v in exponents.items()}}


# --------------------------------------------------------------------------
# Figure 2: leave-one-topology-out profile selection
# --------------------------------------------------------------------------

def selection_vs_risk(selection_json: Path, out_base: Path) -> Dict[str, Any]:
    """Objective under the calibrated rule versus fixed-profile baselines.

    Log axes on both: the risk price is swept over decades, and the
    always-shallowest baseline diverges by orders of magnitude at the high
    end, which is the point of the panel.
    """
    data = json.loads(selection_json.read_text())
    rows = data["summary"]
    R = np.array([r["R"] for r in rows], dtype=float)

    fig, ax = _new_fig(height_mm=62.0)
    plots = [
        ("J_always_shallowest", "Fixed shallow ($b{=}1$)", "--", "^"),
        ("J_always_deepest", "Fixed deep ($b{=}3$)", "--", "s"),
        ("J_selected", "Selected (LOTO)", "-", "o"),
        # Named as the paper names it. The reference is the best profile
        # under the held-out topology's own primitives substituted into the
        # same closed form, not the outcome of running the loop under every
        # profile, and a legend reading "held-out best" invites the second
        # reading.
        ("J_oracle", "Plug-in oracle", ":", None),
    ]
    colors = pubfig.get_palette("default")
    for i, (key, label, ls, mk) in enumerate(plots):
        ys = np.array([r[key] for r in rows], dtype=float)
        ax.plot(R, ys, ls, marker=mk, markersize=3.2, linewidth=1.2,
                label=label, color=colors[i % len(colors)],
                alpha=0.95)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"Risk price $R = C_v / C_t$")
    ax.set_ylabel(r"Objective $J$ (lower is better)")
    ax.legend(frameon=False, loc="upper left", handlelength=1.8,
              borderaxespad=0.3, labelspacing=0.25)
    ax.grid(True, which="major", linewidth=0.3, alpha=0.35)

    # Mark where the calibrated rule switches profile: the switch, not the
    # level, is what distinguishes selection from any fixed policy.
    prev = None
    for r in rows:
        cur = ",".join(r["selected_profiles"])
        if prev is not None and cur != prev:
            ax.axvline(r["R"], color="0.5", linewidth=0.6, linestyle="-.",
                       alpha=0.8)
            ax.annotate(f"switch to {cur}", xy=(r["R"], ax.get_ylim()[0]),
                        xytext=(3, 4), textcoords="offset points",
                        fontsize=5, color="0.35", rotation=90,
                        va="bottom", ha="left")
        prev = cur

    fig.tight_layout(pad=0.3)
    _save(fig, out_base, width="single", height_mm=62)
    plt.close(fig)
    return {"n_R": len(rows),
            "profiles": sorted({p for r in rows
                                for p in r["selected_profiles"]})}


# --------------------------------------------------------------------------
# Figure 3: safety-utility trade-off across policies
# --------------------------------------------------------------------------

def safety_utility_pareto(policy_json: Path, out_base: Path) -> Dict[str, Any]:
    """Unsafe actuation against safe completion, one point per policy.

    Both axes are outcomes, so a policy in the lower right is better on both.
    Plotting them together prevents reading either alone -- an abort-only
    policy sits at the origin, safe and useless.
    """
    data = json.loads(policy_json.read_text())
    # Prefer the feasible-intent slice when present: on infeasible intents a
    # correct system must abort, so including them mixes "did not complete
    # because it was impossible" into a utility metric.
    src = data.get("by_group", {}).get("feasible") or data["policies"]
    pols = {k: v for k, v in src.items() if v.get("n")}
    if not pols:
        raise ValueError("no policies with data")
    scope = ("feasible intents"
             if data.get("by_group", {}).get("feasible") else "all intents")

    fig, ax = _new_fig(height_mm=50.0)
    colors = TOL

    # Several policies land on exactly the same point -- that coincidence is
    # a result, not a plotting problem, so group them and label the group
    # rather than hiding identical markers under one another.
    groups: Dict[Tuple[float, float], List[str]] = {}
    for name, s in sorted(pols.items()):
        key = (round(s["safe_completion"]["rate"], 4),
               round(s["modeled_unsafe_actuation"]["rate"], 4))
        groups.setdefault(key, []).append(name)

    xs = [k[0] for k in groups]
    ys = [k[1] for k in groups]
    mid_x = (min(xs) + max(xs)) / 2 if len(xs) > 1 else xs[0]
    for i, ((x, y), names) in enumerate(sorted(groups.items())):
        ax.scatter([x], [y], s=30, marker="o", color=colors[i % len(colors)],
                   zorder=3, edgecolors="white", linewidths=0.5)
        label = "\n".join(n.replace("verify:smt/", "") for n in names)
        # Labels point away from the centre of mass so neighbouring groups
        # cannot collide, which they do when every label is offset the same
        # way and two groups sit close together.
        right = x < mid_x
        ax.annotate(label, xy=(x, y),
                    xytext=(5 if right else -5, 5 if right else -4),
                    textcoords="offset points", fontsize=5,
                    color=colors[i % len(colors)],
                    va="bottom" if right else "top",
                    ha="left" if right else "right")

    ax.set_xlabel(f"Safe completion rate ({scope})")
    ax.set_ylabel("Modeled unsafe actuation rate")
    # Padding asymmetric to the right only far enough to hold the widest
    # label. The panel was previously ~70% empty, which cost column height
    # without carrying information: six points do not need a wide canvas.
    pad_x = 0.10 * max(1e-6, max(xs) - min(xs))
    ax.set_xlim(min(xs) - pad_x, max(xs) + 1.6 * pad_x)
    # Headroom sized for the labels, not the markers: the tallest group
    # carries three coincident policies and is anchored above its point, so
    # a limit set from the data alone pushes that text through the spine.
    tallest = max(len(v) for v in groups.values())
    ax.set_ylim(-0.105, max(ys) * (1.0 + 0.145 * tallest))
    ax.grid(True, linewidth=0.3, alpha=0.35)
    # Axes-fraction coordinates so the cue follows the data-driven limits.
    # Kept in the empty upper-right quadrant, clear of every labelled group.
    ax.annotate("better", xy=(0.93, 0.42), xytext=(0.70, 0.80),
                xycoords="axes fraction", textcoords="axes fraction",
                fontsize=5.5, color="0.4",
                arrowprops={"arrowstyle": "->", "color": "0.55",
                            "linewidth": 0.6})
    fig.tight_layout(pad=0.3)
    _save(fig, out_base, width="single", height_mm=50)
    plt.close(fig)
    return {"n_policies": len(pols)}


def cost_ratio_scaling(crossover_json: Path, out_base: Path) -> Dict[str, Any]:
    """Reservation verification time as a fraction of a round, versus size.

    Both terms are measured in the same run on the same topology, because the
    quantity is a ratio and mixing measurement conditions is how a crossover
    gets manufactured. Published instances and synthetic scalability rungs
    are drawn distinctly: the latter probe where the trend leads, and are not
    a sample from any deployed topology distribution.
    """
    data = json.loads(crossover_json.read_text())
    rows = [r for r in data["rows"] if r.get("ratio_smt") is not None]
    pub = [r for r in rows if r["class"] == "published"]
    stress = [r for r in rows if r["class"] == "stress"]

    fig, ax = _new_fig(height_mm=62.0)
    colors = pubfig.get_palette("default")
    for group, label, marker, colour in (
            (pub, "Published instances", "o", colors[0]),
            (stress, "Synthetic stress rungs", "^", colors[3])):
        if not group:
            continue
        xs = [r["n_predicates"] for r in group]
        ys = [r["ratio_smt"] for r in group]
        ax.scatter(xs, ys, s=16, marker=marker, color=colour, zorder=3,
                   label=label, edgecolors="white", linewidths=0.4)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Predicate instances in the state")
    ax.set_ylabel(r"$\tau$ / round (reservation)")
    ax.axhline(0.1, color="0.6", linewidth=0.6, linestyle="--")
    ax.annotate("10% of a round", xy=(0.02, 0.1), xycoords=("axes fraction",
                                                            "data"),
                fontsize=5, color="0.4", va="bottom")
    ax.legend(frameon=False, loc="upper left", handletextpad=0.3,
              borderaxespad=0.3)
    ax.grid(True, which="major", linewidth=0.3, alpha=0.35)
    fig.tight_layout(pad=0.3)
    _save(fig, out_base, width="single", height_mm=62)
    plt.close(fig)
    return {"n_published": len(pub), "n_stress": len(stress),
            "ratio_range": [min(r["ratio_smt"] for r in rows),
                            max(r["ratio_smt"] for r in rows)]}


__all__ = ["IEEE", "TOL", "cost_ratio_scaling", "ensure_ieee_spec",
           "safety_utility_pareto", "selection_vs_risk", "tau_scaling"]

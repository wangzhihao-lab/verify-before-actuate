"""Fit the assumed technology family to the measured detection curve.

The renewal results are derived for an exponential detection / linear latency
family. Whether that family describes the measured curve is an empirical
question, and answering it needs three things the earlier three-level
instantiation could not provide: enough budget points, a likelihood rather
than least squares on rates, and a nonparametric baseline to be compared
against.

Protocol:
  * detection counts (k, n) per topology per budget, scored against the
    common full-coverage loss event;
  * exponential family p(b) = pbar * (1 - exp(-alpha*b)) fitted by BINOMIAL
    maximum likelihood, not by regression on rates -- rates near 0 and 1 have
    very unequal variance and least squares ignores that;
  * an isotonic (monotone, nonparametric) baseline fitted by pool-adjacent-
    violators, which is the most permissive monotone model and therefore the
    right yardstick;
  * leave-one-topology-out: fit on nine, score held-out deviance on the
    tenth. A parametric family that only wins in-sample has not earned the
    role it plays in the theory.

The budget point b = 1 is excluded from fitting: at full coverage the checker
IS the reference oracle, so p = 1 there by definition rather than by
technology, and an exponential form cannot reach 1 at finite b.

    PYTHONPATH=. .venv/bin/python run_fit.py --corpus out/corpus_v2
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from src.coverage import budget_count, predicate_instances
from src.exp.analyze import (conditioned, load_records, load_states, usable)
from src.provenance import run_meta
from src.semantics import is_common_loss
from src.verify_frac import frac_verify

logger = logging.getLogger("run_fit")

EPS = 1e-12


# --------------------------------------------------------------------------
# likelihood machinery
# --------------------------------------------------------------------------

def binom_loglik(counts: Sequence[Tuple[float, int, int]],
                 predict) -> float:
    """Sum of binomial log-likelihoods for (budget, detected, total) rows."""
    total = 0.0
    for b, k, n in counts:
        p = min(1.0 - EPS, max(EPS, predict(b)))
        total += k * math.log(p) + (n - k) * math.log(1.0 - p)
    return total


def deviance(counts: Sequence[Tuple[float, int, int]], predict) -> float:
    """Residual deviance against the saturated model; lower is better."""
    dev = 0.0
    for b, k, n in counts:
        p = min(1.0 - EPS, max(EPS, predict(b)))
        phat = k / n if n else 0.0
        for obs, q in ((k, p), (n - k, 1 - p)):
            pass
        t = 0.0
        if k:
            t += k * math.log(max(EPS, phat) / p)
        if n - k:
            t += (n - k) * math.log(max(EPS, 1 - phat) / (1 - p))
        dev += 2 * t
    return dev


def fit_exponential(counts: Sequence[Tuple[float, int, int]]
                    ) -> Tuple[float, float, float]:
    """Binomial MLE for p(b) = pbar*(1-exp(-alpha*b)). Returns (pbar, alpha, ll).

    A coarse grid followed by local refinement: two parameters, a smooth
    likelihood, and no scipy dependency in this environment.
    """
    best = (0.5, 1.0, -math.inf)
    grid_p = [0.50 + 0.01 * i for i in range(51)]        # 0.50 .. 1.00
    grid_a = [0.1 * i for i in range(1, 121)]            # 0.1 .. 12.0
    for pbar in grid_p:
        for alpha in grid_a:
            ll = binom_loglik(
                counts, lambda b, pb=pbar, al=alpha: pb * (1 - math.exp(-al * b)))
            if ll > best[2]:
                best = (pbar, alpha, ll)
    pbar, alpha, ll = best
    for scale in (0.01, 0.002):
        for dp in (-2, -1, 0, 1, 2):
            for da in (-2, -1, 0, 1, 2):
                cp = min(1.0, max(0.3, pbar + dp * scale))
                ca = max(0.01, alpha + da * scale * 20)
                cand = binom_loglik(
                    counts,
                    lambda b, pb=cp, al=ca: pb * (1 - math.exp(-al * b)))
                if cand > ll:
                    pbar, alpha, ll = cp, ca, cand
    return pbar, alpha, ll


def fit_isotonic(counts: Sequence[Tuple[float, int, int]]):
    """Pool-adjacent-violators monotone fit; returns a step predictor.

    Rows at the SAME budget are aggregated before the PAV sweep. Without
    that, the ten per-topology rows at one budget enter as ten separate
    blocks; PAV leaves any of them that happen to arrive in increasing-rate
    order unmerged, so the baseline acquires a per-topology degree of freedom
    that the exponential family -- a function of b alone -- does not have,
    and the step predictor then returns whichever tied block sorted last.
    That is not the monotone-in-b yardstick this comparison needs.
    """
    agg: Dict[float, List[float]] = {}
    for b, k, n in counts:
        cell = agg.setdefault(float(b), [0.0, 0.0])
        cell[0] += k
        cell[1] += n
    rows = [(b, kn[0], kn[1]) for b, kn in sorted(agg.items())]
    blocks = [[b, float(k), float(n)] for b, k, n in rows]
    changed = True
    while changed:
        changed = False
        for i in range(len(blocks) - 1):
            left, right = blocks[i], blocks[i + 1]
            if left[1] / max(EPS, left[2]) > right[1] / max(EPS, right[2]):
                merged = [right[0], left[1] + right[1], left[2] + right[2]]
                blocks[i:i + 2] = [merged]
                changed = True
                break
    bounds = [(blk[0], blk[1] / max(EPS, blk[2])) for blk in blocks]

    def predict(b: float) -> float:
        out = bounds[0][1]
        for edge, val in bounds:
            if b >= edge - 1e-9:
                out = val
        return out
    return predict, bounds


def fit_linear_tau(points: Sequence[Tuple[float, float]]
                   ) -> Tuple[float, float, float]:
    """Least squares tau(b) = tau0 + beta*b, with R^2."""
    n = len(points)
    if n < 2:
        return 0.0, 0.0, 0.0
    mx = statistics.mean(p[0] for p in points)
    my = statistics.mean(p[1] for p in points)
    sxx = sum((p[0] - mx) ** 2 for p in points)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    beta = sxy / sxx if sxx else 0.0
    tau0 = my - beta * mx
    ss_tot = sum((p[1] - my) ** 2 for p in points)
    ss_res = sum((p[1] - (tau0 + beta * p[0])) ** 2 for p in points)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return tau0, beta, r2


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def detection_counts(corpus: Path, fracs: Sequence[float], order: str,
                     e: str) -> Dict[str, List[Tuple[float, int, int]]]:
    """Per-topology (budget, detected, n_loss) rows.

    Conditioned exactly as ``q`` and as the profile selector are: a-priori
    feasible intents whose plan fulfils them. The renewal model's ``p`` is
    the detection rate within the population its ``q`` is drawn from, so
    scoring it over every unsafe plan -- including infeasible requests the
    loop is designed to refuse -- would put the two primitives on different
    denominators.
    """
    records = load_records(corpus / "records.jsonl")
    states = load_states(corpus / "states")
    by_net: Dict[str, List[Tuple[Any, Any]]] = {}
    for rec in records:
        if not usable(rec) or rec["network"] not in states:
            continue
        if not conditioned(rec):
            continue
        st = states[rec["network"]]
        if is_common_loss(st, rec["plan"]):
            by_net.setdefault(rec["network"], []).append((st, rec["plan"]))

    out: Dict[str, List[Tuple[float, int, int]]] = {}
    for net, plans in sorted(by_net.items()):
        rows = []
        for frac in fracs:
            det = sum(1 for st, pl in plans
                      if frac_verify(st, pl, e=e, frac=frac, order=order,
                                     mode="checker")[0] == "REJECT")
            rows.append((frac, det, len(plans)))
        out[net] = rows
        logger.info("%s: %d loss events", net, len(plans))
    return out


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="out/corpus_v2")
    p.add_argument("--order", default="interleaved",
                   choices=("class", "interleaved"))
    p.add_argument("--points", type=int, default=20)
    p.add_argument("--e", default="prefix", choices=("prefix", "term"))
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus)
    # b = 1 excluded: full coverage is the oracle by definition.
    fracs = [round(i / (args.points + 1), 4)
             for i in range(1, args.points + 1)]
    counts = detection_counts(corpus, fracs, args.order, args.e)
    nets = sorted(counts)
    pooled = [r for net in nets for r in counts[net]]

    pbar, alpha, ll = fit_exponential(pooled)
    iso, iso_blocks = fit_isotonic(pooled)
    exp_pred = lambda b: pbar * (1 - math.exp(-alpha * b))
    logger.info("pooled exponential fit: pbar=%.4f alpha=%.3f", pbar, alpha)
    logger.info("pooled deviance  exponential=%.1f  isotonic=%.1f",
                deviance(pooled, exp_pred), deviance(pooled, iso))

    # Leave-one-topology-out held-out deviance: the honest comparison.
    loto = []
    for held in nets:
        train = [r for net in nets if net != held for r in counts[net]]
        test = counts[held]
        pb, al, _ = fit_exponential(train)
        iso_tr, _ = fit_isotonic(train)
        d_exp = deviance(test, lambda b, pb=pb, al=al:
                         pb * (1 - math.exp(-al * b)))
        d_iso = deviance(test, iso_tr)
        loto.append({"held_out": held, "pbar": round(pb, 4),
                     "alpha": round(al, 3),
                     "deviance_exponential": round(d_exp, 2),
                     "deviance_isotonic": round(d_iso, 2),
                     "exponential_better": d_exp < d_iso})
    n_better = sum(1 for r in loto if r["exponential_better"])

    tau_src = corpus / f"pcurve_{args.order}.json"
    tau_fit = None
    if tau_src.exists():
        pts = [(r["frac"], r["tau_mean_ms"])
               for r in json.loads(tau_src.read_text())["rows"]
               if r.get("tau_mean_ms") is not None and r["frac"] < 1.0]
        t0, beta, r2 = fit_linear_tau(pts)
        tau_fit = {"tau0_ms": round(t0, 4), "beta_ms": round(beta, 4),
                   "r2": round(r2, 4), "n_points": len(pts)}
        logger.info("tau linear fit: tau0=%.2fms beta=%.2fms R2=%.4f",
                    t0, beta, r2)

    # The sweep axis is a fraction of each topology's own base predicate
    # count, so one point on the pooled curve is a different absolute number
    # of predicate evaluations on each topology. Record the mapping rather
    # than let the axis be read as a single physical budget.
    states_for_n = load_states(corpus / "states")
    n_base = {net: len(predicate_instances(st))
              for net, st in sorted(states_for_n.items()) if net in counts}
    counts_at_frac = {
        f"{f}": {net: budget_count(nb, f) for net, nb in n_base.items()}
        for f in fracs}

    payload = {
        "meta": run_meta({"corpus": str(corpus), "order": args.order,
                          "e": args.e, "n_budget_points": len(fracs)}),
        "fracs": fracs,
        "n_predicate_instances_per_topology": n_base,
        "absolute_budget_at_each_frac": counts_at_frac,
        "axis_note": ("b is a FRACTION of each topology's base predicate "
                      "instance count; the same frac is a different absolute "
                      "count on each topology, and the budget is integer, so "
                      "the fitted curve is finely discretised, not C^1"),
        "pooled_exponential": {"pbar": round(pbar, 4),
                               "alpha": round(alpha, 3),
                               "loglik": round(ll, 2),
                               "deviance": round(deviance(pooled, exp_pred), 2)},
        "pooled_isotonic": {"deviance": round(deviance(pooled, iso), 2),
                            "n_blocks": len(iso_blocks)},
        "loto": loto,
        "n_folds_exponential_better": n_better,
        "n_folds": len(loto),
        "tau_linear": tau_fit,
        "counts_per_topology": {k: v for k, v in counts.items()},
        "note": ("b=1 excluded from fitting: at full coverage the checker is "
                 "the reference oracle, so p=1 holds by definition and no "
                 "exponential form reaches 1 at finite b"),
    }
    dest = Path(args.out) if args.out else corpus / f"fit_{args.order}.json"
    dest.write_text(json.dumps(payload, indent=1))

    print(f"\nexponential family  pbar={pbar:.4f}  alpha={alpha:.3f}")
    print(f"pooled deviance     exponential={deviance(pooled, exp_pred):.1f}"
          f"   isotonic={deviance(pooled, iso):.1f}")
    print(f"\nheld-out deviance (leave one topology out):")
    print(f"{'held out':<16}{'exp':>10}{'isotonic':>11}  exp better?")
    for r in loto:
        print(f"{r['held_out']:<16}{r['deviance_exponential']:>10.2f}"
              f"{r['deviance_isotonic']:>11.2f}  {r['exponential_better']}")
    print(f"\nexponential beats isotonic out of sample in "
          f"{n_better}/{len(loto)} folds")
    if tau_fit:
        print(f"tau(b) = {tau_fit['tau0_ms']:.2f} + {tau_fit['beta_ms']:.2f}b "
              f"ms   R^2={tau_fit['r2']:.4f}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

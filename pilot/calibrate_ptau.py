"""DEPRECATED (R3, 2026-07-23) — superseded by microbench_ptau.py.

Do NOT run for evidence. This version (a) shrank the p denominator per (e,b)
[spurious p=1], (b) measured tau on VIOLATING plans where early-reject makes
it non-monotone (violates theory A2), and (c) saved only 6 aggregate rows.
Kept for provenance only. Use microbench_ptau.py (fixed shared ¬Safe_prefix
denominator, tau on clean full-traversal plans, per-plan raw + commit SHA).

--- original docstring below ---
Matched calibration of (p, tau) for both verification modes.

On a FIXED topology and a FIXED corpus of plans (a controlled violation
taxonomy + clean plans), measure for each mode m in {SMT, TWIN}, execution
e in {term, prefix}, budget b in {1,2,3}:
  - detection rate p over the violating corpus (per (e,m,b))
  - mean solve/sim time tau over the whole corpus (per (e,m,b))
  - twin/smt cross-check: identical ACCEPT/REJECT verdicts (coverage-equiv)

This replaces the pilot's exploratory p(d)/tau: same corpus, both modes,
saved raw. NO LLM calls. Output: out/calib_<stamp>/calib.json + table.
"""
from __future__ import annotations

import json
import platform
import random
import statistics
import time
from pathlib import Path

from run_p_inject import build_injections
from src.netmodel import gen_topology
from src.smt_verify import smt_verify
from src.twin_verify import twin_verify

REPEAT = 5  # timing repeats; report median


def clean_plans(base, rng, n=12):
    out = []
    flows = list(base.flows)
    for _ in range(n):
        f = rng.choice(flows)
        out.append([{"op": "set_flow_bw", "flow": f,
                     "bw_mbps": base.flows[f]["bw"]}])  # no-op-ish, safe
    return out


def main() -> None:
    seed = 42
    base = gen_topology(random.Random(seed), 24, 14, 40)
    rng = random.Random(seed)
    viol = [(f"inj_{i}", p) for i, (_, p) in
            enumerate(build_injections(base))]
    clean = [(f"clean_{i}", p) for i, p in
             enumerate(clean_plans(base, rng))]
    corpus = viol + clean

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path("out") / f"calib_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    verdict_disagree = 0
    for e in ("term", "prefix"):
        for b in (1, 2, 3):
            det_smt = det_twin = 0
            t_smt, t_twin = [], []
            for name, plan in corpus:
                # median timing over REPEAT runs
                os_, ot_ = [], []
                for _ in range(REPEAT):
                    o_s, _, ts = smt_verify(base, plan, e=e, b=b)
                    o_t, _, tt = twin_verify(base, plan, e=e, b=b)
                    os_.append(ts); ot_.append(tt)
                t_smt.append(statistics.median(os_))
                t_twin.append(statistics.median(ot_))
                if o_s != o_t:
                    verdict_disagree += 1
                if name.startswith("inj"):
                    det_smt += o_s == "REJECT"
                    det_twin += o_t == "REJECT"
            nv = len(viol)
            row = {"e": e, "b": b,
                   "p_smt": det_smt / nv, "p_twin": det_twin / nv,
                   "tau_smt_ms": 1e3 * statistics.mean(t_smt),
                   "tau_twin_ms": 1e3 * statistics.mean(t_twin),
                   "n_viol": nv, "n_corpus": len(corpus)}
            rows.append(row)
            print(f"e={e:<6} b={b}  p_smt={row['p_smt']:.2f} "
                  f"p_twin={row['p_twin']:.2f}  "
                  f"tau_smt={row['tau_smt_ms']:.2f}ms "
                  f"tau_twin={row['tau_twin_ms']:.2f}ms")

    meta = {"seed": seed, "topology": "24n/14chord/40flow",
            "repeat": REPEAT, "python": platform.python_version(),
            "verdict_disagreements_smt_vs_twin": verdict_disagree,
            "corpus": {"violating": len(viol), "clean": len(clean)}}
    (out_dir / "calib.json").write_text(json.dumps(
        {"meta": meta, "rows": rows}, indent=1))
    print(f"\nSMT vs TWIN verdict disagreements: {verdict_disagree} "
          f"(expect 0 = coverage-equivalent on toy)")
    print(f"-> {out_dir}/calib.json")


if __name__ == "__main__":
    main()

"""Coverage/cost MICROBENCHMARK for the two verification modes.

NOT a parameter calibration (R3): a controlled microbenchmark that reports,
with per-plan raw saved:
  - p(e,b) = detection rate over plans that are ACTUALLY ¬Safe_e (per-e
    ground truth, so a transient-only violation is NOT counted against
    terminal mode);
  - tau(e,b) = verification time measured ONLY on CLEAN (ACCEPT) plans, i.e.
    full-traversal cost, so early-reject shortcuts on violating plans do not
    corrupt the cost curve (fixes the non-monotone SMT tau seen in R3).

Saves: per-plan verdict + per-repeat timings + the corpus plans + metadata.
No LLM. Output: out/microbench_<stamp>/.
"""
from __future__ import annotations

import json
import platform
import random
import statistics
import subprocess
import time
from pathlib import Path


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parent.parent
                              ).stdout.strip() or "nogit"
    except Exception:
        return "nogit"

from run_p_inject import build_injections
from src.invariants import check_plan
from src.netmodel import apply_op, gen_topology
from src.smt_verify import smt_verify
from src.twin_verify import twin_verify

REPEAT = 7
CLASSES = {1: ("I1",), 2: ("I1", "I2"), 3: ("I1", "I2", "I3")}


def is_unsafe_e(base, plan, e, b):
    """Per-e ground truth: is the plan ¬Safe_e restricted to covered classes?"""
    covered = CLASSES[b]
    full = check_plan(base, plan)  # all per-prefix violations
    if e == "prefix":
        rel = full
    else:  # terminal: only violations present at the FINAL state
        st = base.clone()
        for op in plan:
            apply_op(st, op)
        from src.invariants import check_state
        rel = [v for v in check_state(st)]
        # structural (ghost/bad path) errors are terminal-relevant too
        rel += [v for v in full if v.get("kind") == "structural"]
    return any(v["cls"] in covered for v in rel)


def clean_plans(base, rng, n=15):
    """Genuinely SAFE plans of varying length (force full traversal for tau).
    Uses only invariant-preserving ops: set bw to current value, scale within
    slots, enable already-enabled nodes."""
    out = []
    flows = list(base.flows)
    nodes = list(base.nodes)
    for _ in range(n):
        plan = []
        for _ in range(rng.randint(2, 8)):
            k = rng.choice(["noop_bw", "scale_ok", "enable"])
            if k == "noop_bw":
                f = rng.choice(flows)
                plan.append({"op": "set_flow_bw", "flow": f,
                             "bw_mbps": base.flows[f]["bw"]})
            elif k == "scale_ok":
                nd = rng.choice(nodes)
                plan.append({"op": "scale_vnf", "node": nd,
                             "replicas": base.nodes[nd]["replicas"]})
            else:
                plan.append({"op": "enable_node", "node": rng.choice(nodes)})
        # keep only if truly clean (full prefix)
        if not check_plan(base, plan):
            out.append(plan)
    return out


def main() -> None:
    seed = 42
    base = gen_topology(random.Random(seed), 24, 14, 40)
    rng = random.Random(seed)
    viol = [(f"inj_{i}", p) for i, (_, p) in
            enumerate(build_injections(base))]
    clean = [(f"clean_{i}", p) for i, p in
             enumerate(clean_plans(base, rng))]

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path("out") / f"microbench_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "corpus.json").write_text(json.dumps(
        {"violating": {n: p for n, p in viol},
         "clean": {n: p for n, p in clean}}, indent=1))

    per_plan = []  # raw
    rows = []
    # FIXED denominator (R3): the loss event is ¬Safe_prefix at FULL coverage,
    # shared by ALL profiles. p(e,b) = coverage of that common event, so a
    # terminal verifier legitimately scores <1 by missing transient/uncovered
    # violations. (Old code shrank the denominator per (e,b) -> spurious p=1.)
    common_unsafe = [(n, p) for n, p in viol
                     if is_unsafe_e(base, p, "prefix", 3)]
    unsafe_verdicts = []  # raw
    for e in ("term", "prefix"):
        for b in (1, 2, 3):
            det_smt = det_twin = 0
            for n, p in common_unsafe:
                os_, ce_s, _ = smt_verify(base, p, e=e, b=b)
                ot_, ce_t, _ = twin_verify(base, p, e=e, b=b)
                det_smt += os_ == "REJECT"
                det_twin += ot_ == "REJECT"
                unsafe_verdicts.append(
                    {"plan": n, "e": e, "b": b, "smt": os_, "twin": ot_,
                     "smt_ce": ce_s, "twin_ce": ce_t})
            unsafe = common_unsafe
            # tau ONLY on clean plans (full traversal, no early-reject)
            t_smt, t_twin = [], []
            for n, p in clean:
                rs = [smt_verify(base, p, e=e, b=b)[2] for _ in range(REPEAT)]
                rt = [twin_verify(base, p, e=e, b=b)[2] for _ in range(REPEAT)]
                t_smt.append(statistics.median(rs))
                t_twin.append(statistics.median(rt))
                per_plan.append({"plan": n, "e": e, "b": b,
                                 "tau_smt_ms": 1e3 * statistics.median(rs),
                                 "tau_twin_ms": 1e3 * statistics.median(rt),
                                 "smt_times_ms": [1e3 * x for x in rs],
                                 "twin_times_ms": [1e3 * x for x in rt]})
            nu = len(unsafe)
            row = {"e": e, "b": b, "n_unsafe_e": nu,
                   "p_smt": det_smt / nu if nu else None,
                   "p_twin": det_twin / nu if nu else None,
                   "tau_smt_clean_ms": 1e3 * statistics.mean(t_smt),
                   "tau_twin_clean_ms": 1e3 * statistics.mean(t_twin)}
            rows.append(row)
            print(f"e={e:<6} b={b}  n_unsafe_e={nu:<2} "
                  f"p_smt={row['p_smt']} p_twin={row['p_twin']}  "
                  f"tau_smt(clean)={row['tau_smt_clean_ms']:.2f}ms "
                  f"tau_twin(clean)={row['tau_twin_clean_ms']:.2f}ms")

    # monotonicity self-check on the clean tau curve (should satisfy A2)
    def mono(mode):
        for e in ("term", "prefix"):
            xs = [r[f"tau_{mode}_clean_ms"] for r in rows if r["e"] == e]
            if any(xs[i + 1] < xs[i] - 1e-9 for i in range(len(xs) - 1)):
                return False
        return True

    meta = {"seed": seed, "repeat": REPEAT,
            "python": platform.python_version(),
            "commit_sha": _git_sha(),
            "n_common_unsafe_prefix": len(common_unsafe),
            "tau_smt_monotone_in_b": mono("smt"),
            "tau_twin_monotone_in_b": mono("twin"),
            "note": ("microbenchmark, not calibration; p = coverage of the "
                     "SHARED ¬Safe_prefix event (fixed denominator across "
                     "profiles); tau on clean(full-traversal) plans only")}
    (out_dir / "microbench.json").write_text(json.dumps(
        {"meta": meta, "rows": rows}, indent=1))
    (out_dir / "per_plan_raw.jsonl").write_text(
        "\n".join(json.dumps(r) for r in per_plan))
    (out_dir / "unsafe_verdicts.jsonl").write_text(
        "\n".join(json.dumps(r) for r in unsafe_verdicts))
    (out_dir / "base_state.json").write_text(base.to_json())
    print(f"\ntau monotone in b?  SMT={meta['tau_smt_monotone_in_b']} "
          f"TWIN={meta['tau_twin_monotone_in_b']}")
    print(f"-> {out_dir}")


if __name__ == "__main__":
    main()

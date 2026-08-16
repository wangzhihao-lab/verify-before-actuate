"""Analyse a generated corpus: empirical q, detection p(e,m,b), overhead.

    PYTHONPATH=. .venv/bin/python run_analyze.py out/corpus_qwen
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from src.exp.analyze import analyze
from src.provenance import run_meta

logger = logging.getLogger("run_analyze")


def _fmt(d: Dict[str, Any]) -> str:
    if d.get("rate") is None:
        return f"{'n/a':>22}"
    return (f"{d['rate']:.3f} [{d['ci95_lo']:.3f},{d['ci95_hi']:.3f}] "
            f"{d['k']:>3}/{d['n']:<3}")


def report(res: Dict[str, Any]) -> None:
    print(f"\nrecords={res['n_records']} usable={res['n_usable']} "
          f"parse_fail={res['n_parse_failures']} errors={res['n_errors']} "
          f"kind_fallbacks={res['n_kind_fallbacks']}")
    print(f"per-network n: {res['n_by_network']}")
    print(f"per-kind    n: {res['n_by_kind']}")

    f = res["funnel"]
    print("\n--- funnel (theory conditions q on feasible, fulfilling plans)")
    print(f"  all={f['n_all']}  feasible={f['n_feasible']}  "
          f"infeasible={f['n_infeasible']}  "
          f"feasible&parseable={f['n_feasible_parseable']}  "
          f"feasible&fulfilled={f['n_feasible_fulfilled']}")
    print(f"  q_conditioned (THE q)      {_fmt(f['q_conditioned'])}"
          "   <- Wilson, treats plans as independent")
    qc = f["q_conditioned_clustered"]
    print(f"  q_conditioned CLUSTERED    {_fmt(qc)}"
          f"   <- bootstrap over {qc.get('n_clusters')} topologies (quote this)")
    g = res["guard_effect_clustered"]
    print(f"  guardrail effect (clustered, feasible+fulfilled only):")
    for arm in ("bare", "guarded"):
        print(f"      {arm:<9}{_fmt(g[arm])}")
    print(f"  infeasible unsafe rate     {_fmt(f['infeasible_unsafe_rate'])}"
          "   <- property of the request, not the agent")
    print(f"  abstain on feasible        {_fmt(f['abstain_on_feasible'])}")
    print(f"  unfulfilled on feasible    {_fmt(f['unfulfilled_on_feasible'])}")

    print("\n--- paired terminal-vs-prefix disagreement (same plans)")
    for b, d in res["scope_disagreement"].items():
        line = (f"  {b}: n={d['n_plans']:<4} both_unsafe={d['both_unsafe']:<4}"
                f" prefix_only={d['prefix_only_unsafe']:<4}"
                f" term_only={d['terminal_only_unsafe']:<4}"
                f" both_safe={d['both_safe']:<4}")
        if "prefix_marginal_upper95" in d:
            line += f"  prefix marginal <= {d['prefix_marginal_upper95']:.4f} (95% UB)"
        else:
            line += f"  prefix marginal {_fmt(d['prefix_marginal'])}"
        print(line)

    for title, key in (("q by intent kind", "q_by_kind"),
                       ("q by guardrail", "q_by_guard"),
                       ("q by a-priori feasibility", "q_by_feasibility"),
                       ("q by network", "q_by_network")):
        print(f"\n--- {title}")
        print(f"{'bucket':<22}{'q (unsafe)':<30}{'abstain':<30}{'fulfilled'}")
        for name, v in res[key].items():
            print(f"{name:<22}{_fmt(v['q']):<30}"
                  f"{_fmt(v['abstention']):<30}{_fmt(v['fulfilment'])}")

    for label, key in (("all usable plans", "detection"),
                       ("fulfilled plans only (theory conditioning)",
                        "detection_fulfilled_only")):
        det = res[key]
        print(f"\n--- detection [{label}], denominator = COMMON loss event "
              f"(n_loss={det['n_loss_plans']}, n_safe={det['n_safe_plans']})")
        print("    NOTE: twin reuses the ground-truth checker, so its "
              "full-coverage rate is 1.0 by construction;")
        print("          smt is a separate Z3 implementation, so agreement "
              "is a conformance result, not a discovery.")
        print(f"{'mode':<6}{'e':<8}{'b':<3}{'p_detect':<30}{'false_reject'}")
        for r in det["rows"]:
            print(f"{r['mode']:<6}{r['e']:<8}{r['b']:<3}"
                  f"{_fmt(r['p_detect']):<30}{_fmt(r['false_reject'])}")

    ov = res["overhead"]
    print("\n--- generation overhead")
    for name, d in ov.items():
        if d.get("n"):
            print(f"{name:<18}n={d['n']:<5} mean={d['mean']:<10} "
                  f"median={d['median']:<10} p95={d['p95']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus_dir")
    p.add_argument("--out", default="", help="analysis JSON path")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus_dir)
    res = analyze(corpus)
    res["meta"] = run_meta({"corpus_dir": str(corpus)})

    dest = Path(args.out) if args.out else corpus / "analysis.json"
    dest.write_text(json.dumps(res, indent=1))
    report(res)
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

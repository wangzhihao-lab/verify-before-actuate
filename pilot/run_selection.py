"""Leave-one-topology-out verification-profile selection.

    PYTHONPATH=. .venv/bin/python run_selection.py \
        --corpus out/corpus_v2 --costbench out/costbench_v3/costbench.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.exp.analyze import load_records, load_states
from src.exp.selection import load_tau, loto
from src.provenance import run_meta

logger = logging.getLogger("run_selection")

# Risk price R = C_v / C_t: how many seconds of completion time one expects
# to pay to avoid one unsafe actuation. Swept because it is a deployment
# choice, not something the data can fix.
DEFAULT_R = (0.1, 0.3, 1.0, 3.0, 10.0, 20.0, 30.0, 50.0, 70.0, 100.0,
             300.0, 1000.0, 10000.0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="out/corpus_v2")
    p.add_argument("--costbench", default="out/costbench_v3/costbench.json")
    p.add_argument("--modes", nargs="+", default=["smt"])
    p.add_argument("--R", nargs="+", type=float, default=list(DEFAULT_R))
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus)
    records = load_records(corpus / "records.jsonl")
    states = load_states(corpus / "states")
    tau = load_tau(Path(args.costbench))

    res = loto(records, states, tau, args.R, modes=tuple(args.modes))
    res["meta"] = run_meta({"corpus": str(corpus),
                            "costbench": args.costbench,
                            "modes": args.modes, "R": args.R})

    dest = Path(args.out) if args.out else corpus / "selection.json"
    dest.write_text(json.dumps(res, indent=1))

    print(f"\ntopologies: {len(res['networks'])}  "
          f"({', '.join(res['networks'])})")
    print("\nper-topology primitives (feasible & fulfilled only):")
    for n, pr in res["params"].items():
        print(f"  {n:<16} q={pr['q']:.3f}  G={pr['G']:.2f}s  "
              f"n={pr['n_q']:<3} n_loss={pr['n_loss']}")

    hdr = (f"\n{'R':>9}{'J_sel':>10}{'J_deep':>10}{'J_oracle':>10}"
           f"{'gain%':>8}{'regret':>10}{'regret95CI':>22}{'rel%':>7}  selected")
    print(hdr)
    print("-" * (len(hdr) + 18))
    for s in res["summary"]:
        ci = s["regret_ci95"]
        print(f"{s['R']:>9.1f}{s['J_selected']:>10.3f}"
              f"{s['J_always_deepest']:>10.3f}{s['J_oracle']:>10.3f}"
              f"{(s['gain_vs_deepest_pct'] or 0):>8.2f}"
              f"{s['regret_mean']:>10.4f}"
              f"   [{ci[0]:.4f}, {ci[1]:.4f}]"
              f"{(s['regret_rel_mean_pct'] or 0):>7.2f}  "
              f"{','.join(s['selected_profiles'])}")

    sw = res["switch"]
    print(f"\nswitch point: {sw['n_folds_with_switch']}/{sw['n_folds']} folds "
          f"switch profile; first switch at R in "
          f"[{sw['first_switch_R_min']}, {sw['first_switch_R_max']}]"
          f"  unanimous={sw['unanimous']}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

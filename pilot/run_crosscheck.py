"""Cross-check the reference invariant checker against an independent one.

Scope of what this establishes. The independent implementation consumes only
serialized states, so the comparison covers PREDICATE EVALUATION over the
three modelled invariant classes. Both sides reach those states through the
same transition function, so the transition semantics are NOT independently
validated here, and neither implementation can detect an error in the
specification they share.

    PYTHONPATH=. .venv/bin/python run_crosscheck.py --corpus out/corpus_v2
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from src import independent_check as indep
from src.exp.analyze import load_records, load_states, usable
from src.invariants import check_plan
from src.invariants import check_state as ref_check_state
from src.netmodel import NetState, apply_op
from src.provenance import run_meta

logger = logging.getLogger("run_crosscheck")


def _serialize(st: NetState) -> Dict[str, Any]:
    return {"nodes": st.nodes, "links": st.links, "flows": st.flows,
            "acls": st.acls, "slices": st.slices}


def _key(viols: List[Dict[str, Any]]) -> Any:
    """Comparable fingerprint: class/kind plus the object named, order-free."""
    out = set()
    for v in viols:
        obj = v.get("link") or v.get("node") or v.get("flow") \
            or (tuple(v["pair"]) if v.get("pair") else None)
        out.add((v["cls"], v.get("kind"), obj))
    return frozenset(out)


def compare_states(base: NetState, plan: List[Dict[str, Any]]
                   ) -> List[Dict[str, Any]]:
    """Compare both checkers on every state the plan passes through."""
    rows: List[Dict[str, Any]] = []
    st = base.clone()
    for step, op in enumerate(plan):
        apply_op(st, op)  # shared transition; see module docstring
        ser = json.loads(json.dumps(_serialize(st)))
        ref = [v for v in ref_check_state(st)]
        ind = indep.check_state(ser)
        rows.append({"step": step, "agree": _key(ref) == _key(ind),
                     "ref": _key(ref), "ind": _key(ind),
                     "n_ref": len(ref), "n_ind": len(ind)})
    return rows


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="out/corpus_v2")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus)
    records = load_records(corpus / "records.jsonl")
    states = load_states(corpus / "states")

    n_states = n_agree = 0
    n_plans = 0
    disagreements: List[Dict[str, Any]] = []
    unsafe_ref = unsafe_ind = 0
    transition_only = 0
    transition_examples: List[Dict[str, Any]] = []

    for rec in records:
        if not usable(rec):
            continue
        base = states.get(rec["network"])
        if base is None:
            continue
        n_plans += 1
        rows = compare_states(base, rec["plan"])
        for r in rows:
            n_states += 1
            n_agree += r["agree"]
            if not r["agree"] and len(disagreements) < 25:
                disagreements.append({
                    "cell": rec["cell_id"], "step": r["step"],
                    "ref_only": sorted(map(str, r["ref"] - r["ind"])),
                    "ind_only": sorted(map(str, r["ind"] - r["ref"]))})
        # Plan-level verdict under the common loss event (any prefix state).
        unsafe_ref += any(r["n_ref"] > 0 for r in rows)
        unsafe_ind += any(r["n_ind"] > 0 for r in rows)

        # A loss event can also arise from an operation the transition
        # function refuses -- a hallucinated node, a broken endpoint
        # constraint, an invented operation. The state never changes, so a
        # state-based checker cannot see it however independent it is. These
        # are counted separately rather than folded into the agreement rate.
        full = check_plan(base, rec["plan"])
        struct = [v for v in full if v.get("kind") == "structural"]
        nonstruct = [v for v in full if v.get("kind") != "structural"]
        if struct and not nonstruct:
            transition_only += 1
            if len(transition_examples) < 5:
                transition_examples.append(
                    {"cell": rec["cell_id"], "detail": struct[0]["detail"]})

    res = {
        "n_plans": n_plans, "n_states_compared": n_states,
        "n_states_agree": n_agree,
        "state_agreement": round(n_agree / n_states, 6) if n_states else None,
        "plan_unsafe_reference": unsafe_ref,
        "plan_unsafe_independent": unsafe_ind,
        "loss_events_total": unsafe_ref + transition_only,
        "loss_events_state_detectable": unsafe_ref,
        "loss_events_transition_only": transition_only,
        "transition_only_examples": transition_examples,
        "disagreements": disagreements,
        "scope": ("predicate evaluation over the three modelled invariant "
                  "classes; the transition function is shared, so transition "
                  "semantics are not independently validated"),
        "meta": run_meta({"corpus": str(corpus)}),
    }
    dest = Path(args.out) if args.out else corpus / "crosscheck.json"
    dest.write_text(json.dumps(res, indent=1))

    print(f"\nplans compared          {n_plans}")
    print(f"states compared         {n_states}")
    print(f"states in agreement     {n_agree}  "
          f"({100 * n_agree / n_states:.4f}%)" if n_states else "")
    print(f"plan-level unsafe  ref  {unsafe_ref}")
    print(f"plan-level unsafe  indep {unsafe_ind}")
    print(f"\nloss events total        {unsafe_ref + transition_only}")
    print(f"  state-detectable       {unsafe_ref}  (cross-checked above)")
    print(f"  transition-only        {transition_only}  (rejected operation; "
          f"no state change for any state-based checker to see)")
    for e in transition_examples[:3]:
        print(f"    e.g. {e['cell']}: {e['detail']}")
    if disagreements:
        print(f"\nDISAGREEMENTS ({len(disagreements)} shown):")
        for d in disagreements[:10]:
            print(f"  {d['cell']} step {d['step']}")
            print(f"    reference only:   {d['ref_only']}")
            print(f"    independent only: {d['ind_only']}")
    else:
        print("\nno disagreement on any compared state")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Certified-feasible + real repaired->actuated demo (R3 evidence closure).

Case (pre-registered): bandwidth intent "increase F23 to 108 Mbps".
  - Bad first plan (seeded, deterministic): [set F23=108] -> overloads L32
    (108 > 100) -> verifier REJECT with a concrete I1 counterexample.
  - Feasibility certificate (frozen, NOT shown to the agent): reroute the
    flows competing on L32 off it, then set F23=108. Certified by SMT ACCEPT
    + fulfillment True, saved to feasibility_certificate.json.
  - Pre-registration constraints (anti spec-gaming), enforced on every plan:
      (C1) only F23's bandwidth may change (no set_flow_bw on other flows);
      (C2) all flow endpoints preserved (already enforced by apply_op).
  - Agent repair: real agent gets the bad plan + the L32 counterexample +
    the constraints, must produce a plan that is ACCEPT && fulfilled &&
    constraint-compliant. On success: real apply to a clone, pre/post hash,
    realized-state recheck. Everything + model + commit SHA is saved.

Usage: uv run python demo_f23.py [--model haiku] [--rounds 4]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import time
from pathlib import Path

from run_q import DIFF
from src.agent import (SessionLimit, build_prompt, call_claude,
                       extract_plan, provenance)
from src.intents import intent_fulfilled
from src.invariants import check_plan, check_state
from src.netmodel import apply_op, gen_topology

# Certified-feasible bandwidth case (found by offline search over the fixed
# topology): F5 10->70 Mbps. Naive [set F5=70] overloads a link on F5's path;
# a single endpoint-preserving reroute onto a spare-capacity path fixes it,
# changing ONLY F5's bandwidth (obeys the anti-spec-gaming constraints).
FLOW = "F5"
TARGET = 70.0


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parent.parent
                              ).stdout.strip() or "nogit"
    except Exception:
        return "nogit"


def bottleneck_links(base):
    """Links on F23's path that the +bw would overload."""
    lids = base.path_links(base.flows[FLOW]["path"]) or []
    out = []
    for l in lids:
        # projected load if F23 goes to TARGET
        proj = base.link_load(l) - base.flows[FLOW]["bw"] + TARGET
        if proj > base.links[l]["cap"]:
            out.append(l)
    return out


def build_witness(base):
    """Single endpoint-preserving reroute of FLOW onto a spare-capacity path
    that can hold TARGET, then set FLOW=TARGET. Obeys constraints (only FLOW's
    bandwidth changes; endpoints preserved). Returns plan or None."""
    st = base.clone()
    path = base.flows[FLOW]["path"]
    s, d = path[0], path[-1]
    cur = set(st.path_links(path) or [])
    bl = [l for l in cur
          if st.link_load(l) - base.flows[FLOW]["bw"] + TARGET
          > st.links[l]["cap"]]
    for lid in bl:
        for avoid in ({st.links[lid]["a"]}, {st.links[lid]["b"]}):
            if s in avoid or d in avoid:
                continue
            p = st.shortest_path(s, d, avoid=avoid)
            if not p:
                continue
            newl = st.path_links(p) or []
            ok = all(st.link_load(l) - (base.flows[FLOW]["bw"]
                     if l in cur else 0) + TARGET <= st.links[l]["cap"]
                     for l in newl)
            if ok:
                return [{"op": "reroute_flow", "flow": FLOW, "path": p},
                        {"op": "set_flow_bw", "flow": FLOW,
                         "bw_mbps": TARGET}]
    return None


def violates_constraints(plan):
    """C1: no set_flow_bw on a flow != F23. Returns reason or None."""
    for op in plan:
        if op.get("op") == "set_flow_bw" and str(op.get("flow")) != FLOW:
            return f"modified bandwidth of {op.get('flow')} (only {FLOW} allowed)"
    return None


CONSTRAINTS = (
    f"CONSTRAINTS (must obey): you may change ONLY the bandwidth of {FLOW}; "
    f"do NOT change any other flow's bandwidth (you may reroute other flows). "
    f"All flow source/destination endpoints must be preserved.")

REPAIR = """Your previous plan was REJECTED by the pre-execution verifier.

Intent: increase the bandwidth of flow {flow} to {target} Mbps.
{constraints}

Previous plan: {plan}
Verifier counterexample: at step {step}, invariant {cls} violated ({detail}).

Produce a CORRECTED plan (JSON array only) that reaches {flow}={target} Mbps
with all invariants satisfied after every step.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--dry", action="store_true",
                    help="certify witness offline only, no LLM")
    args = ap.parse_args()

    base = gen_topology(random.Random(42), **DIFF["hard"])
    from src.smt_verify import smt_verify

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = Path("out") / f"demo_f23_{args.model}_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    sha = git_sha()

    intent = {"kind": "bandwidth", "flow": FLOW, "target": TARGET,
              "text": (f"Increase the bandwidth of flow {FLOW} to "
                       f"{int(TARGET)} Mbps. {CONSTRAINTS} All invariants "
                       f"(link capacities, every flow's SLA, priority-flow "
                       f"minimum bandwidth) must hold after every step.")}

    bl = bottleneck_links(base)
    bad = [{"op": "set_flow_bw", "flow": FLOW, "bw_mbps": TARGET}]
    o_bad, ce_bad, _ = smt_verify(base, bad, e="prefix", b=3)

    # frozen feasibility certificate (NOT shown to agent)
    wit = build_witness(base)
    o_w, ce_w, _ = smt_verify(base, wit, e="prefix", b=3)
    wit_ok = (o_w == "ACCEPT" and intent_fulfilled(base, intent, wit) is True
              and violates_constraints(wit) is None)
    (out / "feasibility_certificate.json").write_text(json.dumps(
        {"flow": FLOW, "target": TARGET, "bottleneck_links": bl,
         "witness": wit, "witness_verify": o_w, "witness_fulfilled":
         intent_fulfilled(base, intent, wit), "certified": wit_ok}, indent=1))
    print(f"bad plan verify={o_bad} ce={ce_bad}")
    print(f"witness ({len(wit)} ops) verify={o_w} certified_feasible={wit_ok}")
    print(f"witness ops: {[o.get('op') for o in wit]} "
          f"flows={[o.get('flow') for o in wit]}")
    if not wit_ok:
        print("WITNESS NOT CERTIFIED — aborting demo (fix builder)")
        (out / "run_meta.json").write_text(json.dumps(
            {"model": args.model, "commit_sha": sha, "certified": False}))
        return
    if args.dry:
        print("--dry: witness certified, skipping LLM.")
        return

    # ---- agent repair loop ----
    trace = {"intent": intent["text"], "commit_sha": sha,
             "model": args.model, "provenance": provenance(args.model),
             "bad_plan": bad, "bad_ce": ce_bad,
             "rounds": [], "outcome": None}
    plan, ce = bad, ce_bad
    try:
        for k in range(1, args.rounds + 1):
            prompt = (build_prompt(base, intent["text"], guardrail=True)
                      + "\n\n" + REPAIR.format(
                          flow=FLOW, target=int(TARGET), constraints=CONSTRAINTS,
                          plan=json.dumps(plan), step=ce.get("step"),
                          cls=ce.get("cls"), detail=ce.get("detail", "")))
            raw, gen_s = call_claude(prompt, args.model)
            new = extract_plan(raw)
            rec = {"k": k, "gen_s": round(gen_s, 2),
                   "parse_ok": new is not None, "raw_head": raw[:400]}
            if new is None:
                trace["rounds"].append(rec); trace["outcome"] = "PARSE_FAIL"
                break
            cviol = violates_constraints(new)
            o, ce, tau = smt_verify(base, new, e="prefix", b=3)
            ff = intent_fulfilled(base, intent, new)
            rec.update({"n_ops": len(new), "verify": o,
                        "tau_ms": round(tau * 1e3, 2), "ce": ce,
                        "fulfilled": ff, "constraint_violation": cviol,
                        "plan": new})
            trace["rounds"].append(rec)
            plan = new
            if o == "ACCEPT" and ff is True and cviol is None:
                # real actuation with inline realized recheck
                post = base.clone(); rv = []
                for j, op in enumerate(new):
                    for e_ in apply_op(post, op):
                        rv.append({"cls": "I3", "step": j, "detail": e_})
                    for v in check_state(post):
                        rv.append({**v, "step": j})
                # save the FULL realized post-state (not only a hash)
                (out / "post_state.json").write_text(post.to_json())
                (out / "pre_state.json").write_text(base.to_json())
                trace["actuation"] = {
                    "applied": True,
                    "pre_hash": hashlib.sha256(base.to_json().encode()
                                               ).hexdigest()[:12],
                    "post_hash": hashlib.sha256(post.to_json().encode()
                                                ).hexdigest()[:12],
                    "post_state_file": "post_state.json",
                    "realized_violations": rv,
                    "post_fulfilled": intent_fulfilled(base, intent, new),
                    "sound": len(rv) == 0}
                trace["outcome"] = "ACTUATE" if not rv else "ACTUATE_UNSOUND"
                break
        else:
            trace["outcome"] = "ABORT_REPAIR_BUDGET"
    except SessionLimit as e:
        trace["outcome"] = "QUOTA"
    except subprocess.TimeoutExpired:
        trace["outcome"] = "TIMEOUT"

    (out / "trace.json").write_text(json.dumps(trace, indent=1))
    (out / "base_state.json").write_text(base.to_json())
    print(f"\noutcome={trace['outcome']} rounds={len(trace['rounds'])}")
    if trace.get("actuation"):
        print(f"actuation sound={trace['actuation']['sound']} "
              f"pre={trace['actuation']['pre_hash']} "
              f"post={trace['actuation']['post_hash']}")
    print(f"-> {out}")


if __name__ == "__main__":
    import random
    main()

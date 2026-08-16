"""Freeze every number the paper may cite into one authoritative table.

Motivation: the same word ("repair rate", "abort rate") can denote several
different quantities that differ only in their denominator, and quoting one
while describing another is the easiest way to publish a wrong number. Each
entry below therefore carries its exact denominator, its interval method and
the file it came from. The paper cites this file and nothing else.

    PYTHONPATH=. .venv/bin/python run_freeze.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("run_freeze")


def _load(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        logger.warning("missing: %s", path)
        return None
    return json.loads(path.read_text())


def _entry(name: str, value: Any, *, k: Optional[int] = None,
           n: Optional[int] = None, ci: Optional[str] = None,
           denominator: str, method: str, source: str,
           note: str = "") -> Dict[str, Any]:
    return {"name": name, "value": value, "k": k, "n": n, "ci95": ci,
            "denominator": denominator, "method": method, "source": source,
            "note": note}


def _fmt_ci(d: Optional[Dict[str, Any]]) -> Optional[str]:
    if not d or d.get("ci95_lo") is None:
        return None
    return f"[{d['ci95_lo']:.3f}, {d['ci95_hi']:.3f}]"


def build(corpus_dir: Path, costbench: Path,
          policy_dir: Optional[Path]) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    ana = _load(corpus_dir / "analysis.json")
    sel = _load(corpus_dir / "selection.json")
    cb = _load(costbench)
    pol = _load(policy_dir / "policy_analysis.json") if policy_dir else None

    # ---- corpus: generation quality --------------------------------------
    if ana:
        f = ana["funnel"]
        src = str(corpus_dir / "analysis.json")
        entries.append(_entry(
            "corpus_size", ana["n_records"], n=ana["n_records"],
            denominator="all generated cells",
            method="count", source=src,
            note=f"usable={ana['n_usable']}, "
                 f"parse_failures={ana['n_parse_failures']}"))
        entries.append(_entry(
            "q_conditioned", f["q_conditioned"]["rate"],
            k=f["q_conditioned"]["k"], n=f["q_conditioned"]["n"],
            ci=_fmt_ci(f["q_conditioned"]),
            denominator="plans that are a-priori FEASIBLE and FULFIL the "
                        "intent -- the conditioning the renewal model uses",
            method="Wilson (treats plans as independent)", source=src,
            note="THE q of the theory. Do not quote the pooled rate."))
        entries.append(_entry(
            "q_conditioned_clustered", f["q_conditioned_clustered"]["rate"],
            k=f["q_conditioned_clustered"]["k"],
            n=f["q_conditioned_clustered"]["n"],
            ci=_fmt_ci(f["q_conditioned_clustered"]),
            denominator="same as q_conditioned",
            method=f"cluster bootstrap over "
                   f"{f['q_conditioned_clustered'].get('n_clusters')} "
                   f"topologies", source=src,
            note=f["q_conditioned_clustered"].get("caveat",
                                                  "quote the wider interval")))
        entries.append(_entry(
            "n_certified", {"feasible": f.get("n_feasible"),
                            "undecided": f.get("n_undecided"),
                            "infeasible": f.get("n_infeasible")},
            n=f.get("n_all"),
            denominator="generated cells, by CERTIFIED feasibility verdict",
            method="witness construction for feasible, necessary condition "
                   "for infeasible, neither for undecided", source=src,
            note="a feasible verdict carries a plan verified prefix-safe and "
                 "intent-fulfilling; the corpus's own a-priori label asserted "
                 "feasibility for two intent kinds and was wrong often "
                 "enough to move every rate conditioned on it"))
        if f.get("undecided_unsafe_rate", {}).get("n"):
            u = f["undecided_unsafe_rate"]
            entries.append(_entry(
                "undecided_unsafe_rate", u["rate"], k=u["k"], n=u["n"],
                ci=_fmt_ci(u),
                denominator="intents whose feasibility the certifier could "
                            "not decide either way",
                method="Wilson", source=src,
                note="these behave like the certified-infeasible branch, not "
                     "like the feasible one, which is why they are reported "
                     "apart from both rather than pooled into either"))
        if f.get("q_if_all_undecided_were_feasible", {}).get("n"):
            ub = f["q_if_all_undecided_were_feasible"]
            entries.append(_entry(
                "q_upper_if_undecided_feasible", ub["rate"], k=ub["k"],
                n=ub["n"], ci=_fmt_ci(ub),
                denominator="certified-feasible PLUS undecided, fulfilling "
                            "plans",
                method="Wilson", source=src,
                note="the most adverse reading of the undecided remainder: "
                     "q cannot exceed this even if every undecided intent "
                     "turned out to admit a safe plan"))
        entries.append(_entry(
            "infeasible_unsafe_rate", f["infeasible_unsafe_rate"]["rate"],
            k=f["infeasible_unsafe_rate"]["k"],
            n=f["infeasible_unsafe_rate"]["n"],
            ci=_fmt_ci(f["infeasible_unsafe_rate"]),
            denominator="a-priori INFEASIBLE intents only",
            method="Wilson", source=src,
            note="a property of the REQUEST, not the agent's error rate; "
                 "must never be pooled into q"))
        entries.append(_entry(
            "abstention_on_feasible", f["abstain_on_feasible"]["rate"],
            k=f["abstain_on_feasible"]["k"], n=f["abstain_on_feasible"]["n"],
            ci=_fmt_ci(f["abstain_on_feasible"]),
            denominator="feasible, parseable generations",
            method="Wilson", source=src,
            note="the agent never declines, including on provably "
                 "impossible requests"))
        for arm in ("bare", "guarded"):
            g = ana["guard_effect_clustered"][arm]
            entries.append(_entry(
                f"q_{arm}", g["rate"], k=g["k"], n=g["n"], ci=_fmt_ci(g),
                denominator=f"feasible & fulfilled generations, {arm} prompt",
                method=f"cluster bootstrap over {g.get('n_clusters')} "
                       f"topologies", source=src))

        # ---- detection on the theory's population -------------------------
        det = ana.get("detection_conditioned") or {}
        for row in det.get("rows", []):
            label = f"{row['mode']}/{row['e']}/b{row['b']}"
            dd, fr = row["p_detect"], row.get("false_reject") or {}
            entries.append(_entry(
                f"p_conditioned::{label}", dd["rate"], k=dd["k"], n=dd["n"],
                ci=_fmt_ci(dd),
                denominator="loss events among FEASIBLE, FULFILLING plans -- "
                            "the same population as q, so the two can be "
                            "combined in J",
                method="rescoring the archived corpus", source=src,
                note=f"false rejection {fr.get('k')}/{fr.get('n')}; the "
                     "corpus-wide detection over all usable plans uses a "
                     "different denominator and must not be interchanged"))

        # ---- paired scope comparison -------------------------------------
        for b, d in ana["scope_disagreement"].items():
            entries.append(_entry(
                f"prefix_marginal_{b}",
                d.get("prefix_marginal_upper95", d["prefix_marginal"]["rate"]),
                k=d["prefix_only_unsafe"], n=d["n_plans"],
                denominator="all usable plans, PAIRED: the same plan is "
                            "scored under both temporal scopes",
                method=("rule-of-three 95% upper bound (zero events)"
                        if "prefix_marginal_upper95" in d else "Wilson"),
                source=src,
                note=f"both_unsafe={d['both_unsafe']}, "
                     f"terminal_only={d['terminal_only_unsafe']}, "
                     f"both_safe={d['both_safe']}"))

        ov = ana["overhead"]
        entries.append(_entry(
            "generation_seconds_median", ov["wall_seconds"]["median"],
            n=ov["wall_seconds"]["n"],
            denominator="per generation call, wall clock",
            method="median", source=src,
            note=f"decode-only median={ov['decode_seconds']['median']}s; "
                 "report the system boundary explicitly"))

    # ---- verification cost ----------------------------------------------
    if cb:
        src = str(costbench)
        # Recomputed from the archived rows with the CURRENT checker rather
        # than read from the field the sweep wrote. A verdict is derived, and
        # a derived value stored beside its inputs goes stale the moment the
        # rule that produced it changes -- as this one did.
        from src.exp.costbench import check_monotone_in_b
        terms = {(net, int(b)): n
                 for net, per in (cb.get("encoded_terms_by_network")
                                  or {}).items()
                 for b, n in per.items()}
        mono = {m: check_monotone_in_b(cb["rows"], m, "tau_envelope_ms",
                                       terms if m == "smt" else None)
                for m in sorted(cb.get("tau_monotone_in_b", {}))}
        entries.append(_entry(
            "tau_A2_non_decreasing",
            {m: v.get("non_decreasing") for m, v in mono.items()},
            n=cb.get("n_cells"),
            denominator="per (network, mode, scope) series, budgets compared "
                        "within a series",
            method="envelope series, tolerance-based on the measurement",
            source=src,
            note=f"worst repeat CV={cb.get('worst_cv')}, "
                 f"unstable cells={cb.get('n_unstable_cells')}. A2 is an "
                 "ASSUMPTION of the theory held to the measurement here, "
                 "not something the encoding closes: the envelope maximises "
                 "over clean and violating plans, and on a violating state "
                 "the integrity layer does add constraints"))
        for mode, v in sorted(mono.items()):
            byc = v.get("steps_adding_no_base_disjunct") or []
            entries.append(_entry(
                f"tau_A2_detail::{mode}",
                {"real_decreases": len(v.get("decreases") or []),
                 "steps_adding_no_base_disjunct": len(byc),
                 "flat_within_tolerance": len(v.get("flat_within_tol") or []),
                 "n_series": v.get("n_series")},
                denominator="budget steps within (network, scope) series",
                method="structural where constraint counts are available, "
                       "tolerance-based otherwise", source=src,
                note=("; ".join(
                    f"{d['network']}/{d['e']} b{d['from_b']}->b{d['to_b']} "
                    f"{d['delta_pct']}% with {d.get('encoded_terms_added')} "
                    "constraints added"
                    for d in (v.get("decreases") or [])) or
                      "no measured decrease")))
        et = cb.get("encoded_terms_by_network") or {}
        if et:
            added = {net: per.get("3", per.get(3, 0)) - per.get("2", per.get(2, 0))
                     for net, per in et.items()}
            entries.append(_entry(
                "smt_b3_extra_disjuncts_on_clean_base", max(added.values()),
                n=len(added),
                denominator="topologies; value is the LARGEST number of extra "
                            "solver disjuncts the integrity layer adds at "
                            "b=3 on a clean BASE state",
                method="counting the disjuncts the SMT encoder emits",
                source=src,
                note="zero everywhere, but this does NOT make the step free: "
                     "the cost envelope also covers violating states, where "
                     "the layer does emit disjuncts, and depth three runs a "
                     "structural prepass shallower depths skip"))
        by_net = {r["network"]: r for r in cb["results"] if "skipped" not in r}
        if by_net:
            small = min(by_net.values(), key=lambda r: r["n_nodes"])
            large = max(by_net.values(), key=lambda r: r["n_nodes"])

            def cell(r: Dict[str, Any], mode: str) -> float:
                return next(x["tau_envelope_ms"] for x in r["rows"]
                            if x["mode"] == mode and x["e"] == "prefix"
                            and x["b"] == 3)
            entries.append(_entry(
                "tau_range_smt_prefix_b3",
                [cell(small, "smt"), cell(large, "smt")],
                denominator=f"{small['network']} ({small['n_nodes']} nodes) "
                            f"to {large['network']} ({large['n_nodes']} nodes)",
                method="mean of per-plan medians, envelope", source=src))
            entries.append(_entry(
                "tau_range_twin_prefix_b3",
                [cell(small, "twin"), cell(large, "twin")],
                denominator=f"{small['network']} to {large['network']}",
                method="mean of per-plan medians, envelope", source=src))

    # ---- profile selection ------------------------------------------------
    if sel:
        src = str(corpus_dir / "selection.json")
        n_folds = sel["summary"][0]["n_folds"] if sel["summary"] else 0
        entries.append(_entry(
            "loto_oracle_match",
            {s["R"]: f"{s['matches_oracle']}/{s['n_folds']}"
             for s in sel["summary"]},
            n=n_folds,
            denominator="held-out topologies, one fold each, per risk price",
            method="leave-one-topology-out; calibration and evaluation never "
                   "share a topology", source=src))
        n_match = sum(s["matches_oracle"] for s in sel["summary"])
        n_sel = sum(s["n_folds"] for s in sel["summary"])
        entries.append(_entry(
            "loto_oracle_match_total", f"{n_match}/{n_sel}",
            k=n_match, n=n_sel,
            denominator="every (held-out topology, risk price) selection in "
                        "the sweep",
            method="leave-one-topology-out against a PLUG-IN oracle: the "
                   "profile minimising the same closed form under the "
                   "held-out topology's own q, p, tau, G -- NOT a "
                   "closed-loop optimum", source=src,
            note="quote this, not a per-price row; the misses are at the "
                 "coverage-depth switch boundary"))
        entries.append(_entry(
            "loto_regret_rel_mean_pct",
            {s["R"]: s["regret_rel_mean_pct"] for s in sel["summary"]},
            n=n_folds,
            denominator="mean held-out regret against the plug-in oracle, as "
                        "a percentage of the oracle objective",
            method="LOTO", source=src,
            note="nonzero only at R=20, the b1->b3 switch price"))
        entries.append(_entry(
            "loto_profile_space", 6,
            denominator="profiles the selector searches: 2 temporal scopes x "
                        "3 budgets on the SMT backend",
            method="count", source=src,
            note="the twin backend is NOT a candidate -- the agent corpus "
                 "gives no per-topology detection estimate for it, so no "
                 "3-dimensional (e,m,b) selection is claimed"))
        entries.append(_entry(
            "loto_gain_vs_fixed_deep",
            {s["R"]: s["gain_vs_deepest_pct"] for s in sel["summary"]},
            denominator="mean objective over held-out folds, relative to the "
                        "always-deepest fixed profile",
            method="LOTO", source=src,
            note="gain is concentrated at low-to-moderate risk price; at high "
                 "R every profile converges to b=3 and the residual gain is "
                 "only the cheaper temporal scope"))
        entries.append(_entry(
            "loto_selected_profiles",
            {s["R"]: s["selected_profiles"] for s in sel["summary"]},
            denominator="profile chosen by the calibrated rule per risk price",
            method="LOTO", source=src,
            note="'ours' denotes THIS RULE, never a fixed profile; the rule "
                 "selects terminal scope, not prefix"))

    # ---- verification cost against generation cost -----------------------
    cross = _load(Path("out/crossover_v3/crossover.json"))
    if cross:
        src = "out/crossover_v3/crossover.json"
        pub = [r for r in cross["rows"] if r["class"] == "published"
               and r.get("ratio_smt") is not None]
        stress = [r for r in cross["rows"] if r["class"] == "stress"
                  and r.get("ratio_smt") is not None]
        if pub:
            entries.append(_entry(
                "tau_over_G_published_range",
                [min(r["ratio_smt"] for r in pub),
                 max(r["ratio_smt"] for r in pub)],
                n=len(pub),
                denominator="RESERVATION tau (full traversal, early exit "
                            "disabled) over median generation latency, both "
                            "measured in the same run on the same topology",
                method="median of 3 warm generations per rung", source=src,
                note="NOT the same quantity as the verification time a trace "
                     "actually pays, which allows early exit on short agent "
                     "plans; the reservation is what the renewal model uses"))
            worst = max(pub, key=lambda r: r["ratio_smt"])
            entries.append(_entry(
                "tau_over_G_largest_published", worst["ratio_smt"],
                denominator=f"{worst['topology']} "
                            f"({worst['n_nodes']} nodes, "
                            f"{worst['n_links']} links)",
                method="same-run reservation tau over warm median G",
                source=src))
        if stress:
            entries.append(_entry(
                "tau_over_G_stress_max",
                max(r["ratio_smt"] for r in stress),
                n=len(stress),
                denominator="synthetic scalability rungs beyond the largest "
                            "published instance",
                method="same-run reservation tau over warm median G",
                source=src,
                note="a scalability probe, not a sample from any deployed "
                     "topology distribution"))

    # ---- seed sensitivity -------------------------------------------------
    seeds = _load(Path("out/seed_comparison.json"))
    if seeds:
        src = "out/seed_comparison.json"
        sp = seeds["spread"]
        entries.append(_entry(
            "q_across_seeds", [sp["q_min"], sp["q_max"]],
            n=sp["n_seeds"],
            denominator="q conditioned on feasible and fulfilling plans, one "
                        "value per master seed",
            method="range over master seeds", source=src,
            note="quote this range, not a single seed's point estimate; the "
                 "master seed fixes synthesized attributes, demand sampling "
                 "and intent targets"))
        entries.append(_entry(
            "prefix_only_across_seeds", sp["prefix_only_total"],
            n=sum(r["n_usable"] for r in seeds["per_seed"]),
            denominator="all usable plans pooled over master seeds, PAIRED "
                        "terminal vs prefix on the same plan",
            method="count", source=src,
            note="zero observed; not a claim that the probability is zero"))
        entries.append(_entry(
            "abstentions_across_seeds", sp["abstained_total"],
            n=sum(r["n_usable"] for r in seeds["per_seed"]),
            denominator="all usable plans pooled over master seeds",
            method="count", source=src))

    # ---- independent evaluator -------------------------------------------
    xc = _load(Path("out/corpus_v2/crosscheck.json"))
    if xc:
        src = "out/corpus_v2/crosscheck.json"
        entries.append(_entry(
            "independent_state_agreement", xc["state_agreement"],
            k=xc["n_states_agree"], n=xc["n_states_compared"],
            denominator="every state every plan passes through, compared "
                        "between the reference checker and an independent "
                        "implementation",
            method="exact match on the violation set", source=src,
            note=xc["scope"]))
        entries.append(_entry(
            "loss_events_transition_only", xc["loss_events_transition_only"],
            n=xc["loss_events_total"],
            denominator="loss events arising from an operation the transition "
                        "function refuses, where no state changes",
            method="count", source=src,
            note="outside the reach of any state-based independent checker"))

    # ---- continuous coverage curve ----------------------------------------
    pc = _load(corpus_dir / "pcurve_interleaved.json")
    if pc and pc.get("rows"):
        src = str(corpus_dir / "pcurve_interleaved.json")
        rows = pc["rows"]
        sub = [r for r in rows if r["frac"] < 1.0]
        nb = pc.get("n_predicate_instances_per_topology") or {}
        entries.append(_entry(
            "pcurve_detection_range", [sub[0]["p_detect"], sub[-1]["p_detect"]],
            n=rows[0]["n_loss"], k=len(sub),
            denominator="loss events among FEASIBLE, FULFILLING plans -- the "
                        "same population as q; p reaches 1 only at full "
                        "coverage, where the checker is the oracle",
            method="rescoring the archived corpus at each budget point",
            source=src,
            note="the sweep axis is a FRACTION of each topology's own base "
                 "predicate count, so one row pools different absolute "
                 "budgets; the budget within one verification is an integer "
                 "count, so the curve is finely discretised, not C^1"))
        entries.append(_entry(
            "pcurve_false_rejection", max(r["false_reject"] for r in rows),
            n=len(rows),
            denominator="budget points; value is the worst false-rejection "
                        "rate over all of them",
            method="count over safe plans at each point", source=src))
        if nb:
            entries.append(_entry(
                "predicate_instances_per_topology",
                [min(nb.values()), max(nb.values())], n=len(nb),
                denominator="base-state predicate instances, per topology",
                method="enumeration", source=src,
                note="the physical budget a coverage fraction buys differs "
                     "by this much across topologies"))
        entries.append(_entry(
            "pcurve_timing_plans", pc.get("n_timing_plans"),
            n=pc.get("n_timing_topologies"),
            denominator="plans used for the tau(b) curve, drawn round-robin "
                        "over topologies",
            method="count", source=src,
            note="drawn evenly on purpose: a corpus-order prefix put nearly "
                 "all timing plans on one topology"))

    # ---- coverage curve and family fit ------------------------------------
    fit = _load(Path("out/corpus_v2/fit_interleaved.json"))
    if fit:
        src = "out/corpus_v2/fit_interleaved.json"
        entries.append(_entry(
            "exponential_family_holds_out",
            f"{fit['n_folds_exponential_better']}/{fit['n_folds']}",
            n=fit["n_folds"],
            denominator="held-out topologies where the exponential detection "
                        "family beats an isotonic monotone baseline",
            method="leave-one-topology-out binomial deviance", source=src,
            note="not evidence for the family; it is retained as the "
                 "analytical example that yields the closed forms, and the "
                 "selector never uses it"))
        if fit.get("tau_linear"):
            tl = fit["tau_linear"]
            entries.append(_entry(
                "tau_linear_fit",
                f"tau(b) = {tl['tau0_ms']} + {tl['beta_ms']}b ms",
                n=tl["n_points"],
                denominator="budget points below full coverage",
                method=f"least squares, R2={tl['r2']}", source=src))

    # ---- second agent ------------------------------------------------------
    mc = _load(Path("out/model_comparison.json"))
    if mc:
        src = "out/model_comparison.json"
        for tag in ("a", "b"):
            m = mc[f"marginal_{tag}"]
            entries.append(_entry(
                f"q_model_{tag}", m["q_conditioned"],
                k=m["q_counts"][0], n=m["q_counts"][1],
                denominator=f"{m['model']}: ITS OWN feasible, fulfilling "
                            "plans on the repetition-zero subset",
                method="count", source=src,
                note="the two models' denominators DIFFER; their difference "
                     "is not a paired quantity and carries no p-value"))
        pr = mc["paired"]
        entries.append(_entry(
            "model_paired_discordance",
            f"{pr['discordant_a_only']}/{pr['discordant_b_only']}",
            k=pr["discordant_a_only"] + pr["discordant_b_only"],
            n=pr["n_paired"], denominator=pr["denominator"],
            method=pr["method"], source=src,
            note=f"exact two-sided p={pr['p_exact_two_sided']}; "
                 f"unsafe {pr['a_unsafe']} vs {pr['b_unsafe']} on the paired "
                 "set. Directional only -- do not report as significant"))

    # ---- temporal-order stress suite ---------------------------------------
    tp = _load(Path("out/temporal_v2/summary.json"))
    if tp:
        src = "out/temporal_v2/summary.json"
        entries.append(_entry(
            "temporal_suite_prefix_only", tp.get("prefix_only_unsafe"),
            n=tp.get("n_usable"),
            denominator="plans on the constructed ordering-stress suite, "
                        "where a terminal-safe/prefix-unsafe plan is known "
                        "to exist in the plan space of every instance",
            ci=(f"[0, {tp['prefix_only_upper95']}]"
                if tp.get("prefix_only_upper95") is not None else None),
            method="paired terminal vs prefix on the same plan; "
                   "rule-of-three 95% upper bound", source=src,
            note="reported SEPARATELY from the natural corpus on purpose; "
                 "pooling would manufacture a prefix advantage. Ordering "
                 f"evidence: {tp.get('ordering')}"))
        entries.append(_entry(
            "temporal_suite_misordered_yet_terminal_unsafe",
            (tp.get("ordering") or {}).get("wrong_order"),
            n=tp.get("n_usable"),
            denominator="stress-suite plans that emitted both ordered "
                        "operations in the UNSAFE order",
            method="operation-type matching against the constructive witness",
            source=src,
            note="all of them are unsafe under TERMINAL checking too, which "
                 "is why the prefix-only count is zero despite misordering"))

    # ---- adversarial injection taxonomy ------------------------------------
    # Recomputed from the archived base state rather than read from the run's
    # own output: this is the one place the paper claims prefix checking
    # strictly dominates terminal checking, so the claim should be replayed
    # by the current checker, not trusted from a file.
    inj_dir = Path("out/q_20260723_060529")
    if (inj_dir / "base_state.json").exists():
        try:
            from run_p import detect, load_state
            from run_p_inject import build_injections
            from src.invariants import check_plan

            base = load_state(inj_dir / "base_state.json")
            kept = [(nm, pl) for nm, pl in build_injections(base)
                    if check_plan(base, pl)]
            # L3 is terminal at full coverage, L4 the same coverage checked
            # after every operation, so a plan missed by L3 and caught by L4
            # is terminal-safe and prefix-unsafe by construction.
            prefix_only = [nm for nm, pl in kept
                           if not detect(base, pl, 3) and detect(base, pl, 4)]
            entries.append(_entry(
                "injection_prefix_only", len(prefix_only), n=len(kept),
                denominator="hand-constructed adversarial violations in the "
                            "archived taxonomy",
                method="paired terminal (L3) vs all-prefix (L4) at full "
                       "coverage, recomputed from the archived base state",
                source=str(inj_dir / "base_state.json"),
                note="the existence proof for prefix checking: NOT evidence "
                     "about any agent's error distribution, on which the "
                     f"measured count is zero. families={prefix_only}"))
        except (ImportError, KeyError, ValueError, AssertionError) as exc:
            logger.warning("injection taxonomy replay failed: %s", exc)

    # ---- policy comparison -----------------------------------------------
    if pol:
        src = str(policy_dir / "policy_analysis.json")
        for grp, s_by in sorted((pol.get("by_group") or {}).items()):
            for name, s in sorted(s_by.items()):
                if not s.get("n"):
                    continue
                for key in ("modeled_unsafe_actuation", "safe_completion",
                            "abort"):
                    d = s.get(key)
                    if not d:
                        continue
                    entries.append(_entry(
                        f"{grp}::{name}::{key}", d["rate"], k=d["k"],
                        n=d["n"], ci=_fmt_ci(d),
                        denominator=f"{grp} intents only -- the denominator "
                                    "the closed-loop table reports",
                        method="Wilson (NOT paired/clustered)", source=src,
                        note="Table IV quotes the FEASIBLE group; the "
                             "all-intent entries below use a different "
                             "denominator and must not be interchanged"))
                cost = s.get("cost") or {}
                if grp == "feasible" and cost:
                    entries.append(_entry(
                        f"{grp}::{name}::llm_calls", cost["llm_calls"],
                        n=s["n"],
                        denominator="mean agent calls per feasible intent",
                        method="mean over traces", source=src,
                        note="THE compute measure for this table. The "
                             "wall-clock column is not: the eight policies "
                             "run in a fixed order against one local server, "
                             "so cross-policy second-level differences carry "
                             "cold-start and ordering effects"))
        for name, s in sorted(pol["policies"].items()):
            if not s.get("n"):
                continue
            if s.get("n_plan_changed") is not None:
                entries.append(_entry(
                    f"{name}::plan_changed", s["n_plan_changed"], n=s["n"],
                    denominator="all intents: traces whose final plan differs "
                                "from the round-zero plan",
                    method="count", source=src,
                    note="self-reflection's rounds mostly reaffirm the plan; "
                         "the gate's rejection feedback is what moves it"))
            for key, denom in (
                ("modeled_unsafe_actuation",
                 "all intents run under this policy"),
                ("safe_completion", "all intents run under this policy"),
                ("abort", "all intents run under this policy"),
                ("interception_given_unsafe",
                 "intents whose ROUND-0 plan was unsafe"),
                ("repaired_given_unsafe",
                 "intents whose ROUND-0 plan was unsafe"),
                ("false_kill_given_good",
                 "intents whose ROUND-0 plan was already safe AND fulfilling"),
            ):
                d = s.get(key)
                if not d:
                    continue
                entries.append(_entry(
                    f"{name}::{key}", d["rate"], k=d["k"], n=d["n"],
                    ci=_fmt_ci(d), denominator=denom,
                    method="Wilson (NOT paired/clustered -- see note)",
                    source=src,
                    note="statistical unit is the paired intent, nested in "
                         "topology; these marginal intervals understate "
                         "uncertainty for BETWEEN-policy comparison"))
    # ---- provenance status of every source ---------------------------------
    # A dirty revision cannot describe the code that ran. Record which
    # sources were produced that way rather than let the table imply a
    # single-revision replay that has not been performed.
    dirty: List[str] = []
    unattested: List[str] = []
    all_sources = sorted({e["source"] for e in entries if e.get("source")})
    for path in all_sources:
        blob = _load(Path(path))
        meta = None
        if isinstance(blob, dict):
            m = blob.get("meta")
            meta = m if isinstance(m, dict) else blob
        # source_dirty, not git_dirty: a runner writing into the tracked
        # output tree dirties it for the next runner in the same batch, which
        # says nothing about whether the recorded revision describes the code.
        # Files predating that distinction carry only git_dirty; fall back to
        # it rather than silently scoring them clean.
        flag = None
        if isinstance(meta, dict):
            flag = meta.get("source_dirty")
            if flag is None:
                flag = meta.get("git_dirty")
        if flag is None:
            # A file carrying no provenance at all cannot attest to anything.
            # Scoring it clean is how an audit reports a reassuring number it
            # has not earned, so it is counted separately.
            unattested.append(path)
        elif flag:
            dirty.append(path)
    entries.append(_entry(
        "sources_at_dirty_revision", len(dirty), n=len(all_sources),
        denominator="distinct source files backing this table",
        method="source_dirty flag recorded by each runner; files carrying no "
               "provenance are NOT counted clean, see "
               "sources_without_provenance",
        source="(this table)",
        note=("a source-dirty tree means the recorded commit identifies the "
              "branch point, not the code that ran: " + ", ".join(dirty))
        if dirty else "every attested source was produced at a clean source "
                      "revision"))
    entries.append(_entry(
        "sources_without_provenance", len(unattested), n=len(all_sources),
        denominator="same as sources_at_dirty_revision",
        method="absence of both source_dirty and git_dirty in the file",
        source="(this table)",
        note=("raw inputs rather than derived results, so they record no "
              "runner metadata; the clean-revision claim does not cover "
              "them: " + ", ".join(unattested))
        if unattested else "every source carries provenance"))

    return {"entries": entries,
            "n_entries": len(entries),
            "policy_data_present": pol is not None}


def to_markdown(frozen: Dict[str, Any]) -> str:
    lines = ["# Frozen result numbers", "",
             "Single source of truth for every quantity the paper cites.",
             "Each row states its own denominator: the same name can denote",
             "different quantities that differ only in what they divide by.",
             ""]
    for e in frozen["entries"]:
        val = e["value"]
        val_s = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
        lines.append(f"## `{e['name']}`")
        lines.append(f"- **value**: {val_s}")
        if e["k"] is not None and e["n"] is not None:
            lines.append(f"- **counts**: {e['k']} / {e['n']}")
        elif e["n"] is not None:
            lines.append(f"- **n**: {e['n']}")
        if e["ci95"]:
            lines.append(f"- **95% CI**: {e['ci95']}")
        lines.append(f"- **denominator**: {e['denominator']}")
        lines.append(f"- **method**: {e['method']}")
        lines.append(f"- **source**: `{e['source']}`")
        if e["note"]:
            lines.append(f"- **note**: {e['note']}")
        lines.append("")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="out/corpus_v2")
    p.add_argument("--costbench", default="out/costbench_v3/costbench.json")
    p.add_argument("--policies", default="out/policies_v3")
    p.add_argument("--out", default="../paper/numbers")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    pol_dir = Path(args.policies)
    frozen = build(Path(args.corpus), Path(args.costbench),
                   pol_dir if (pol_dir / "policy_analysis.json").exists()
                   else None)
    base = Path(args.out)
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_suffix(".json").write_text(json.dumps(frozen, indent=1))
    base.with_suffix(".md").write_text(to_markdown(frozen))

    logger.info("%d frozen entries (policy data present: %s)",
                frozen["n_entries"], frozen["policy_data_present"])
    logger.info("-> %s.{json,md}", base)
    if not frozen["policy_data_present"]:
        logger.warning("policy comparison NOT frozen yet: rerun after the "
                       "sweep completes and its analysis is written")
    return 0


if __name__ == "__main__":
    sys.exit(main())

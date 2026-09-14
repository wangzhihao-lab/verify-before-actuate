# Frozen result numbers

Single source of truth for every quantity the paper cites.
Each row states its own denominator: the same name can denote
different quantities that differ only in what they divide by.

## `corpus_size`
- **value**: 500
- **n**: 500
- **denominator**: all generated cells
- **method**: count
- **source**: `out/corpus_v2/analysis.json`
- **note**: usable=499, parse_failures=1

## `q_conditioned`
- **value**: 0.3622
- **counts**: 113 / 312
- **95% CI**: [0.311, 0.417]
- **denominator**: plans that are a-priori FEASIBLE and FULFIL the intent -- the conditioning the renewal model uses
- **method**: Wilson (treats plans as independent)
- **source**: `out/corpus_v2/analysis.json`
- **note**: THE q of the theory. Do not quote the pooled rate.

## `q_conditioned_clustered`
- **value**: 0.3622
- **counts**: 113 / 312
- **95% CI**: [0.328, 0.393]
- **denominator**: same as q_conditioned
- **method**: cluster bootstrap over 10 topologies
- **source**: `out/corpus_v2/analysis.json`
- **note**: only 10 clusters (<20): bootstrap interval is imprecise; report the wider of this and the Wilson interval

## `n_certified`
- **value**: {"feasible": 328, "undecided": 52, "infeasible": 120}
- **n**: 500
- **denominator**: generated cells, by CERTIFIED feasibility verdict
- **method**: witness construction for feasible, necessary condition for infeasible, neither for undecided
- **source**: `out/corpus_v2/analysis.json`
- **note**: a feasible verdict carries a plan verified prefix-safe and intent-fulfilling; the corpus's own a-priori label asserted feasibility for two intent kinds and was wrong often enough to move every rate conditioned on it

## `undecided_unsafe_rate`
- **value**: 1.0
- **counts**: 52 / 52
- **95% CI**: [0.931, 1.000]
- **denominator**: intents whose feasibility the certifier could not decide either way
- **method**: Wilson
- **source**: `out/corpus_v2/analysis.json`
- **note**: these behave like the certified-infeasible branch, not like the feasible one, which is why they are reported apart from both rather than pooled into either

## `q_upper_if_undecided_feasible`
- **value**: 0.4518
- **counts**: 164 / 363
- **95% CI**: [0.401, 0.503]
- **denominator**: certified-feasible PLUS undecided, fulfilling plans
- **method**: Wilson
- **source**: `out/corpus_v2/analysis.json`
- **note**: the most adverse reading of the undecided remainder: q cannot exceed this even if every undecided intent turned out to admit a safe plan

## `infeasible_unsafe_rate`
- **value**: 0.8908
- **counts**: 106 / 119
- **95% CI**: [0.822, 0.935]
- **denominator**: a-priori INFEASIBLE intents only
- **method**: Wilson
- **source**: `out/corpus_v2/analysis.json`
- **note**: a property of the REQUEST, not the agent's error rate; must never be pooled into q

## `abstention_on_feasible`
- **value**: 0.0
- **counts**: 0 / 328
- **95% CI**: [0.000, 0.012]
- **denominator**: feasible, parseable generations
- **method**: Wilson
- **source**: `out/corpus_v2/analysis.json`
- **note**: the agent never declines, including on provably impossible requests

## `q_bare`
- **value**: 0.4744
- **counts**: 74 / 156
- **95% CI**: [0.425, 0.521]
- **denominator**: feasible & fulfilled generations, bare prompt
- **method**: cluster bootstrap over 10 topologies
- **source**: `out/corpus_v2/analysis.json`

## `q_guarded`
- **value**: 0.25
- **counts**: 39 / 156
- **95% CI**: [0.203, 0.288]
- **denominator**: feasible & fulfilled generations, guarded prompt
- **method**: cluster bootstrap over 10 topologies
- **source**: `out/corpus_v2/analysis.json`

## `p_conditioned::smt/term/b1`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::smt/term/b2`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::smt/term/b3`
- **value**: 1.0
- **counts**: 113 / 113
- **95% CI**: [0.967, 1.000]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::smt/prefix/b1`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::smt/prefix/b2`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::smt/prefix/b3`
- **value**: 1.0
- **counts**: 113 / 113
- **95% CI**: [0.967, 1.000]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::twin/term/b1`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::twin/term/b2`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::twin/term/b3`
- **value**: 1.0
- **counts**: 113 / 113
- **95% CI**: [0.967, 1.000]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::twin/prefix/b1`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::twin/prefix/b2`
- **value**: 0.3009
- **counts**: 34 / 113
- **95% CI**: [0.224, 0.391]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `p_conditioned::twin/prefix/b3`
- **value**: 1.0
- **counts**: 113 / 113
- **95% CI**: [0.967, 1.000]
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q, so the two can be combined in J
- **method**: rescoring the archived corpus
- **source**: `out/corpus_v2/analysis.json`
- **note**: false rejection 0/199; the corpus-wide detection over all usable plans uses a different denominator and must not be interchanged

## `prefix_marginal_b1`
- **value**: 0.00601
- **counts**: 0 / 499
- **denominator**: all usable plans, PAIRED: the same plan is scored under both temporal scopes
- **method**: rule-of-three 95% upper bound (zero events)
- **source**: `out/corpus_v2/analysis.json`
- **note**: both_unsafe=116, terminal_only=0, both_safe=383

## `prefix_marginal_b2`
- **value**: 0.00601
- **counts**: 0 / 499
- **denominator**: all usable plans, PAIRED: the same plan is scored under both temporal scopes
- **method**: rule-of-three 95% upper bound (zero events)
- **source**: `out/corpus_v2/analysis.json`
- **note**: both_unsafe=125, terminal_only=0, both_safe=374

## `prefix_marginal_b3`
- **value**: 0.00601
- **counts**: 0 / 499
- **denominator**: all usable plans, PAIRED: the same plan is scored under both temporal scopes
- **method**: rule-of-three 95% upper bound (zero events)
- **source**: `out/corpus_v2/analysis.json`
- **note**: both_unsafe=278, terminal_only=0, both_safe=221

## `generation_seconds_median`
- **value**: 5.748
- **n**: 499
- **denominator**: per generation call, wall clock
- **method**: median
- **source**: `out/corpus_v2/analysis.json`
- **note**: decode-only median=3.9295s; report the system boundary explicitly

## `tau_A2_non_decreasing`
- **value**: {"smt": false, "twin": true}
- **n**: 312
- **denominator**: per (network, mode, scope) series, budgets compared within a series
- **method**: envelope series, tolerance-based on the measurement
- **source**: `out/costbench_v3/costbench.json`
- **note**: worst repeat CV=0.9282, unstable cells=1. A2 is an ASSUMPTION of the theory held to the measurement here, not something the encoding closes: the envelope maximises over clean and violating plans, and on a violating state the integrity layer does add constraints

## `tau_A2_detail::smt`
- **value**: {"real_decreases": 2, "steps_adding_no_base_disjunct": 52, "flat_within_tolerance": 8, "n_series": 52}
- **denominator**: budget steps within (network, scope) series
- **method**: structural where constraint counts are available, tolerance-based otherwise
- **source**: `out/costbench_v3/costbench.json`
- **note**: giul39/prefix b1->b2 -7.25% with 49 constraints added; norway/term b2->b3 -5.07% with 0 constraints added

## `tau_A2_detail::twin`
- **value**: {"real_decreases": 0, "steps_adding_no_base_disjunct": 0, "flat_within_tolerance": 0, "n_series": 52}
- **denominator**: budget steps within (network, scope) series
- **method**: structural where constraint counts are available, tolerance-based otherwise
- **source**: `out/costbench_v3/costbench.json`
- **note**: no measured decrease

## `smt_b3_extra_disjuncts_on_clean_base`
- **value**: 0
- **n**: 26
- **denominator**: topologies; value is the LARGEST number of extra solver disjuncts the integrity layer adds at b=3 on a clean BASE state
- **method**: counting the disjuncts the SMT encoder emits
- **source**: `out/costbench_v3/costbench.json`
- **note**: zero everywhere, but this does NOT make the step free: the cost envelope also covers violating states, where the layer does emit disjuncts, and depth three runs a structural prepass shallower depths skip

## `tau_range_smt_prefix_b3`
- **value**: [40.8196, 707.0485]
- **denominator**: dfn-bwin (10 nodes) to brain (161 nodes)
- **method**: mean of per-plan medians, envelope
- **source**: `out/costbench_v3/costbench.json`

## `tau_range_twin_prefix_b3`
- **value**: [95.4505, 3368.1065]
- **denominator**: dfn-bwin to brain
- **method**: mean of per-plan medians, envelope
- **source**: `out/costbench_v3/costbench.json`

## `loto_oracle_match`
- **value**: {"0.1": "10/10", "0.3": "10/10", "1.0": "10/10", "3.0": "10/10", "10.0": "9/10", "20.0": "10/10", "30.0": "10/10", "50.0": "10/10", "70.0": "10/10", "100.0": "10/10", "300.0": "10/10", "1000.0": "10/10", "10000.0": "10/10"}
- **n**: 10
- **denominator**: held-out topologies, one fold each, per risk price
- **method**: leave-one-topology-out; calibration and evaluation never share a topology
- **source**: `out/corpus_v2/selection.json`

## `loto_oracle_match_total`
- **value**: 129/130
- **counts**: 129 / 130
- **denominator**: every (held-out topology, risk price) selection in the sweep
- **method**: leave-one-topology-out against a PLUG-IN oracle: the profile minimising the same closed form under the held-out topology's own q, p, tau, G -- NOT a closed-loop optimum
- **source**: `out/corpus_v2/selection.json`
- **note**: quote this, not a per-price row; the misses are at the coverage-depth switch boundary

## `loto_regret_rel_mean_pct`
- **value**: {"0.1": 0.0, "0.3": 0.0, "1.0": 0.0, "3.0": 0.0, "10.0": 0.1001, "20.0": 0.0, "30.0": 0.0, "50.0": 0.0, "70.0": 0.0, "100.0": 0.0, "300.0": 0.0, "1000.0": 0.0, "10000.0": 0.0}
- **n**: 10
- **denominator**: mean held-out regret against the plug-in oracle, as a percentage of the oracle objective
- **method**: LOTO
- **source**: `out/corpus_v2/selection.json`
- **note**: nonzero only at R=10, one step below the b1->b3 switch price of R=20

## `loto_profile_space`
- **value**: 6
- **denominator**: profiles the selector searches: 2 temporal scopes x 3 budgets on the SMT backend
- **method**: count
- **source**: `out/corpus_v2/selection.json`
- **note**: the twin backend is NOT a candidate -- the agent corpus gives no per-topology detection estimate for it, so no 3-dimensional (e,m,b) selection is claimed

## `loto_gain_vs_fixed_deep`
- **value**: {"0.1": 27.639, "0.3": 27.234, "1.0": 25.817, "3.0": 21.768, "10.0": 7.597, "20.0": 0.537, "30.0": 0.537, "50.0": 0.537, "70.0": 0.537, "100.0": 0.537, "300.0": 0.537, "1000.0": 0.537, "10000.0": 0.537}
- **denominator**: mean objective over held-out folds, relative to the always-deepest fixed profile
- **method**: LOTO
- **source**: `out/corpus_v2/selection.json`
- **note**: gain is concentrated at low-to-moderate risk price; at high R every profile converges to b=3 and the residual gain is only the cheaper temporal scope

## `loto_selected_profiles`
- **value**: {"0.1": ["smt/term/b1"], "0.3": ["smt/term/b1"], "1.0": ["smt/term/b1"], "3.0": ["smt/term/b1"], "10.0": ["smt/term/b1"], "20.0": ["smt/term/b3"], "30.0": ["smt/term/b3"], "50.0": ["smt/term/b3"], "70.0": ["smt/term/b3"], "100.0": ["smt/term/b3"], "300.0": ["smt/term/b3"], "1000.0": ["smt/term/b3"], "10000.0": ["smt/term/b3"]}
- **denominator**: profile chosen by the calibrated rule per risk price
- **method**: LOTO
- **source**: `out/corpus_v2/selection.json`
- **note**: 'ours' denotes THIS RULE, never a fixed profile; the rule selects terminal scope, not prefix

## `tau_over_G_published_range`
- **value**: [0.00275, 0.12102]
- **n**: 9
- **denominator**: RESERVATION tau (full traversal, early exit disabled) over median generation latency, both measured in the same run on the same topology
- **method**: median of 3 warm generations per rung
- **source**: `out/crossover_v3/crossover.json`
- **note**: NOT the same quantity as the verification time a trace actually pays, which allows early exit on short agent plans; the reservation is what the renewal model uses

## `tau_over_G_largest_published`
- **value**: 0.12102
- **denominator**: ta2 (65 nodes, 108 links)
- **method**: same-run reservation tau over warm median G
- **source**: `out/crossover_v3/crossover.json`

## `tau_over_G_stress_max`
- **value**: 0.37913
- **n**: 3
- **denominator**: synthetic scalability rungs beyond the largest published instance
- **method**: same-run reservation tau over warm median G
- **source**: `out/crossover_v3/crossover.json`
- **note**: a scalability probe, not a sample from any deployed topology distribution

## `q_across_seeds`
- **value**: [0.2245, 0.303]
- **n**: 3
- **denominator**: q conditioned on feasible and fulfilling plans, one value per master seed
- **method**: range over master seeds
- **source**: `out/seed_comparison.json`
- **note**: quote this range, not a single seed's point estimate; the master seed fixes synthesized attributes, demand sampling and intent targets

## `prefix_only_across_seeds`
- **value**: 0
- **n**: 695
- **denominator**: all usable plans pooled over master seeds, PAIRED terminal vs prefix on the same plan
- **method**: count
- **source**: `out/seed_comparison.json`
- **note**: zero observed; not a claim that the probability is zero

## `abstentions_across_seeds`
- **value**: 0
- **n**: 695
- **denominator**: all usable plans pooled over master seeds
- **method**: count
- **source**: `out/seed_comparison.json`

## `independent_state_agreement`
- **value**: 1.0
- **counts**: 693 / 693
- **denominator**: every state every plan passes through, compared between the reference checker and an independent implementation
- **method**: exact match on the violation set
- **source**: `out/corpus_v2/crosscheck.json`
- **note**: predicate evaluation over the three modelled invariant classes; the transition function is shared, so transition semantics are not independently validated

## `loss_events_transition_only`
- **value**: 10
- **n**: 278
- **denominator**: loss events arising from an operation the transition function refuses, where no state changes
- **method**: count
- **source**: `out/corpus_v2/crosscheck.json`
- **note**: outside the reach of any state-based independent checker

## `pcurve_detection_range`
- **value**: [0.044248, 0.973451]
- **counts**: 20 / 113
- **denominator**: loss events among FEASIBLE, FULFILLING plans -- the same population as q; p reaches 1 only at full coverage, where the checker is the oracle
- **method**: rescoring the archived corpus at each budget point
- **source**: `out/corpus_v2/pcurve_interleaved.json`
- **note**: the sweep axis is a FRACTION of each topology's own base predicate count, so one row pools different absolute budgets; the budget within one verification is an integer count, so the curve is finely discretised, not C^1

## `pcurve_false_rejection`
- **value**: 0.0
- **n**: 21
- **denominator**: budget points; value is the worst false-rejection rate over all of them
- **method**: count over safe plans at each point
- **source**: `out/corpus_v2/pcurve_interleaved.json`

## `predicate_instances_per_topology`
- **value**: [126, 173]
- **n**: 10
- **denominator**: base-state predicate instances, per topology
- **method**: enumeration
- **source**: `out/corpus_v2/pcurve_interleaved.json`
- **note**: the physical budget a coverage fraction buys differs by this much across topologies

## `pcurve_timing_plans`
- **value**: 60
- **n**: 10
- **denominator**: plans used for the tau(b) curve, drawn round-robin over topologies
- **method**: count
- **source**: `out/corpus_v2/pcurve_interleaved.json`
- **note**: drawn evenly on purpose: a corpus-order prefix put nearly all timing plans on one topology

## `exponential_family_holds_out`
- **value**: 2/10
- **n**: 10
- **denominator**: held-out topologies where the exponential detection family beats an isotonic monotone baseline
- **method**: leave-one-topology-out binomial deviance
- **source**: `out/corpus_v2/fit_interleaved.json`
- **note**: not evidence for the family; it is retained as the analytical example that yields the closed forms, and the selector never uses it

## `tau_linear_fit`
- **value**: tau(b) = 0.8303 + 11.9037b ms
- **n**: 20
- **denominator**: budget points below full coverage
- **method**: least squares, R2=0.9955
- **source**: `out/corpus_v2/fit_interleaved.json`

## `q_model_a`
- **value**: 0.303
- **counts**: 20 / 66
- **denominator**: qwen2.5:7b-instruct-q8_0: ITS OWN feasible, fulfilling plans on the repetition-zero subset
- **method**: count
- **source**: `out/model_comparison.json`
- **note**: the two models' denominators DIFFER; their difference is not a paired quantity and carries no p-value

## `q_model_b`
- **value**: 0.1846
- **counts**: 12 / 65
- **denominator**: huihui-qwen3-vl-32b-instruct-abliterated-i1: ITS OWN feasible, fulfilling plans on the repetition-zero subset
- **method**: count
- **source**: `out/model_comparison.json`
- **note**: the two models' denominators DIFFER; their difference is not a paired quantity and carries no p-value

## `model_paired_discordance`
- **value**: 5/0
- **counts**: 5 / 63
- **denominator**: cells where BOTH models produced a fulfilling plan for an a-priori feasible intent
- **method**: exact McNemar (two-sided binomial on discordant pairs)
- **source**: `out/model_comparison.json`
- **note**: exact two-sided p=0.0625; unsafe 17 vs 12 on the paired set. Directional only -- do not report as significant

## `temporal_suite_prefix_only`
- **value**: 0
- **n**: 117
- **95% CI**: [0, 0.02564]
- **denominator**: plans on the constructed ordering-stress suite, where a terminal-safe/prefix-unsafe plan is known to exist in the plan space of every instance
- **method**: paired terminal vs prefix on the same plan; rule-of-three 95% upper bound
- **source**: `out/temporal_v2/summary.json`
- **note**: reported SEPARATELY from the natural corpus on purpose; pooling would manufacture a prefix advantage. Ordering evidence: {'correct_order': 33, 'omitted': 61, 'wrong_order': 6, 'ambiguous': 17}

## `temporal_suite_misordered_yet_terminal_unsafe`
- **value**: 6
- **n**: 117
- **denominator**: stress-suite plans that emitted both ordered operations in the UNSAFE order
- **method**: operation-type matching against the constructive witness
- **source**: `out/temporal_v2/summary.json`
- **note**: all of them are unsafe under TERMINAL checking too, which is why the prefix-only count is zero despite misordering

## `injection_prefix_only`
- **value**: 2
- **n**: 8
- **denominator**: hand-constructed adversarial violations in the archived taxonomy
- **method**: paired terminal (L3) vs all-prefix (L4) at full coverage, recomputed from the archived base state
- **source**: `out/q_20260723_060529/base_state.json`
- **note**: the existence proof for prefix checking: NOT evidence about any agent's error distribution, on which the measured count is zero. families=['VI4_temp_overload', 'VI4_disable_before_reroute']

## `feasible::no_verify::modeled_unsafe_actuation`
- **value**: 0.3833
- **counts**: 23 / 60
- **95% CI**: [0.271, 0.510]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::no_verify::safe_completion`
- **value**: 0.5833
- **counts**: 35 / 60
- **95% CI**: [0.457, 0.699]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::no_verify::abort`
- **value**: 0.0333
- **counts**: 2 / 60
- **95% CI**: [0.009, 0.114]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::no_verify::llm_calls`
- **value**: 1
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `feasible::reflect/r1::modeled_unsafe_actuation`
- **value**: 0.3833
- **counts**: 23 / 60
- **95% CI**: [0.271, 0.510]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::reflect/r1::safe_completion`
- **value**: 0.5833
- **counts**: 35 / 60
- **95% CI**: [0.457, 0.699]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::reflect/r1::abort`
- **value**: 0.0333
- **counts**: 2 / 60
- **95% CI**: [0.009, 0.114]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::reflect/r1::llm_calls`
- **value**: 2
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `feasible::reflect/r3::modeled_unsafe_actuation`
- **value**: 0.3833
- **counts**: 23 / 60
- **95% CI**: [0.271, 0.510]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::reflect/r3::safe_completion`
- **value**: 0.5833
- **counts**: 35 / 60
- **95% CI**: [0.457, 0.699]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::reflect/r3::abort`
- **value**: 0.0333
- **counts**: 2 / 60
- **95% CI**: [0.009, 0.114]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::reflect/r3::llm_calls`
- **value**: 4
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `feasible::static_rules::modeled_unsafe_actuation`
- **value**: 0.25
- **counts**: 15 / 60
- **95% CI**: [0.158, 0.372]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::static_rules::safe_completion`
- **value**: 0.5833
- **counts**: 35 / 60
- **95% CI**: [0.457, 0.699]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::static_rules::abort`
- **value**: 0.1667
- **counts**: 10 / 60
- **95% CI**: [0.093, 0.280]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::static_rules::llm_calls`
- **value**: 1
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `feasible::verify:smt/prefix/b1::modeled_unsafe_actuation`
- **value**: 0.3167
- **counts**: 19 / 60
- **95% CI**: [0.213, 0.442]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b1::safe_completion`
- **value**: 0.5833
- **counts**: 35 / 60
- **95% CI**: [0.457, 0.699]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b1::abort`
- **value**: 0.1
- **counts**: 6 / 60
- **95% CI**: [0.047, 0.202]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b1::llm_calls`
- **value**: 1.1667
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `feasible::verify:smt/prefix/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 60
- **95% CI**: [0.000, 0.060]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b3::safe_completion`
- **value**: 0.7833
- **counts**: 47 / 60
- **95% CI**: [0.664, 0.869]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b3::abort`
- **value**: 0.2167
- **counts**: 13 / 60
- **95% CI**: [0.131, 0.336]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b3::llm_calls`
- **value**: 1.8167
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `feasible::verify:smt/prefix/b3/nowit::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 60
- **95% CI**: [0.000, 0.060]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b3/nowit::safe_completion`
- **value**: 0.75
- **counts**: 45 / 60
- **95% CI**: [0.628, 0.842]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b3/nowit::abort`
- **value**: 0.25
- **counts**: 15 / 60
- **95% CI**: [0.158, 0.372]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/prefix/b3/nowit::llm_calls`
- **value**: 1.85
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `feasible::verify:smt/term/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 60
- **95% CI**: [0.000, 0.060]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/term/b3::safe_completion`
- **value**: 0.7833
- **counts**: 47 / 60
- **95% CI**: [0.664, 0.869]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/term/b3::abort`
- **value**: 0.2167
- **counts**: 13 / 60
- **95% CI**: [0.131, 0.336]
- **denominator**: feasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `feasible::verify:smt/term/b3::llm_calls`
- **value**: 1.8167
- **n**: 60
- **denominator**: mean agent calls per feasible intent
- **method**: mean over traces
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: THE compute measure for this table. The wall-clock column is not: the eight policies run in a fixed order against one local server, so cross-policy second-level differences carry cold-start and ordering effects

## `infeasible::no_verify::modeled_unsafe_actuation`
- **value**: 0.9062
- **counts**: 29 / 32
- **95% CI**: [0.758, 0.968]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::no_verify::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::no_verify::abort`
- **value**: 0.0938
- **counts**: 3 / 32
- **95% CI**: [0.032, 0.242]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::reflect/r1::modeled_unsafe_actuation`
- **value**: 0.9062
- **counts**: 29 / 32
- **95% CI**: [0.758, 0.968]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::reflect/r1::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::reflect/r1::abort`
- **value**: 0.0938
- **counts**: 3 / 32
- **95% CI**: [0.032, 0.242]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::reflect/r3::modeled_unsafe_actuation`
- **value**: 0.875
- **counts**: 28 / 32
- **95% CI**: [0.719, 0.950]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::reflect/r3::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::reflect/r3::abort`
- **value**: 0.125
- **counts**: 4 / 32
- **95% CI**: [0.050, 0.281]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::static_rules::modeled_unsafe_actuation`
- **value**: 0.625
- **counts**: 20 / 32
- **95% CI**: [0.453, 0.771]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::static_rules::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::static_rules::abort`
- **value**: 0.375
- **counts**: 12 / 32
- **95% CI**: [0.229, 0.547]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b1::modeled_unsafe_actuation`
- **value**: 0.3438
- **counts**: 11 / 32
- **95% CI**: [0.204, 0.517]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b1::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b1::abort`
- **value**: 0.6562
- **counts**: 21 / 32
- **95% CI**: [0.483, 0.796]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b3::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b3::abort`
- **value**: 1.0
- **counts**: 32 / 32
- **95% CI**: [0.893, 1.000]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b3/nowit::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b3/nowit::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/prefix/b3/nowit::abort`
- **value**: 1.0
- **counts**: 32 / 32
- **95% CI**: [0.893, 1.000]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/term/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/term/b3::safe_completion`
- **value**: 0.0
- **counts**: 0 / 32
- **95% CI**: [0.000, 0.107]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `infeasible::verify:smt/term/b3::abort`
- **value**: 1.0
- **counts**: 32 / 32
- **95% CI**: [0.893, 1.000]
- **denominator**: infeasible intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::no_verify::modeled_unsafe_actuation`
- **value**: 0.875
- **counts**: 7 / 8
- **95% CI**: [0.529, 0.978]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::no_verify::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::no_verify::abort`
- **value**: 0.125
- **counts**: 1 / 8
- **95% CI**: [0.022, 0.471]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::reflect/r1::modeled_unsafe_actuation`
- **value**: 0.875
- **counts**: 7 / 8
- **95% CI**: [0.529, 0.978]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::reflect/r1::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::reflect/r1::abort`
- **value**: 0.125
- **counts**: 1 / 8
- **95% CI**: [0.022, 0.471]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::reflect/r3::modeled_unsafe_actuation`
- **value**: 0.875
- **counts**: 7 / 8
- **95% CI**: [0.529, 0.978]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::reflect/r3::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::reflect/r3::abort`
- **value**: 0.125
- **counts**: 1 / 8
- **95% CI**: [0.022, 0.471]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::static_rules::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::static_rules::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::static_rules::abort`
- **value**: 1.0
- **counts**: 8 / 8
- **95% CI**: [0.676, 1.000]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b1::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b1::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b1::abort`
- **value**: 1.0
- **counts**: 8 / 8
- **95% CI**: [0.676, 1.000]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b3::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b3::abort`
- **value**: 1.0
- **counts**: 8 / 8
- **95% CI**: [0.676, 1.000]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b3/nowit::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b3/nowit::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/prefix/b3/nowit::abort`
- **value**: 1.0
- **counts**: 8 / 8
- **95% CI**: [0.676, 1.000]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/term/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/term/b3::safe_completion`
- **value**: 0.0
- **counts**: 0 / 8
- **95% CI**: [0.000, 0.324]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `unknown::verify:smt/term/b3::abort`
- **value**: 1.0
- **counts**: 8 / 8
- **95% CI**: [0.676, 1.000]
- **denominator**: unknown intents only -- the denominator the closed-loop table reports
- **method**: Wilson (NOT paired/clustered)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: Table IV quotes the FEASIBLE group; the all-intent entries below use a different denominator and must not be interchanged

## `no_verify::plan_changed`
- **value**: 0
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `no_verify::modeled_unsafe_actuation`
- **value**: 0.59
- **counts**: 59 / 100
- **95% CI**: [0.492, 0.681]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `no_verify::safe_completion`
- **value**: 0.35
- **counts**: 35 / 100
- **95% CI**: [0.264, 0.448]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `no_verify::abort`
- **value**: 0.06
- **counts**: 6 / 100
- **95% CI**: [0.028, 0.125]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `no_verify::interception_given_unsafe`
- **value**: 0.0328
- **counts**: 2 / 61
- **95% CI**: [0.009, 0.112]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `no_verify::repaired_given_unsafe`
- **value**: 0.0
- **counts**: 0 / 61
- **95% CI**: [0.000, 0.059]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `no_verify::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r1::plan_changed`
- **value**: 4
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `reflect/r1::modeled_unsafe_actuation`
- **value**: 0.59
- **counts**: 59 / 100
- **95% CI**: [0.492, 0.681]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r1::safe_completion`
- **value**: 0.35
- **counts**: 35 / 100
- **95% CI**: [0.264, 0.448]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r1::abort`
- **value**: 0.06
- **counts**: 6 / 100
- **95% CI**: [0.028, 0.125]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r1::interception_given_unsafe`
- **value**: 0.0328
- **counts**: 2 / 61
- **95% CI**: [0.009, 0.112]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r1::repaired_given_unsafe`
- **value**: 0.0
- **counts**: 0 / 61
- **95% CI**: [0.000, 0.059]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r1::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r3::plan_changed`
- **value**: 6
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `reflect/r3::modeled_unsafe_actuation`
- **value**: 0.58
- **counts**: 58 / 100
- **95% CI**: [0.482, 0.672]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r3::safe_completion`
- **value**: 0.35
- **counts**: 35 / 100
- **95% CI**: [0.264, 0.448]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r3::abort`
- **value**: 0.07
- **counts**: 7 / 100
- **95% CI**: [0.034, 0.138]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r3::interception_given_unsafe`
- **value**: 0.0492
- **counts**: 3 / 61
- **95% CI**: [0.017, 0.135]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r3::repaired_given_unsafe`
- **value**: 0.0
- **counts**: 0 / 61
- **95% CI**: [0.000, 0.059]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `reflect/r3::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `static_rules::plan_changed`
- **value**: 0
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `static_rules::modeled_unsafe_actuation`
- **value**: 0.35
- **counts**: 35 / 100
- **95% CI**: [0.264, 0.448]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `static_rules::safe_completion`
- **value**: 0.35
- **counts**: 35 / 100
- **95% CI**: [0.264, 0.448]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `static_rules::abort`
- **value**: 0.3
- **counts**: 30 / 100
- **95% CI**: [0.219, 0.396]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `static_rules::interception_given_unsafe`
- **value**: 0.4262
- **counts**: 26 / 61
- **95% CI**: [0.310, 0.551]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `static_rules::repaired_given_unsafe`
- **value**: 0.0
- **counts**: 0 / 61
- **95% CI**: [0.000, 0.059]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `static_rules::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b1::plan_changed`
- **value**: 27
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `verify:smt/prefix/b1::modeled_unsafe_actuation`
- **value**: 0.3
- **counts**: 30 / 100
- **95% CI**: [0.219, 0.396]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b1::safe_completion`
- **value**: 0.35
- **counts**: 35 / 100
- **95% CI**: [0.264, 0.448]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b1::abort`
- **value**: 0.35
- **counts**: 35 / 100
- **95% CI**: [0.264, 0.448]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b1::interception_given_unsafe`
- **value**: 0.5082
- **counts**: 31 / 61
- **95% CI**: [0.386, 0.629]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b1::repaired_given_unsafe`
- **value**: 0.0
- **counts**: 0 / 61
- **95% CI**: [0.000, 0.059]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b1::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3::plan_changed`
- **value**: 54
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `verify:smt/prefix/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 100
- **95% CI**: [0.000, 0.037]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3::safe_completion`
- **value**: 0.47
- **counts**: 47 / 100
- **95% CI**: [0.375, 0.567]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3::abort`
- **value**: 0.53
- **counts**: 53 / 100
- **95% CI**: [0.433, 0.625]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3::interception_given_unsafe`
- **value**: 1.0
- **counts**: 61 / 61
- **95% CI**: [0.941, 1.000]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3::repaired_given_unsafe`
- **value**: 0.1967
- **counts**: 12 / 61
- **95% CI**: [0.116, 0.313]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3/nowit::plan_changed`
- **value**: 41
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `verify:smt/prefix/b3/nowit::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 100
- **95% CI**: [0.000, 0.037]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3/nowit::safe_completion`
- **value**: 0.45
- **counts**: 45 / 100
- **95% CI**: [0.356, 0.548]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3/nowit::abort`
- **value**: 0.55
- **counts**: 55 / 100
- **95% CI**: [0.452, 0.644]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3/nowit::interception_given_unsafe`
- **value**: 1.0
- **counts**: 61 / 61
- **95% CI**: [0.941, 1.000]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3/nowit::repaired_given_unsafe`
- **value**: 0.1639
- **counts**: 10 / 61
- **95% CI**: [0.092, 0.276]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/prefix/b3/nowit::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/term/b3::plan_changed`
- **value**: 54
- **n**: 100
- **denominator**: all intents: traces whose final plan differs from the round-zero plan
- **method**: count
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: self-reflection's rounds mostly reaffirm the plan; the gate's rejection feedback is what moves it

## `verify:smt/term/b3::modeled_unsafe_actuation`
- **value**: 0.0
- **counts**: 0 / 100
- **95% CI**: [0.000, 0.037]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/term/b3::safe_completion`
- **value**: 0.47
- **counts**: 47 / 100
- **95% CI**: [0.375, 0.567]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/term/b3::abort`
- **value**: 0.53
- **counts**: 53 / 100
- **95% CI**: [0.433, 0.625]
- **denominator**: all intents run under this policy
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/term/b3::interception_given_unsafe`
- **value**: 1.0
- **counts**: 61 / 61
- **95% CI**: [0.941, 1.000]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/term/b3::repaired_given_unsafe`
- **value**: 0.1967
- **counts**: 12 / 61
- **95% CI**: [0.116, 0.313]
- **denominator**: intents whose ROUND-0 plan was unsafe
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `verify:smt/term/b3::false_kill_given_good`
- **value**: 0.0
- **counts**: 0 / 35
- **95% CI**: [0.000, 0.099]
- **denominator**: intents whose ROUND-0 plan was already safe AND fulfilling
- **method**: Wilson (NOT paired/clustered -- see note)
- **source**: `out/policies_v3/policy_analysis.json`
- **note**: statistical unit is the paired intent, nested in topology; these marginal intervals understate uncertainty for BETWEEN-policy comparison

## `sources_at_dirty_revision`
- **value**: 0
- **n**: 12
- **denominator**: distinct source files backing this table
- **method**: source_dirty flag recorded by each runner; files carrying no provenance are NOT counted clean, see sources_without_provenance
- **source**: `(this table)`
- **note**: every attested source was produced at a clean source revision

## `sources_without_provenance`
- **value**: 1
- **n**: 12
- **denominator**: same as sources_at_dirty_revision
- **method**: absence of both source_dirty and git_dirty in the file
- **source**: `(this table)`
- **note**: raw inputs rather than derived results, so they record no runner metadata; the clean-revision claim does not cover them: out/q_20260723_060529/base_state.json

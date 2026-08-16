"""Generate the supplementary tables from archived results.

Every table here reports something the paper states only in aggregate,
because 13 pages could not hold the detail. Generated rather than
transcribed, for the same reason the frozen table is: a hand-copied number
is a number that can drift from the run that produced it.

    PYTHONPATH=. .venv/bin/python run_supplement_tables.py \
        --out ../artifact/supp_tables.tex
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("run_supplement_tables")

PROFILE_SHORT = {"smt/term/b1": "T1", "smt/term/b2": "T2", "smt/term/b3": "T3",
                 "smt/prefix/b1": "P1", "smt/prefix/b2": "P2",
                 "smt/prefix/b3": "P3"}

INJECTION_LABEL = {
    "VI1_flow_overload": "Flow bandwidth above link capacity",
    "VI1_slice_overload": "Slice reservation above link capacity",
    "VI2_scale_down": "Replicas cut below SLA on a tight path",
    "VI3_acl_conflict": "Contradictory ACL pair",
    "VI3_ghost_entity": "Operation on a nonexistent flow",
    "VI3_disable_no_reroute": "Transit node disabled, flows left on it",
    "VI4_temp_overload": "Overload then restore (transient)",
    "VI4_disable_before_reroute": "Disable before reroute (transient)",
}


def esc(s: Any) -> str:
    """Escape the LaTeX specials that occur in these values.

    Braces must be escaped too: several frozen entries hold JSON objects as
    their value, and an unescaped ``{`` from ``{"feasible": 328, ...}`` opens
    a group TeX then spends the rest of the table trying to close.

    Order matters. Backslashes are stashed first so that the braces in the
    ``\\textbackslash{}`` replacement are not themselves escaped afterwards.
    """
    s = str(s).replace("\\", "\x00")
    s = s.replace("{", r"\{").replace("}", r"\}")
    s = (s.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
         .replace("#", r"\#").replace("$", r"\$"))
    return s.replace("\x00", r"\textbackslash{}")


def breakable(s: str) -> str:
    """Allow line breaks inside long identifiers.

    Entry names are joined by ``/``, ``::`` and ``_``, none of which TeX
    treats as a break opportunity, so a p-column cannot wrap them and they
    run into the next column instead. Applied AFTER escaping, hence the
    escaped ``\\_`` rather than a bare underscore.
    """
    return (s.replace("/", r"/\allowbreak ").replace(":", r":\allowbreak ")
            .replace(r"\_", r"\_\allowbreak "))


def trunc(s: Any, n: int) -> str:
    """Truncate THEN escape, never the other way round.

    Escaping first and cutting after can slice an escape sequence in half:
    ``\\_`` becomes a bare backslash, which then escapes whatever character
    follows it -- in practice the brace closing the cell, which swallows the
    rest of the table.
    """
    raw = str(s)
    return esc(raw if len(raw) <= n else raw[:n - 1] + "…")


def table_injections(base_state: Path) -> str:
    """S1: which depths catch each adversarial injection.

    Recomputed from the archived base state with the current checker, so
    this table and the frozen table's injection_prefix_only entry cannot
    disagree.
    """
    from run_p import detect, load_state
    from run_p_inject import build_injections
    from src.invariants import check_plan

    base = load_state(base_state)
    kept = [(n, p) for n, p in build_injections(base) if check_plan(base, p)]
    rows = []
    for name, plan in kept:
        d = [detect(base, plan, lv) for lv in (1, 2, 3, 4)]
        mark = ["\\checkmark" if x else "--" for x in d]
        prefix_only = (not d[2]) and d[3]
        label = INJECTION_LABEL.get(name, name)
        if prefix_only:
            label = r"\textbf{" + label + "}"
        rows.append(f"{label} & " + " & ".join(mark) + r" \\")

    body = "\n".join(rows)
    return rf"""
\subsection{{Adversarial injection taxonomy}}
\label{{supp:injections}}

Section V-C of the paper reports that no generated plan, on the natural
corpus or the ordering-stress suite, was terminal-safe and prefix-unsafe.
That is a statement about the agent's error distribution, not about the
mechanism. Table~\ref{{tab:supp-inject}} exhibits the mechanism directly: two
of eight hand-constructed violations are transient by construction, and both
are invisible to terminal checking at every budget.

\begin{{table}}[h]
\centering
\caption{{Detection of eight adversarial injections. $L_1$--$L_3$ are terminal
checking at increasing coverage; $L_4$ is all-prefix checking at full
coverage. The two bold rows are caught \emph{{only}} by $L_4$ --- they are
terminal-safe and prefix-unsafe. Recomputed from the archived base state.}}
\label{{tab:supp-inject}}
\footnotesize
\begin{{tabular}}{{lcccc}}
\toprule
Injected violation & $L_1$ & $L_2$ & $L_3$ & $L_4$\\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{table}}
"""


def table_pcurve(pcurve: Path) -> str:
    """S2: the detection-cost curve at every measured budget point."""
    d = json.loads(pcurve.read_text())
    rows = []
    for r in d["rows"]:
        rows.append(
            f"{r['frac']:.3f} & {r.get('n_detected', '')}/{r.get('n_loss', '')}"
            f" & {r['p_detect']:.3f} & {r.get('false_reject', 0.0):.3f}"
            f" & {r.get('tau_mean_ms', float('nan')):.2f} \\\\")
    body = "\n".join(rows)
    return rf"""
\subsection{{The full detection--cost curve}}
\label{{supp:pcurve}}

The paper quotes only the endpoints of this curve --- detection rising from
$0.044$ to $0.973$ below full coverage --- because the intermediate points
did not fit. They are the evidence behind the negative result on the
exponential family: detection is a coarse step function, not a smooth
saturating curve, and it does not bend over before full coverage.

\begin{{table}}[h]
\centering
\caption{{Detection and verification time against coverage budget, indexed by
the fraction of each topology's own predicate-instance count. Detection is
measured over the same 113 loss events as $\hat q$. False rejection is zero
at every point.}}
\label{{tab:supp-pcurve}}
\footnotesize
\begin{{tabular}}{{rrrrr}}
\toprule
Budget & Detected & $p$ & False rej. & $\tau$ (ms)\\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{table}}
"""


def table_loto(selection: Path) -> str:
    """S3: the selected profile in each (topology, risk price) fold."""
    d = json.loads(selection.read_text())
    nets: List[str] = d["networks"]
    Rs = sorted({r["R"] for r in d["rows"]})
    grid: Dict[tuple, dict] = {(r["held_out"], r["R"]): r for r in d["rows"]}

    header = " & ".join(esc(n)[:6] for n in nets)
    rows, n_miss = [], 0
    for R in Rs:
        cells = []
        for n in nets:
            r = grid.get((n, R))
            if not r:
                cells.append("--")
                continue
            sel = PROFILE_SHORT.get(r["selected"], r["selected"])
            oracle = (r.get("oracle") or {}).get("profile")
            if oracle and oracle != r["selected"]:
                cells.append(r"\underline{" + sel + "}")
                n_miss += 1
            else:
                cells.append(sel)
        rows.append(f"${R:g}$ & " + " & ".join(cells) + r" \\")
    body = "\n".join(rows)
    return rf"""
\subsection{{Leave-one-topology-out selection, fold by fold}}
\label{{supp:loto}}

Table~III of the paper pools the ten folds at each risk price. This is the
underlying grid, so that the single disagreement with the plug-in oracle can
be located rather than taken on trust: it is one fold at $R=10$, one step
below the price at which the rule switches depth.

\begin{{table*}}[h]
\centering
\caption{{Profile selected for each held-out topology at each risk price.
T$b$/P$b$ denote terminal/all-prefix scope at budget $b$. Underlined: the
selection differs from the plug-in oracle under that topology's own measured
primitives ({n_miss} of {len(d['rows'])} folds).}}
\label{{tab:supp-loto}}
\footnotesize
\setlength{{\tabcolsep}}{{4pt}}
\begin{{tabular}}{{r{'c' * len(nets)}}}
\toprule
$R$ & {header}\\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{table*}}
"""


def table_ordering(temporal: Path) -> str:
    """S4: what the agent did with the ordered operation pair, by class."""
    d = json.loads(temporal.read_text())
    by_kind = d.get("ordering_by_kind") or {}
    cols = ["correct_order", "wrong_order", "omitted", "ambiguous"]
    rows = []
    for kind in sorted(by_kind):
        v = by_kind[kind]
        rows.append(f"\\texttt{{{esc(kind)}}} & "
                    + " & ".join(str(v.get(c, 0)) for c in cols) + r" \\")
    tot = d.get("ordering") or {}
    rows.append(r"\midrule")
    rows.append("All & " + " & ".join(str(tot.get(c, 0)) for c in cols)
                + r" \\")
    body = "\n".join(rows)
    return rf"""
\subsection{{Ordering outcomes on the stress suite}}
\label{{supp:ordering}}

The paper reports these counts pooled. Split by intent class they show why
the terminal/prefix disagreement count is zero, and it is not that the agent
orders correctly: the dominant failure is \emph{{omission}}, which stays
visible in the final state, and every misordered plan is unsafe terminally
as well.

\begin{{table}}[h]
\centering
\caption{{How generated plans treated the ordered operation pair each
stress-suite instance requires. ``Ambiguous'' means the witness repeats an
operation type, so order cannot be attributed from the plan alone.}}
\label{{tab:supp-ordering}}
\footnotesize
\begin{{tabular}}{{lrrrr}}
\toprule
Intent class & Correct & Wrong & Omitted & Ambiguous\\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{table}}
"""


def table_frozen(frozen: Path) -> str:
    """S5: the frozen result table, in full, grouped by source file."""
    d = json.loads(frozen.read_text())
    by_src: Dict[str, List[dict]] = {}
    for e in d["entries"]:
        by_src.setdefault(e.get("source") or "(derived)", []).append(e)

    chunks = []
    for src in sorted(by_src):
        chunks.append(r"\multicolumn{4}{l}{\textbf{" + esc(src) + r"}}\\")
        for e in sorted(by_src[src], key=lambda x: x["name"]):
            v = e["value"]
            v = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            kn = (f"{e['k']}/{e['n']}" if e.get("k") is not None
                  else (str(e["n"]) if e.get("n") is not None else ""))
            chunks.append(
                f"\\texttt{{\\scriptsize {breakable(trunc(e['name'], 44))}}} "
                f"& {trunc(v, 38)} & {kn} & "
                f"{trunc(e.get('denominator') or '', 64)} \\\\")
        chunks.append(r"\addlinespace")
    body = "\n".join(chunks)
    return rf"""
\subsection{{The frozen result table}}
\label{{supp:frozen}}

Every quantity the paper reports, with the denominator it is defined over,
the interval method, and the file it was read from. Conditional rates in
this evaluation differ mainly in their denominator, and this table exists so
that two of them cannot be interchanged. {len(d['entries'])} entries,
generated from the archived results at a clean source revision.

% longtable cannot run in IEEEtran's two-column mode, and these rows do not
% fit a column anyway; the table is the last thing in the document, so the
% page simply stays single-column from here on.
\onecolumn
\begin{{center}}
\scriptsize
\setlength{{\tabcolsep}}{{4pt}}
\begin{{longtable}}{{@{{}}p{{0.29\textwidth}}rrp{{0.40\textwidth}}@{{}}}}
\toprule
Entry & Value & $k/n$ & Denominator\\
\midrule
\endfirsthead
\multicolumn{{4}}{{@{{}}l}}{{\emph{{(continued)}}}}\\
\toprule
Entry & Value & $k/n$ & Denominator\\
\midrule
\endhead
{body}
\bottomrule
\end{{longtable}}
\end{{center}}
"""


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="out/corpus_v2")
    p.add_argument("--temporal", default="out/temporal_v2/summary.json")
    p.add_argument("--base-state",
                   default="out/q_20260723_060529/base_state.json")
    p.add_argument("--frozen", default="../paper/numbers.json")
    p.add_argument("--out", default="../artifact/supp_tables.tex")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus)
    parts = [r"\section{Supplementary Tables}", r"\label{sec:supp-tables}",
             "", "Each table below reports in full something the paper "
                 "states only in aggregate.", ""]
    jobs = [
        ("injections", lambda: table_injections(Path(args.base_state))),
        ("pcurve", lambda: table_pcurve(corpus / "pcurve_interleaved.json")),
        ("loto", lambda: table_loto(corpus / "selection.json")),
        ("ordering", lambda: table_ordering(Path(args.temporal))),
        ("frozen", lambda: table_frozen(Path(args.frozen))),
    ]
    built = []
    for name, fn in jobs:
        try:
            parts.append(fn())
            built.append(name)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            logger.warning("skip %s: %s", name, exc)

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(parts) + "\n")
    logger.info("wrote %s (%d tables: %s)", dest, len(built),
                ", ".join(built))
    return 0 if built else 1


if __name__ == "__main__":
    sys.exit(main())

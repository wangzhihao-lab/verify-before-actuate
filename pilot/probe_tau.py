"""Pilot probe P0: does SMT verification time tau grow meaningfully with
verification depth (topology size x constraint richness x plan length)?

Encodes a toy but structurally honest check: a k-step configuration plan
(bandwidth allocations of flows onto links) verified against the three
invariant classes of the paper:
  I1 resource conservation: per-link allocated bandwidth <= capacity
  I2 SLA: per-flow end-to-end latency bound along its path
  I3 config conflict: no two steps写同一 flow 的矛盾配置 (pairwise)

Depth dial here = number of invariant classes checked (1..3) x plan length.
Scaling dial = topology size (links, flows).

Output: wall-clock Z3 solve time per (topology, plan_len, classes) cell.
Seed fixed. This is a magnitude probe, not the real harness.
"""
import random
import time

import z3

random.seed(42)


def build_and_check(n_links: int, n_flows: int, plan_len: int,
                    classes: int) -> float:
    """Return Z3 wall time (s) for one verification instance."""
    cap = [random.randint(50, 200) for _ in range(n_links)]
    lat = [random.uniform(0.5, 5.0) for _ in range(n_links)]
    # each flow uses a random path of 2-5 links
    paths = [random.sample(range(n_links), k=random.randint(2, 5))
             for _ in range(n_flows)]
    sla = [random.uniform(5.0, 30.0) for _ in range(n_flows)]

    s = z3.Solver()
    # plan step t assigns bandwidth bw[t][f] to a random subset of flows
    bw = [[z3.Real(f"bw_{t}_{f}") for f in range(n_flows)]
          for t in range(plan_len)]
    touched = [random.sample(range(n_flows), k=max(1, n_flows // 3))
               for _ in range(plan_len)]

    for t in range(plan_len):
        for f in range(n_flows):
            if f in touched[t]:
                s.add(bw[t][f] >= 0, bw[t][f] <= 100)
            else:
                prev = bw[t - 1][f] if t > 0 else z3.RealVal(
                    random.randint(1, 20))
                s.add(bw[t][f] == prev)

    if classes >= 1:  # I1 resource conservation, after every step
        for t in range(plan_len):
            for l in range(n_links):
                users = [bw[t][f] for f in range(n_flows) if l in paths[f]]
                if users:
                    s.add(z3.Sum(users) <= cap[l])
    if classes >= 2:  # I2 SLA: latency grows with link utilization proxy
        for t in range(plan_len):
            for f in range(n_flows):
                path_lat = z3.Sum([z3.RealVal(lat[l]) *
                                   (1 + bw[t][f] / 100) for l in paths[f]])
                s.add(path_lat <= sla[f] * 3)
    if classes >= 3:  # I3 pairwise conflict across steps
        for t1 in range(plan_len):
            for t2 in range(t1 + 1, plan_len):
                for f in range(n_flows):
                    if f in touched[t1] and f in touched[t2]:
                        s.add(z3.Or(bw[t1][f] == bw[t2][f],
                                    bw[t2][f] >= bw[t1][f] - 50))

    t0 = time.perf_counter()
    s.check()
    return time.perf_counter() - t0


if __name__ == "__main__":
    print(f"{'links':>6} {'flows':>6} {'plan':>5} {'classes':>7} {'tau_ms':>10}")
    for n_links, n_flows in [(20, 30), (100, 150), (500, 750), (2000, 3000)]:
        for plan_len in [3, 8]:
            for classes in [1, 2, 3]:
                ts = [build_and_check(n_links, n_flows, plan_len, classes)
                      for _ in range(3)]
                tau_ms = 1000 * sorted(ts)[1]  # median of 3
                print(f"{n_links:>6} {n_flows:>6} {plan_len:>5} "
                      f"{classes:>7} {tau_ms:>10.2f}")

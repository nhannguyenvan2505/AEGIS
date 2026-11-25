"""Judge a detector candidate against the baseline with criteria fixed beforehand.

    python check_acceptance.py --baseline reports/baseline_val.json --candidate reports/healthy10_val.json

Both reports come from the training pack's evaluate.py. Exit 0 = every rule passes, 1 = a rule fails,
2 = no verdict (criteria still a draft, or the two reports cannot be compared).
Rules compare point estimates; a result close to a limit is within sampling noise, not proof.
"""
import argparse
import json
import sys
from pathlib import Path

DISEASES = ("rice_blast", "brown_spot", "sheath_blight")
DEFAULT_CRITERIA = Path(__file__).resolve().parent / "acceptance_criteria.json"
EPSILON = 1e-9


def share(group, *keys):
    return sum(group.get(k, 0) for k in keys) / group["n"]


def incomparable(base, cand):
    reasons = []
    for field in ("split", "healthy_excluded", "gate_sha256"):
        if base.get(field) != cand.get(field):
            reasons.append(f"{field} differs between the two reports" if field != "gate_sha256"
                           else "gate differs: this check judges detector candidates only")
    if base.get("limit") or cand.get("limit"):
        reasons.append("a report was made with --limit (smoke test)")
    if not base.get("healthy_excluded"):
        reasons.append("healthy_excluded is empty: the Healthy images have not been reviewed")
    if base.get("environment", {}).get("ultralytics") != cand.get("environment", {}).get("ultralytics"):
        reasons.append("ultralytics version differs")
    return reasons


def evaluate(base, cand, c):
    """Yield (rule, passed, baseline value, candidate value, limit)."""
    for name in DISEASES:
        b, n = base["end_to_end"]["sick_" + name], cand["end_to_end"]["sick_" + name]
        old, new = share(b, "correct_disease"), share(n, "correct_disease")
        limit = old - c["disease_correct_max_drop_pp"] / 100
        yield f"{name} correct", new >= limit - EPSILON, old, new, limit
        missed = ("reported_no_disease", "uncertain", "rejected")
        old, new = share(b, *missed), share(n, *missed)
        limit = old + c["disease_missed_max_rise_pp"] / 100
        yield f"{name} missed", new <= limit + EPSILON, old, new, limit
    b, n = base["end_to_end"]["healthy"], cand["end_to_end"]["healthy"]
    old, new = share(b, "false_disease"), share(n, "false_disease")
    limit = old * (1 - c["healthy_false_disease_min_relative_drop"])
    yield "healthy false disease", new <= limit + EPSILON, old, new, limit
    old, new = share(b, "false_disease", "uncertain"), share(n, "false_disease", "uncertain")
    limit = old + c["healthy_flagged_max_rise_pp"] / 100
    yield "healthy flagged", new <= limit + EPSILON, old, new, limit
    old, new = base["detector_map"]["map50"], cand["detector_map"]["map50"]
    limit = old - c["map50_max_drop"]
    yield "map50", new >= limit - EPSILON, old, new, limit
    old, new = (r["gate"]["non_rice"].get("accepted", 0) for r in (base, cand))
    limit = old + c["non_rice_accepted_max_rise"]
    yield "non-rice accepted", new <= limit, old, new, limit
    old, new = (share(r["gate"]["rice"], "rejected") for r in (base, cand))
    limit = old + c["rice_rejected_max_rise_pp"] / 100
    yield "rice rejected", new <= limit + EPSILON, old, new, limit


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--criteria", type=Path, default=DEFAULT_CRITERIA)
    a = ap.parse_args()
    base, cand, criteria = (json.loads(p.read_text(encoding="utf-8")) for p in (a.baseline, a.candidate, a.criteria))
    reasons = incomparable(base, cand)
    if reasons:
        print("NO VERDICT:", *reasons, sep="\n  - ")
        sys.exit(2)
    rows = list(evaluate(base, cand, criteria))
    for rule, passed, old, new, limit in rows:
        print(f"{'pass' if passed else 'FAIL'}  {rule:24s} baseline={old:.4g}  candidate={new:.4g}  limit={limit:.4g}")
    print(f"healthy images scored: {base['end_to_end']['healthy']['n']}, excluded: {len(base['healthy_excluded'])}")
    if criteria.get("status") != "approved" or not criteria.get("approved_by") or not criteria.get("approved_on"):
        print("NO VERDICT: the criteria are still a draft; approve and commit them before judging a candidate.")
        sys.exit(2)
    passed = all(row[1] for row in rows)
    print("VERDICT:", "PASS" if passed else "FAIL")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

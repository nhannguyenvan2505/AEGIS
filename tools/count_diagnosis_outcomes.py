"""Count image diagnosis outcomes in Backend logs, including rejections, which are never stored.

    python tools/count_diagnosis_outcomes.py backend.log [more.log ...]
    some-command-that-prints-logs | python tools/count_diagnosis_outcomes.py -

Reads the "request_completed" JSON events of the Backend (any prefix before the JSON is ignored)
and prints totals. It only knows what is in the logs it is given: keeping them is the deployment's
job. Only results the AI answered on /v2 are counted; Idempotency-Key replays are not.

Exit code 2 means some event lines were cut or damaged, so the totals are incomplete. Windows
PowerShell 5.1 "*>" does this by wrapping long lines; redirect with cmd instead.
"""
import argparse
import json
import sys
from collections import Counter

MARKER = '"request_completed"'


def events(lines, unreadable):
    """Yield Backend completion events; append to `unreadable` every event line that cannot be parsed."""
    for line in lines:
        start = line.find("{")
        try:
            event = json.loads(line[start:]) if start >= 0 else None
        except ValueError:
            event = None
        if event is None:
            if MARKER in line:
                unreadable.append(line)
            continue
        if (isinstance(event, dict) and event.get("event") == "request_completed"
                and event.get("service") == "aegis-backend"):
            yield event


def read_lines(path):
    with open(path, "rb") as stream:
        head = stream.read(2)
    encoding = "utf-16" if head in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    with open(path, encoding=encoding, errors="replace") as stream:
        yield from stream


def summarize(lines):
    statuses, issues, errors, unreadable = Counter(), Counter(), Counter(), []
    for event in events(lines, unreadable):
        if event.get("diagnosis_status"):
            statuses[event["diagnosis_status"]] += 1
            issues.update(event.get("quality_issues") or [])
        if event.get("ai_error_code"):
            errors[event["ai_error_code"]] += 1
    total = sum(statuses.values())
    rejected = sum(count for status, count in statuses.items() if status.startswith("rejected_"))
    return {"diagnoses": total, "by_status": dict(sorted(statuses.items())), "rejected": rejected,
            "rejected_share": round(rejected / total, 4) if total else None,
            "quality_issues": dict(sorted(issues.items())), "ai_errors": dict(sorted(errors.items())),
            "unreadable_events": len(unreadable)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+", help="log files, or - for standard input")
    a = ap.parse_args()

    def lines():
        for name in a.logs:
            yield from sys.stdin if name == "-" else read_lines(name)

    report = summarize(lines())
    print(json.dumps(report, indent=2))
    if report["unreadable_events"]:
        print(f"WARNING: {report['unreadable_events']} event line(s) could not be read; the totals are incomplete.",
              file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

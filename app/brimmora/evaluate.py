"""Golden-set evaluation through the real API. python -m brimmora.evaluate run | agreement"""
import csv
import json
import sys
from pathlib import Path

from . import llm
from .client import ask
from .constants import NO_EVIDENCE

EVAL = Path("/srv/eval")
JUDGE = """You grade an enterprise assistant. Compare the ANSWER with the REFERENCE.
Reply with JSON only: {"verdict": "pass" | "fail", "reason": "<one sentence>"}
Pass if the answer states the reference's key facts and adds nothing that contradicts it.
Paraphrasing, extra correct detail, and citation markers such as [1] are fine.
Fail only if a key fact is missing or contradicted, and name it in the reason."""


def judge(question, answer, reference):
    """Returns (passed, reason). Accepts "pass" in any case; anything unparseable is a fail."""
    raw = llm.chat([{"role": "system", "content": JUDGE},
                    {"role": "user", "content": f"QUESTION: {question}\nREFERENCE: {reference}\nANSWER: {answer}"}],
                   purpose="judge", json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, f"judge reply was not JSON: {raw[:120]}"
    verdict = str(data.get("verdict", "")).strip().lower()
    return verdict in ("pass", "passed"), str(data.get("reason", ""))


def _as_list(value):
    return [value] if isinstance(value, str) else list(value or [])


def _mean(values):
    return round(sum(values) / len(values), 3) if values else 1.0


def run_eval():
    items = [json.loads(line) for line in (EVAL / "golden.jsonl").read_text().splitlines() if line.strip()]
    thresholds = json.loads((EVAL / "thresholds.json").read_text())
    rows = []
    for item in items:
        r = ask(item["user"], item["question"])
        refused = r["answer"] == NO_EVIDENCE
        row = {"id": item["id"], "user": item["user"], "question": item["question"],
               "route": r["route"], "refused": refused, "answer": r["answer"],
               "request_id": r["request_id"]}
        if item.get("must_refuse"):
            row["refusal_ok"] = refused
        else:
            cited = {c["source"] for c in r["citations"]}
            row["route_ok"] = r["route"] in _as_list(item["expected_route"])
            row["hit"] = bool(cited & set(_as_list(item["expected_source"])))
            if refused:
                row["judge_pass"], row["judge_reason"] = False, "the assistant refused"
            else:
                row["judge_pass"], row["judge_reason"] = judge(item["question"], r["answer"], item["reference"])
            row["reference"] = item["reference"]
        rows.append(row)
        print(f"{item['id']:>4}  {item['user']:6} route={r['route']:5} "
              f"{'refused ' if refused else 'answered'}  {item['question'][:58]}")

    answerable = [r for r in rows if "hit" in r]
    metrics = {
        "route_accuracy": _mean([r["route_ok"] for r in answerable]),
        "retrieval_hit_rate": _mean([r["hit"] for r in answerable]),
        "grounded_rate": _mean([r["judge_pass"] for r in answerable]),
        "refusal_accuracy": _mean([r["refusal_ok"] for r in rows if "refusal_ok" in r]),
    }
    passed = all(metrics[k] >= v for k, v in thresholds.items())
    report = {"passed": passed, "metrics": metrics, "thresholds": thresholds, "items": rows}
    (EVAL / "report.json").write_text(json.dumps(report, indent=2))

    with open(EVAL / "judge_sample.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "question", "answer", "reference", "judge_verdict", "judge_reason", "human_verdict"])
        for r in answerable:
            writer.writerow([r["id"], r["question"], r["answer"], r["reference"],
                             "pass" if r["judge_pass"] else "fail", r["judge_reason"], ""])

    failed = [r for r in answerable if not r["judge_pass"]]
    if failed:
        print("\nAnswers the judge failed:")
        for r in failed:
            print(f"  {r['id']}: {r['judge_reason']}")
    print(f"\n{'metric':22} {'value':>7} {'threshold':>10}")
    for k, v in metrics.items():
        flag = "" if v >= thresholds.get(k, 0) else "  <- below threshold"
        print(f"{k:22} {v:7.3f} {thresholds.get(k, 0):10.3f}{flag}")
    print(f"\n{'PASSED' if passed else 'FAILED'}: report in eval/report.json")
    return report


def agreement():
    rows = list(csv.DictReader(open(EVAL / "judge_sample.csv")))
    labeled = [r for r in rows if r["human_verdict"].strip()]
    if not labeled:
        sys.exit("fill the human_verdict column (pass or fail) in eval/judge_sample.csv first")
    rate = sum(r["judge_verdict"] == r["human_verdict"].strip().lower() for r in labeled) / len(labeled)
    print(f"judge agrees with humans on {rate:.0%} of {len(labeled)} labeled answers (target 85%)")
    sys.exit(0 if rate >= 0.85 else 1)


if __name__ == "__main__":
    if sys.argv[1] == "run":
        sys.exit(0 if run_eval()["passed"] else 1)
    agreement()

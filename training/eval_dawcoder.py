"""Evaluate all three DAWcoder tasks against the supported JSON contract.

Use --limit 0 for the full validation set. No model is needed for --dry-run.
"""
import argparse
from collections import Counter
import json
import hashlib
import random
import re
import urllib.request
from pathlib import Path

try:
    from .patch_validation import TASKS, validate
except ImportError:
    from patch_validation import TASKS, validate

ROOT = Path(__file__).resolve().parent.parent
VAL = ROOT / "training" / "data" / "dawcoder_sft_val.jsonl"
OLLAMA = "http://127.0.0.1:11434/api/chat"


def chat(model: str, system: str, user: str, num_predict: int = 8192) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False, "think": False,
        "options": {"temperature": 0, "num_predict": num_predict, "num_ctx": 16384},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp).get("message", {}).get("content", "")


def extract_json(text: str):
    text = text.strip()
    if text.startswith("\x60\x60\x60"):
        text = re.sub(r"^\x60\x60\x60[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?\x60\x60\x60$", "", text).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except ValueError:
                pass
    return None


def select_rows(rows, limit=60, seed=20261107):
    """Seeded sampling within each task, then round-robin across tasks."""
    if limit < 0:
        raise ValueError("--limit must be nonnegative; 0 selects the full set")
    groups = {task: [] for task in TASKS}
    for row in rows:
        task = json.loads(row["instruction"])["task"]
        if task not in groups:
            raise ValueError(f"Unknown validation task: {task}")
        groups[task].append(row)
    missing = [task for task, group in groups.items() if not group]
    if missing:
        raise ValueError(f"Validation set is missing tasks: {', '.join(missing)}")
    if limit and limit < len(TASKS):
        raise ValueError("--limit must be at least 3 to cover mix/form/texture")
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    target = min(limit or len(rows), len(rows))
    result, index = [], 0
    while len(result) < target:
        for task in TASKS:
            if index < len(groups[task]):
                result.append(groups[task][index])
                if len(result) == target:
                    break
        index += 1
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dawcoder-preview")
    ap.add_argument("--limit", type=int, default=60, help="total samples; 0 = full validation set")
    ap.add_argument("--seed", type=int, default=20261107)
    ap.add_argument("--num-predict", type=int, default=8192)
    ap.add_argument("--val", type=Path, default=VAL)
    ap.add_argument("--dry-run", action="store_true", help="show task coverage without calling a model")
    ap.add_argument("--out", default="training/eval-report.json")
    args = ap.parse_args()
    if args.num_predict < 1:
        ap.error("--num-predict must be positive")
    rows = [json.loads(line) for line in args.val.read_text(encoding="utf-8").splitlines() if line.strip()]
    try:
        selected = select_rows(rows, args.limit, args.seed)
    except ValueError as exc:
        ap.error(str(exc))
    coverage = Counter(json.loads(row["instruction"])["task"] for row in selected)
    print("Task coverage: " + json.dumps(dict(coverage)))
    if args.dry_run:
        return
    stats = {task: {"n": 0, "parsed": 0, "valid": 0, "reasons": Counter()} for task in TASKS}
    samples, results = [], []
    for i, row in enumerate(selected):
        user = json.loads(row["instruction"])
        task = user["task"]
        raw, patch, ok, why = "", None, False, "invalid-json"
        try:
            raw = chat(args.model, row["system"], row["instruction"], args.num_predict)
            patch = extract_json(raw)
            if patch is not None:
                ok, why = validate(task, user.get("state", {}), patch)
        except (OSError, ValueError, KeyError) as exc:
            why = "request-error"
            raw = str(exc)
        st = stats[task]
        st["n"] += 1
        st["parsed"] += patch is not None
        st["valid"] += ok
        st["reasons"][why] += 1
        results.append({"task": task, "input_sha256": hashlib.sha256(row["instruction"].encode("utf-8")).hexdigest(), "parsed": patch is not None, "valid": ok, "reason": why})
        if sum(sample["task"] == task for sample in samples) < 2:
            samples.append({"task": task, "ok": ok, "reason": why, "input": user, "output": raw})
        print(f"[{i+1}/{len(selected)}] {task} parsed={patch is not None} valid={ok} reason={why}")
    total = len(selected)
    per_task = {task: {**st, "rate": round(st["valid"] / st["n"], 4), "json_parse_rate": round(st["parsed"] / st["n"], 4)} for task, st in stats.items()}
    report = {
        "model": args.model, "total": total, "seed": args.seed,
        "validation_file": str(args.val.resolve()), "validation_sha256": hashlib.sha256(args.val.read_bytes()).hexdigest(),
        "selection": "balanced_round_robin",
        "num_predict": args.num_predict, "coverage_complete": all(coverage[task] > 0 for task in TASKS),
        "json_parse_rate": round(sum(st["parsed"] for st in stats.values()) / total, 4),
        "valid_rate": round(sum(st["valid"] for st in stats.values()) / total, 4),
        "macro_valid_rate": round(sum(st["rate"] for st in per_task.values()) / len(TASKS), 4),
        "per_task": per_task, "samples": samples, "results": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("samples", "results")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

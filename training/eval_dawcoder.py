"""DAWcoder 预览版评测：对 Ollama 模型跑 val 集，验证输出 JSON 的结构合法性。

用法：
  python training/eval_dawcoder.py --model dawcoder-preview --limit 60
  python training/eval_dawcoder.py --model dawcoder-preview --limit 60 --out training/eval-report.json

指标：JSON 解析率、按任务的 schema 合法率、平均输出 token 数、样例。
"""
import argparse
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAL = ROOT / "training" / "data" / "dawcoder_sft_val.jsonl"
OLLAMA = "http://127.0.0.1:11434/api/chat"


def chat(model: str, system: str, user: str, num_predict: int = 900) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": num_predict},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("message", {}).get("content", "")


def extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def validate(task: str, state: dict, patch: dict) -> tuple[bool, str]:
    if not isinstance(patch, dict):
        return False, "not-object"
    if task == "mix":
        ops = patch.get("ops")
        if not isinstance(ops, list) or not ops:
            return False, "no-ops"
        names = {t["name"] for t in state.get("tracks", [])} | {b["name"] for b in state.get("buses", [])}
        for op in ops:
            if not isinstance(op, dict) or op.get("op") not in {"set_track", "set_eq", "set_comp", "set_send"}:
                return False, "bad-op"
            if op.get("op") == "set_track" and op.get("track") not in names:
                return False, "unknown-track"
            if op.get("op") == "set_eq" and op.get("track") not in names:
                return False, "unknown-track"
        return True, "ok"
    if task == "form":
        secs = patch.get("sections")
        if not isinstance(secs, list) or not secs:
            return False, "no-sections"
        bar = 1
        for s in secs:
            if s.get("start_bar") != bar or s.get("bars", 0) < 4 or s.get("bars", 0) % 4 != 0:
                return False, "bad-section"
            bar += s["bars"]
        if len(patch.get("markers", [])) != len(secs):
            return False, "marker-mismatch"
        return True, "ok"
    if task == "texture":
        notes = patch.get("notes")
        if not isinstance(notes, list) or not notes:
            return False, "no-notes"
        for n in notes:
            if not (1 <= n.get("bar", 0) <= 8):
                return False, "bad-bar"
            if not (0 <= n.get("step", -1) <= 15 and 1 <= n.get("len_steps", 0) <= 32):
                return False, "bad-grid"
            if not (48 <= n.get("key", 0) <= 72):
                return False, "bad-key"
        return True, "ok"
    return False, "unknown-task"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dawcoder-preview")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--out", default="training/eval-report.json")
    args = ap.parse_args()

    rows = [json.loads(l) for l in VAL.read_text(encoding="utf-8").splitlines() if l.strip()][: args.limit]
    stats = {"mix": [0, 0], "form": [0, 0], "texture": [0, 0]}
    parsed = 0
    samples = []
    for i, row in enumerate(rows):
        user = json.loads(row["instruction"])
        task = user["task"]
        raw = chat(args.model, row["system"], row["instruction"])
        patch = extract_json(raw)
        ok = False
        if patch is not None:
            parsed += 1
            ok, why = validate(task, user.get("state", {}), patch)
        stats[task][0] += 1
        if ok:
            stats[task][1] += 1
        if len(samples) < 6:
            samples.append({"task": task, "ok": ok, "output": raw[:600]})
        print(f"[{i+1}/{len(rows)}] {task} parsed={patch is not None} valid={ok}")

    report = {
        "model": args.model,
        "total": len(rows),
        "json_parse_rate": round(parsed / max(1, len(rows)), 3),
        "per_task": {k: {"n": v[0], "valid": v[1], "rate": round(v[1] / max(1, v[0]), 3)} for k, v in stats.items()},
        "samples": samples,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1)[:1200])


if __name__ == "__main__":
    main()

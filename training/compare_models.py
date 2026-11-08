"""Build training/COMPARISON-REPORT.md from eval-report-*.json (+ optional reward comparison).

  python training/compare_models.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

TRAIN = Path(__file__).resolve().parent.parent / "training"
OUT = TRAIN / "COMPARISON-REPORT.md"
BASELINE = "dawcoder-preview"


def load_reports() -> list[dict]:
    reports = []
    for p in sorted(TRAIN.glob("eval-report-*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        model = data.get("model") or p.stem.replace("eval-report-", "")
        per_task = data.get("per_task", {})
        request_err = sum(v.get("reasons", {}).get("request-error", 0) for v in per_task.values())
        total = data.get("total") or sum(v.get("n", 0) for v in per_task.values())
        data["_file"] = p.name
        data["_request_error"] = request_err
        data["_total"] = total
        data["_reliable"] = total > 0 and request_err / total <= 0.10
        reports.append(data)
    return reports


def load_reward() -> dict:
    """Merge reward summaries from compare-posttrain*.json (model -> overall)."""
    out = {}
    for p in sorted(list(TRAIN.glob("compare-posttrain*.json")) + list(TRAIN.glob("compare-astra*.json"))):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for model, payload in data.items():
            summary = (payload or {}).get("summary", {})
            if "overall" in summary:
                out[model] = summary["overall"]
    return out


def pct(x: float | None) -> str:
    return "-" if x is None else f"{100 * x:.1f}%"


def main() -> int:
    reports = load_reports()
    rewards = load_reward()
    lines = [
        "# DAWcoder 妯″瀷瀵规瘮鎶ュ憡",
        "",
        f"鐢熸垚鏃堕棿锛歿datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "璇勬祴鍗忚锛歚training/EVAL-PROTOCOL.md`锛坴al 60 鏉″潎琛★紝seed 20261107锛宼emperature 0锛宯um_predict 8192锛?,
        "",
        "| 妯″瀷 | 鎶ュ憡 | 鍙潬 | JSON 瑙ｆ瀽 | schema 鍚堟硶 | macro | mix | form | texture | reward(overall) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    rows = []
    for r in reports:
        per = r.get("per_task", {})
        row = {
            "model": r.get("model"),
            "file": r.get("_file"),
            "reliable": r.get("_reliable"),
            "json": r.get("json_parse_rate"),
            "valid": r.get("valid_rate"),
            "macro": r.get("macro_valid_rate"),
            "mix": per.get("mix", {}).get("rate"),
            "form": per.get("form", {}).get("rate"),
            "texture": per.get("texture", {}).get("rate"),
            "reward": rewards.get(r.get("model"), {}).get("mean_reward"),
        }
        rows.append(row)
    rows.sort(key=lambda x: (-(x["valid"] or 0), x["model"] or ""))
    for x in rows:
        lines.append(
            "| {m} | {f} | {rel} | {j} | {v} | {ma} | {mix} | {form} | {tex} | {rw} |".format(
                m=x["model"], f=x["file"], rel="鉁? if x["reliable"] else "鈿狅笍 璇锋眰閿欒澶?,
                j=pct(x["json"]), v=pct(x["valid"]), ma=pct(x["macro"]),
                mix=pct(x["mix"]), form=pct(x["form"]), tex=pct(x["texture"]),
                rw="-" if x["reward"] is None else f"{x['reward']:.4f}"))

    base = next((r for r in rows if r["model"] == BASELINE), None)
    lines += ["", "## 鍥炲綊妫€鏌ワ紙鐩稿鍩虹嚎 `%s`锛? % BASELINE, ""]
    if base is None:
        lines.append("- 鍩虹嚎鎶ュ憡缂哄け锛坄eval-report-preview.json`锛?)
    else:
        for x in rows:
            if x["model"] == BASELINE or not x["reliable"]:
                continue
            issues = []
            if x["valid"] is not None and base["valid"] is not None and x["valid"] < base["valid"] - 0.05:
                issues.append(f"schema 鍚堟硶鐜囦笅闄?{(base['valid'] - x['valid']) * 100:.1f} 涓櫨鍒嗙偣")
            for task in ("mix", "form", "texture"):
                if x[task] is not None and base[task] is not None and x[task] < base[task] - 0.05:
                    issues.append(f"{task} 鍚堟硶鐜囦笅闄?{(base[task] - x[task]) * 100:.1f} 涓櫨鍒嗙偣")
            if x["reward"] is not None and base["reward"] is not None and x["reward"] < base["reward"] - 0.01:
                issues.append(f"reward 涓嬮檷 {base['reward'] - x['reward']:.4f}")
            lines.append(f"- **{x['model']}**锛? + ("锛?.join(issues) if issues else "鏃犻€€鍖栵紝閫氳繃"))
    lines += ["", "## 璇存槑", "",
              "- 鏍?鈿狅笍 鐨勬姤鍛婂瓨鍦?>10% request-error锛圤llama 鏈嶅姟涓柇锛夛紝鏁版嵁涓嶅彲鐢ㄤ簬瀵规瘮锛岄渶閲嶈窇銆?,
              "- reward 鏉ヨ嚜 `compare-posttrain*.json`锛堝鏈夛級锛屼负涓庨噾鏍囧噯 patch 鐨勭浉浼煎害锛?~1锛夈€?,
              "- 鍙彂甯冩爣鍑嗭細JSON 瑙ｆ瀽 鈮?9%銆乻chema 鈮?8%銆佹棤鍗曚换鍔?<95%銆佺浉瀵瑰熀绾挎棤 >5pp 閫€鍖栥€?]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT)
    print("\n".join(lines[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


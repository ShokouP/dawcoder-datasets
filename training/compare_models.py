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
    for p in sorted(TRAIN.glob("compare-posttrain*.json")):
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
        "# DAWcoder 模型对比报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "评测协议：`training/EVAL-PROTOCOL.md`（val 60 条均衡，seed 20261107，temperature 0，num_predict 8192）",
        "",
        "| 模型 | 报告 | 可靠 | JSON 解析 | schema 合法 | macro | mix | form | texture | reward(overall) |",
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
                m=x["model"], f=x["file"], rel="✅" if x["reliable"] else "⚠️ 请求错误多",
                j=pct(x["json"]), v=pct(x["valid"]), ma=pct(x["macro"]),
                mix=pct(x["mix"]), form=pct(x["form"]), tex=pct(x["texture"]),
                rw="-" if x["reward"] is None else f"{x['reward']:.4f}"))

    base = next((r for r in rows if r["model"] == BASELINE), None)
    lines += ["", "## 回归检查（相对基线 `%s`）" % BASELINE, ""]
    if base is None:
        lines.append("- 基线报告缺失（`eval-report-preview.json`）")
    else:
        for x in rows:
            if x["model"] == BASELINE or not x["reliable"]:
                continue
            issues = []
            if x["valid"] is not None and base["valid"] is not None and x["valid"] < base["valid"] - 0.05:
                issues.append(f"schema 合法率下降 {(base['valid'] - x['valid']) * 100:.1f} 个百分点")
            for task in ("mix", "form", "texture"):
                if x[task] is not None and base[task] is not None and x[task] < base[task] - 0.05:
                    issues.append(f"{task} 合法率下降 {(base[task] - x[task]) * 100:.1f} 个百分点")
            if x["reward"] is not None and base["reward"] is not None and x["reward"] < base["reward"] - 0.01:
                issues.append(f"reward 下降 {base['reward'] - x['reward']:.4f}")
            lines.append(f"- **{x['model']}**：" + ("；".join(issues) if issues else "无退化，通过"))
    lines += ["", "## 说明", "",
              "- 标 ⚠️ 的报告存在 >10% request-error（Ollama 服务中断），数据不可用于对比，需重跑。",
              "- reward 来自 `compare-posttrain*.json`（如有），为与金标准 patch 的相似度（0~1）。",
              "- 可发布标准：JSON 解析 ≥99%、schema ≥98%、无单任务 <95%、相对基线无 >5pp 退化。"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT)
    print("\n".join(lines[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

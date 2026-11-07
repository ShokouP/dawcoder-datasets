#!/usr/bin/env python3
"""合并两路 CPT 语料（本会话 curated / 另一路 expanded / permissive），去重并生成统一语料。

  python cpt/merge_corpora.py \
      --inputs cpt/data-expanded cpt/data-curated cpt/data-permissive \
      --out D:/train/data/dawcoder-merged \
      --name dawcoder-cpt-v0.5-merged

输出：
  corpus_{train,val}.jsonl      统一语料（逐条保留 source/license/url/text_sha256）
  cpt_{train,val}_text.jsonl    CPT 训练格式（仅 text）
  manifest.json / stats.md / ATTRIBUTIONS.md / MERGE-REPORT.md

去重：按 text_sha256 全局去重（优先保留先出现的输入）；切分按 text_sha256 重算 98/2，
     避免同文档跨 train/val 泄漏。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_CHARS = 300
MAX_CHARS = 120_000
LICENSE_CLASS = {
    "CC0-1.0": "permissive",
    "Public-Domain": "permissive",
    "MIT": "permissive",
    "ISC": "permissive",
    "BSD": "permissive",
    "Apache-2.0": "permissive",
    "CC-BY-SA-4.0": "share-alike",
    "CC-BY-NC-SA-4.0": "non-commercial",
    "Non-Commercial": "non-commercial",
}


def est_tokens(text: str) -> int:
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return int(cjk / 1.6 + (len(text) - cjk) / 4)


def cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk / len(text)


def split_of(d: dict) -> bool:
    """按 group_key（同源文档族）或 text hash 决定是否 val，保证同源不跨切分。"""
    group = d.get("group_key")
    key = group if group else d["text_sha256"]
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:4], 16) % 100 < 2


def iter_records(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="dawcoder-cpt-v0.5-merged")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    inputs = [Path(p) for p in args.inputs]
    seen: set[str] = set()
    per_source: dict[str, dict] = defaultdict(lambda: {"docs": 0, "chars": 0, "tokens": 0, "licenses": Counter()})
    license_class: Counter = Counter()
    lang = Counter()
    lengths: list[int] = []
    docs = train = val = chars = 0
    input_stats = {}
    dup_removed = 0
    conflict_split = 0

    # 先统计输入（去重前）
    for inp in inputs:
        input_stats[inp.name] = {"docs": 0, "chars": 0, "tokens": 0}
        for split in ("train", "val"):
            path = inp / f"corpus_{split}.jsonl"
            if not path.exists():
                continue
            for d in iter_records(path):
                t = d.get("text", "")
                input_stats[inp.name]["docs"] += 1
                input_stats[inp.name]["chars"] += len(t)
                input_stats[inp.name]["tokens"] += est_tokens(t)
        print(f"input {inp.name}: {input_stats[inp.name]['docs']:,} docs / "
              f"~{input_stats[inp.name]['tokens']/1e6:.1f}M tokens", flush=True)

    fh_train = (out / "corpus_train.jsonl").open("w", encoding="utf-8", newline="\n")
    fh_val = (out / "corpus_val.jsonl").open("w", encoding="utf-8", newline="\n")
    fh_ttext = (out / "cpt_train_text.jsonl").open("w", encoding="utf-8", newline="\n")
    fh_vtext = (out / "cpt_val_text.jsonl").open("w", encoding="utf-8", newline="\n")
    t0 = time.time()
    try:
        for inp in inputs:
            for split in ("train", "val"):
                path = inp / f"corpus_{split}.jsonl"
                if not path.exists():
                    continue
                for d in iter_records(path):
                    text = d.get("text", "")
                    if not (MIN_CHARS <= len(text) <= MAX_CHARS):
                        continue
                    h = d.get("text_sha256") or hashlib.sha256(text.encode()).hexdigest()
                    if h in seen:
                        dup_removed += 1
                        continue
                    seen.add(h)
                    d["text_sha256"] = h
                    is_val = split_of(d)
                    if split == "val":
                        conflict_split += 1
                    rec = json.dumps(d, ensure_ascii=False) + "\n"
                    txt = json.dumps({"text": text}, ensure_ascii=False) + "\n"
                    if is_val:
                        fh_val.write(rec)
                        fh_vtext.write(txt)
                        val += 1
                    else:
                        fh_train.write(rec)
                        fh_ttext.write(txt)
                        train += 1
                    sid = d.get("source", "?")
                    st = per_source[sid]
                    st["docs"] += 1
                    st["chars"] += len(text)
                    st["tokens"] += est_tokens(text)
                    st["licenses"][d.get("license", "?")] += 1
                    license_class[LICENSE_CLASS.get(d.get("license", "?"), "other")] += 1
                    r = cjk_ratio(text)
                    lang["zh" if r > 0.5 else "en" if r < 0.1 else "mixed"] += 1
                    lengths.append(len(text))
                    docs += 1
                    chars += len(text)
    finally:
        for fh in (fh_train, fh_val, fh_ttext, fh_vtext):
            fh.close()

    lengths.sort()
    pct = lambda p: lengths[min(len(lengths) - 1, int(len(lengths) * p))] if lengths else 0
    total_tokens = sum(v["tokens"] for v in per_source.values())

    def digest(name: str) -> dict:
        path = out / name
        return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size, "lines": sum(1 for _ in path.open(encoding="utf-8"))}

    manifest = {
        "corpus": args.name,
        "profile": "public",
        "split_policy": "group",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": [p.name for p in inputs],
        "input_stats": input_stats,
        "docs": docs,
        "chars": chars,
        "est_tokens": total_tokens,
        "train_docs": train,
        "val_docs": val,
        "dedupe": {"removed_duplicates": dup_removed, "unique_docs": docs,
                   "val_split_recounted": val, "note": "按 text_sha256 重算 98/2，避免跨 split 泄漏"},
        "language": dict(lang),
        "license_class": dict(license_class),
        "length": {"p50": pct(0.5), "p90": pct(0.9), "p99": pct(0.99)},
        "sources": {sid: {"docs": v["docs"], "chars": v["chars"], "tokens": v["tokens"],
                          "licenses": dict(v["licenses"])} for sid, v in sorted(per_source.items())},
        "files": {name: digest(name) for name in ("corpus_train.jsonl", "corpus_val.jsonl",
                                                  "cpt_train_text.jsonl", "cpt_val_text.jsonl")},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8", newline="\n")

    stats = ["# 合并语料统计", "",
             f"- 语料版本：`{args.name}`",
             f"- 输入：{', '.join(p.name for p in inputs)}",
             f"- 文档数：**{docs:,}**（train {train:,} / val {val:,}）",
             f"- 字符数：**{chars:,}**；估算 tokens：**{total_tokens:,}**",
             f"- 语言分布：中文 {lang['zh']} / 英文 {lang['en']} / 中英混合 {lang['mixed']}",
             f"- 许可分类：{dict(license_class)}",
             f"- 去重：移除重复 {dup_removed:,} 条（按 text_sha256）",
             f"- 长度分位：p50 {pct(0.5):,} / p90 {pct(0.9):,} / p99 {pct(0.99):,}", "",
             "| 源 | 文档 | 字符 | 估算 tokens | 许可 |", "|---|---:|---:|---:|---|"]
    for sid, v in sorted(per_source.items()):
        stats.append(f"| {sid} | {v['docs']} | {v['chars']:,} | {v['tokens']:,} | "
                     f"{', '.join(v['licenses'].keys())} |")
    stats += ["", "> tokens 为字符估算（CJK/1.6 + 其他/4），训练前请用 Qwen 分词器实测。"]
    (out / "stats.md").write_text("\n".join(stats) + "\n", encoding="utf-8", newline="\n")

    # 合并许可/署名：优先复制 expanded 的 ATTRIBUTIONS，再附合并说明
    attr_parts = []
    for inp in inputs:
        p = inp / "ATTRIBUTIONS.md"
        if p.exists():
            attr_parts.append(f"<!-- source: {inp.name} -->\n" + p.read_text(encoding="utf-8"))
    attr_parts.append(
        "# 合并说明\n\n此语料由 " + "、".join(p.name for p in inputs) +
        " 合并去重得到；逐源署名与许可见上。share-alike 部分按 CC BY-SA 4.0 使用；"
        "非商用/SA 数据不得进入商用训练集。\n")
    (out / "ATTRIBUTIONS.md").write_text("\n\n".join(attr_parts), encoding="utf-8", newline="\n")

    report = [
        "# 语料合并报告（MERGE-REPORT）", "",
        f"- 输出：`{out}`",
        f"- 版本：`{args.name}`",
        f"- 结果：**{docs:,} docs / {chars:,} chars / ~{total_tokens:,} tokens**"
        f"（train {train:,} / val {val:,}）",
        f"- 输入规模：" + "；".join(f"{k}: {v['docs']:,} docs / ~{v['tokens']/1e6:.1f}M tok"
                                   for k, v in input_stats.items()),
        f"- 去重移除：{dup_removed:,} 条重复（含 permissive 与 expanded 的重叠部分）",
        f"- 语言：{dict(lang)}",
        f"- 许可分类：{dict(license_class)}",
        "",
        "## 输入对照", "",
        "| 输入 | docs | ~tokens |", "|---|---:|---:|",
    ]
    for k, v in input_stats.items():
        report.append(f"| {k} | {v['docs']:,} | {v['tokens']/1e6:.2f}M |")
    report += ["", "## 合并后逐源", "", "| 源 | docs | ~tokens | 许可 |", "|---|---:|---:|---|"]
    for sid, v in sorted(per_source.items()):
        report.append(f"| {sid} | {v['docs']:,} | {v['tokens']/1e6:.3f}M | {', '.join(v['licenses'])} |")
    report += ["",
               "## 使用建议", "",
               "- **预览版 CPT / 研究**：用合并版（share-alike 为主，含 SE/Wikipedia/Sonic Pi 教程）。",
               "- **商用训练**：用 `cpt/data-permissive`（仅 CC0/PD/MIT/ISC 等白名单），"
               "或在合并版上按 `license_class` 过滤掉 share-alike。",
               "- 中文仍偏少（见语言分布）；待 zhwiki dump 完成后补入。",
               ""]
    (out / "MERGE-REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")

    print(f"完成：{docs:,} docs / {chars:,} chars / ~{total_tokens:,} tokens -> {out}")
    print(f"去重移除 {dup_removed:,}；train {train:,} / val {val:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

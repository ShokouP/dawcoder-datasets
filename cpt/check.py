#!/usr/bin/env python3
"""校验 CPT 语料（CI 可直接跑）。"""
from __future__ import annotations

import hashlib
import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from build import PERMISSIVE_LICENSES

ROOT = Path(__file__).resolve().parent.parent
CPT = ROOT / "cpt"
OUT = CPT / "data"
REQUIRED = {"doc_id", "source", "license", "tier", "title", "text", "text_sha256"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=OUT)
    args = ap.parse_args()
    output = args.data if args.data.is_absolute() else ROOT / args.data
    errors: list[str] = []
    sources = {s["id"]: s for s in yaml.safe_load((CPT / "sources.yaml").read_text(encoding="utf-8"))["sources"]}

    for sid, src in sources.items():
        for key in ("id", "title", "license", "tier", "redistributable", "fetch"):
            if key not in src:
                errors.append(f"[sources] {sid} 缺少字段 {key}")
        if src.get("tier") not in {"T0", "T1", "T2", "T3"}:
            errors.append(f"[sources] {sid} tier 非法")
        if src.get("redistributable") and src.get("tier") in {"T2", "T3"}:
            errors.append(f"[sources] {sid} 非 T0/T1 却声明可再分发")

    mpath = output / "manifest.json"
    if not mpath.exists():
        print("ERROR 缺少 cpt/data/manifest.json（先跑 cpt/build.py）")
        return 1
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    if manifest.get("profile") not in {"public", "permissive"}:
        errors.append("只允许 public/permissive profile 的语料")
    for name, meta in manifest["files"].items():
        path = output / name
        if not path.exists():
            errors.append(f"[manifest] 缺文件 {name}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            errors.append(f"[manifest] {name} sha256 不匹配")
        if len(path.read_text(encoding="utf-8").splitlines()) != meta["lines"]:
            errors.append(f"[manifest] {name} 行数不匹配")

    seen_ids: set[str] = set()
    seen_hash: set[str] = set()
    seen_sources: set[str] = set()
    total = 0
    group_splits = {}
    for name in ("corpus_train.jsonl", "corpus_val.jsonl"):
        path = output / name
        if not path.exists():
            errors.append(f"[corpus] 缺文件 {name}")
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            d = json.loads(line)
            total += 1
            missing = REQUIRED - set(d)
            if missing:
                errors.append(f"[{name}:{i}] 缺字段 {missing}")
                continue
            src = sources.get(d["source"])
            if not src:
                errors.append(f"[{name}:{i}] 未知 source {d['source']}")
                continue
            seen_sources.add(d["source"])
            if d["license"] != src["license"]:
                errors.append(f"[{name}:{i}] license 与源注册表不一致")
            if not src.get("redistributable"):
                errors.append(f"[{name}:{i}] 包含不可再分发源 {d['source']}")
            if manifest.get("profile") == "permissive" and d["license"] not in PERMISSIVE_LICENSES:
                errors.append(f"[{name}:{i}] permissive profile 包含非白名单许可")
            group = d.get("group_key")
            if manifest.get("split_policy") and not group:
                errors.append(f"[{name}:{i}] 缺少 group_key")
            if group:
                if group in group_splits and group_splits[group] != name:
                    errors.append(f"[{name}:{i}] 同源文档跨 train/val: {group}")
                group_splits[group] = name
            if src["fetch"].get("method") == "github_docs":
                if not re.fullmatch(r"[0-9a-f]{40}", d.get("revision", "")) or not d.get("source_path") or not d.get("license_url"):
                    errors.append(f"[{name}:{i}] 开放文档缺少版本或来源证据")
                evidence = output / "licenses" / (d["source"] + ".txt")
                if not evidence.exists():
                    errors.append(f"[{name}:{i}] 缺少原始许可声明")
            if not (300 <= len(d["text"]) <= 120_000):
                errors.append(f"[{name}:{i}] 文本长度越界")
            if hashlib.sha256(d["text"].encode("utf-8")).hexdigest() != d["text_sha256"]:
                errors.append(f"[{name}:{i}] text_sha256 不匹配")
            if d["doc_id"] in seen_ids:
                errors.append(f"[{name}:{i}] doc_id 重复 {d['doc_id']}")
            seen_ids.add(d["doc_id"])
            if d["text_sha256"] in seen_hash:
                errors.append(f"[{name}:{i}] 文本重复")
            seen_hash.add(d["text_sha256"])

    if total != manifest["docs"]:
        errors.append(f"[manifest] docs 数量不符：{total} != {manifest['docs']}")
    for sid in seen_sources:
        if sid not in manifest["sources"]:
            errors.append(f"[manifest] 缺少源统计 {sid}")
    attr = output / "ATTRIBUTIONS.md"
    if not attr.exists():
        errors.append("[attributions] 缺少 ATTRIBUTIONS.md")
    else:
        text = attr.read_text(encoding="utf-8")
        for sid in seen_sources:
            if sid not in text:
                errors.append(f"[attributions] 未声明来源 {sid}")
    if not (output / "stats.md").exists():
        errors.append("[stats] 缺少 stats.md")

    print(f"语料：{manifest.get('docs')} docs / {manifest.get('chars'):,} chars / ~{manifest.get('est_tokens'):,} tokens")
    print(f"源：{', '.join(sorted(seen_sources))}")
    if errors:
        for e in errors[:40]:
            print("ERROR", e)
        print(f"\n{len(errors)} error(s)")
        return 1
    print("\n0 error(s) —— CPT 语料可直接用于继续预训练")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""把 fetch_zhwiki_dump.py 产出的中文维基 raw JSONL 转成统一语料格式（供 merge_corpora 合并）。

  python cpt/zhwiki_to_corpus.py \
      --raw cpt/raw/zh-wikipedia-dump.jsonl \
      --out D:/train/data/zhwiki-corpus

输出：corpus_{train,val}.jsonl（含 group_key=zhwiki:<title>，按 group 切分）+ manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

MIN_CHARS = 300
MAX_CHARS = 120_000
LICENSE = "CC-BY-SA-4.0"
TIER = "T1"


def est_tokens(text: str) -> int:
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return int(cjk / 1.6 + (len(text) - cjk) / 4)


def split_bucket(group: str) -> str:
    return "val" if int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:4], 16) % 100 < 2 else "train"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="cpt/raw/zh-wikipedia-dump.jsonl")
    ap.add_argument("--out", default=r"D:/train/data/zhwiki-corpus")
    ap.add_argument("--name", default="dawcoder-cpt-zhwiki-v0.1")
    args = ap.parse_args()
    raw = Path(args.raw)
    if not raw.exists():
        raise SystemExit(f"缺少 raw：{raw}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    stats = {"docs": 0, "chars": 0, "tokens": 0, "train": 0, "val": 0}
    hashes: set[str] = set()
    writers = {"train": (out / "corpus_train.jsonl").open("w", encoding="utf-8", newline="\n"),
               "val": (out / "corpus_val.jsonl").open("w", encoding="utf-8", newline="\n")}
    try:
        for line in raw.open(encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            text = d.get("text", "")
            if not (MIN_CHARS <= len(text) <= MAX_CHARS):
                continue
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if h in hashes:
                continue
            hashes.add(h)
            title = d.get("title", "")
            group = f"zhwiki:{title}"
            split = split_bucket(group)
            rec = {
                "doc_id": d.get("doc_id"),
                "source": "zh-wikipedia-dump",
                "license": LICENSE,
                "tier": TIER,
                "title": title,
                "url": d.get("url", ""),
                "kind": d.get("kind", "chunk"),
                "group_key": group,
                "text": text,
                "text_sha256": h,
                "retrieved_at": d.get("retrieved_at", ""),
            }
            writers[split].write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["docs"] += 1
            stats["chars"] += len(text)
            stats["tokens"] += est_tokens(text)
            stats[split] += 1
    finally:
        for fh in writers.values():
            fh.close()

    manifest = {
        "corpus": args.name,
        "profile": "public",
        "split_policy": "group",
        "docs": stats["docs"],
        "chars": stats["chars"],
        "est_tokens": stats["tokens"],
        "train_docs": stats["train"],
        "val_docs": stats["val"],
        "sources": {"zh-wikipedia-dump": {"license": LICENSE, "tier": TIER,
                                          "docs": stats["docs"], "chars": stats["chars"],
                                          "tokens": stats["tokens"]}},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8", newline="\n")
    print(f"完成：{stats['docs']:,} docs / {stats['chars']:,} chars / ~{stats['tokens']:,} tokens "
          f"(train {stats['train']:,} / val {stats['val']:,}) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""对 zhwiki raw 做二次清洗与相关性筛选，降低噪声条目。

  python cpt/clean_zhwiki_raw.py \
      --raw cpt/raw/zh-wikipedia-dump.jsonl \
      --out cpt/raw/zh-wikipedia-dump.clean.jsonl

规则：
  - 去掉残留标记（[[, ]], {{, }}, &nbsp;, 空书名号/括号, <...>, 引用编号）
  - 相关性：标题含音乐/音频词 → 保留；否则标题命中黑名单（足球/哲学/政府…）→ 丢弃；
    否则开头 400 字含音乐/音频词 → 保留。目标是"音乐领域中文文本"，不是只留混音工程文。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

MUSIC = ["音乐", "录音", "音频", "声音", "混音", "母带", "乐器", "歌曲", "专辑", "歌手",
         "乐队", "声学", "音效", "合成器", "采样", "耳机", "音响", "音色", "音高", "节奏",
         "编曲", "和声", "和弦", "伴奏", "演唱", "交响", "歌剧", "爵士", "摇滚", "流行",
         "电子音乐", "音轨", "分轨", "响度", "频谱", "琴", "鼓", "贝斯", "吉他", "钢琴",
         "笛", "箫", "二胡", "古筝", "打击乐", "调音", "扩声", "音源", "虚拟乐器", "MIDI"]
BLOCK_TITLE = ["足球", "篮球", "联赛", "哲学", "政府", "小说", "漫画", "动画", "游戏",
               "数学", "物理", "化学", "生物", "医学", "地理", "历史", "军事", "政治",
               "经济", "法律", "电影", "电视剧", "操作系统", "编程语言"]

EMPTY_QUOTE_RE = re.compile(r"《\s*》|（\s*）|\(\s*\)|“\s*”|「\s*」|『\s*』")
LINK_TAIL_RE = re.compile(r"\]{2,}|\}{2,}|\[{2,}|\{{2,}")
CITE_RE = re.compile(r"\[\d+\]")
HTML_RE = re.compile(r"<[^>]{0,40}>")
SPACE_RE = re.compile(r"[ \t\u3000]+")


def clean(text: str) -> str:
    text = CITE_RE.sub("", text)
    text = EMPTY_QUOTE_RE.sub("", text)
    text = LINK_TAIL_RE.sub("", text)
    text = HTML_RE.sub(" ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("|", " ").replace("==", ""))
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def relevant(title: str, text: str) -> bool:
    if any(b in title for b in BLOCK_TITLE):
        return False
    if any(m in title for m in MUSIC):
        return True
    head = text[:400]
    return any(m in head for m in MUSIC)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="cpt/raw/zh-wikipedia-dump.jsonl")
    ap.add_argument("--out", default="cpt/raw/zh-wikipedia-dump.clean.jsonl")
    ap.add_argument("--min-chars", type=int, default=1200)
    args = ap.parse_args()
    raw = Path(args.raw)
    out = Path(args.out)
    rows = [json.loads(l) for l in raw.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept, dropped = [], Counter()
    seen = set()
    for d in rows:
        text = clean(d.get("text", ""))
        if len(text) < args.min_chars:
            dropped["too-short"] += 1
            continue
        if not relevant(d.get("title", ""), text):
            dropped["off-domain"] += 1
            continue
        if text[:120] in seen:
            dropped["duplicate-head"] += 1
            continue
        seen.add(text[:120])
        d["text"] = text
        kept.append(d)
    out.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in kept),
                   encoding="utf-8", newline="\n")
    chars = sum(len(d["text"]) for d in kept)
    resid = Counter()
    for d in kept:
        for m in ("[[", "]]", "{{", "}}", "&nbsp;", "（）", "《》", "<", ">"):
            if m in d["text"]:
                resid[m] += 1
    print(f"kept {len(kept)}/{len(rows)} docs, {chars/1e6:.2f}M chars, dropped={dict(dropped)}")
    print("residue:", dict(resid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

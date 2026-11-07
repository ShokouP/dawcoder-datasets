#!/usr/bin/env python3
"""从 zhwiki 官方 dump 中抽取音频/音乐制作相关中文条目，转为 CPT 原始 JSONL。

  python cpt/fetch_zhwiki_dump.py [--dump PATH] [--max-docs 8000] [--max-chars 35000000]

依赖：标准库（bz2 + ElementTree），无需 GPU。
输出：cpt/raw/zh-wikipedia-dump.jsonl（gitignored）
"""
from __future__ import annotations

import argparse
import bz2
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DUMPS = ROOT / "cpt" / "raw" / "dumps"
DEFAULT_DUMP = DUMPS / "zhwiki-latest-pages-articles.xml.bz2"
OUT = ROOT / "cpt" / "raw" / "zh-wikipedia-dump.jsonl"
NS = "{http://www.mediawiki.org/xml/export-0.11/}"

KEYWORDS = [
    "混音", "母带", "均衡器", "均衡", "压缩器", "压缩", "混响", "效果器", "音频", "录音",
    "音乐制作", "声学", "音色", "和声", "对位", "编曲", "配器", "采样率", "采样", "量化",
    "调音台", "混音台", "麦克风", "监听", "扬声器", "耳机", "前置放大器", "放大器",
    "频率响应", "动态范围", "失真", "噪声", "分贝", "滤波器", "频谱", "傅里叶",
    "数字音频", "工作站", "插件", "虚拟乐器", "合成器", "录音室", "母带处理",
    "立体声", "环绕声", "声像", "响度", "信噪比", "音频接口", "MIDI", "音轨", "分轨", "总线",
    "音频工程", "音频信号", "声压", "隔音", "吸音", "相位", "失真效果", "延迟效果",
]

TAG_RE = re.compile(r"<[^>]+>")
REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
TABLE_RE = re.compile(r"\{\|.*?\|\}", re.S)
TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
FILE_RE = re.compile(r"\[\[(?:File|文件|Image|图像):[^\]]*\]\]", re.I)
CAT_RE = re.compile(r"\[\[(?:Category|分类|分類):[^\]]*\]\]")
LINK_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
LINK2_RE = re.compile(r"\[\[([^\]]+)\]\]")
EXT_RE = re.compile(r"\[(?:https?://\S+)\s*([^\]]*)\]")
HEAD_RE = re.compile(r"^=+\s*(.*?)\s*=+$", re.M)
QUOTE_RE = re.compile(r"'{2,}")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_wikitext(text: str) -> str:
    text = COMMENT_RE.sub("", text)
    text = REF_RE.sub("", text)
    for _ in range(4):
        text = TEMPLATE_RE.sub("", text)
    text = TABLE_RE.sub("", text)
    text = FILE_RE.sub("", text)
    text = CAT_RE.sub("", text)
    text = LINK_RE.sub(r"\2", text)
    text = LINK2_RE.sub(r"\1", text)
    text = EXT_RE.sub(r"\1", text)
    text = HEAD_RE.sub(r"\1", text)
    text = TAG_RE.sub(" ", text)
    text = QUOTE_RE.sub("", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def chunk(text: str, size: int = 12000, min_size: int = 3000) -> list[str]:
    parts, i = [], 0
    while i < len(text):
        j = min(len(text), i + size)
        if j < len(text):
            cut = text.rfind("。", i + size // 2, j)
            if cut > i:
                j = cut + 1
        part = text[i:j].strip()
        if len(part) >= min_size:
            parts.append(part)
        i = j
    return parts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(DEFAULT_DUMP))
    ap.add_argument("--max-docs", type=int, default=8000)
    ap.add_argument("--max-chars", type=int, default=35_000_000)
    ap.add_argument("--min-chars", type=int, default=800)
    args = ap.parse_args()
    dump = Path(args.dump)
    if not dump.exists():
        sys.exit(f"缺少 dump：{dump}（先下载 zhwiki-latest-pages-articles.xml.bz2）")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    t0 = time.time()
    docs = 0
    chars = 0
    pages = 0
    fh = OUT.open("w", encoding="utf-8", newline="\n")
    try:
        with bz2.open(dump, "rb") as bf:
            stack: list = []
            for event, elem in ET.iterparse(bf, events=("start", "end")):
                if event == "start":
                    stack.append(elem)
                    continue
                if elem.tag == f"{NS}page":
                    pages += 1
                    ns = (elem.findtext(f"{NS}ns") or "").strip()
                    title = (elem.findtext(f"{NS}title") or "").strip()
                    redirect = elem.find(f"{NS}redirect")
                    rev = elem.find(f"{NS}revision")
                    text = ""
                    if rev is not None:
                        text = rev.findtext(f"{NS}text") or ""
                    if ns == "0" and redirect is None and text:
                        clean = clean_wikitext(text)
                        if args.min_chars <= len(clean) <= 150_000:
                            hay = title + " " + clean
                            if any(k in hay for k in KEYWORDS):
                                for k, part in enumerate(chunk(clean)):
                                    if docs >= args.max_docs or chars >= args.max_chars:
                                        break
                                    url = "https://zh.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
                                    fh.write(json.dumps({
                                        "doc_id": f"zhwiki-dump-{pages}-{k:03d}",
                                        "source": "zh-wikipedia-dump",
                                        "license": "CC-BY-SA-4.0",
                                        "tier": "T1",
                                        "title": title,
                                        "url": url,
                                        "kind": "chunk",
                                        "text": part,
                                        "retrieved_at": now(),
                                    }, ensure_ascii=False) + "\n")
                                    docs += 1
                                    chars += len(part)
                        # 清理父节点引用，避免内存增长
                        if len(stack) >= 2:
                            try:
                                stack[-2].remove(elem)
                            except ValueError:
                                pass
                    elem.clear()
                    if docs >= args.max_docs or chars >= args.max_chars:
                        print(f"达到上限：docs={docs} chars={chars/1e6:.1f}M", flush=True)
                        break
                    if pages % 20000 == 0:
                        print(f"  pages={pages:,} docs={docs:,} chars={chars/1e6:.1f}M "
                              f"{time.time()-t0:.0f}s", flush=True)
                if stack:
                    stack.pop()
    finally:
        fh.close()
    print(f"完成：pages={pages:,} docs={docs:,} chars={chars:,} "
          f"({chars/1e6:.1f}M) {time.time()-t0:.0f}s -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

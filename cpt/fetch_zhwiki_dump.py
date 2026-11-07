#!/usr/bin/env python3
"""从 zhwiki 官方 dump 中抽取音频/音乐制作相关中文条目，转为 CPT 原始 JSONL。

v2：更严格的领域匹配（强关键词 / 弱关键词组合）+ 更强的 wikitext 清洗
（去参考文献段、表格行、列表行、引用标记、残留标记），减少噪声条目。

  python cpt/fetch_zhwiki_dump.py [--dump PATH] [--max-docs 12000] [--max-chars 50000000]
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

# 强关键词：命中即视为音频/音乐制作相关
STRONG = [
    "混音", "母带", "均衡器", "压缩器", "混响", "效果器", "音频工程", "录音室", "调音台",
    "麦克风", "前置放大器", "声学", "心理声学", "音色", "和声", "对位", "编曲", "配器",
    "采样率", "频谱", "滤波器", "动态范围", "信噪比", "音频接口", "数字音频工作站",
    "合成器", "监听音箱", "声像", "响度", "音频信号", "音频处理", "音频文件格式",
    "录音技术", "立体声", "环绕声", "失真效果", "延迟效果", "频率响应", "MIDI",
    "音乐制作", "声音设计", "音效", "缩混", "母带处理", "多段压缩", "总线压缩",
]
# 弱关键词：需命中 ≥2 个不同词
WEAK = ["音频", "录音", "声音", "音乐", "压缩", "采样", "音轨", "分轨", "总线", "插件",
        "合成", "音高", "节拍", "分贝", "噪声", "降噪", "混音师", "音乐人", "乐器"]

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
CITE_RE = re.compile(r"\[\d+\]")
EMPTY_PAREN_RE = re.compile(r"[（(]\s*[，,、;；]?\s*[)）]")

STOP_SECTIONS = ["参考文献", "参考资料", "参考来源", "外部链接", "外部連結", "参见", "參見",
                 "注释", "註釋", "引用", "延伸阅读", "延伸閱讀", "相关条目", "相關條目",
                 "脚注", "腳註", "参考", "參考", "参考文献与注释"]


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
    text = CITE_RE.sub("", text)
    text = TAG_RE.sub(" ", text)
    text = QUOTE_RE.sub("", text)

    # 逐行清洗：去掉标题、表格/列表行、参考文献段
    out_lines: list[str] = []
    drop_section = False
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        m = HEAD_RE.match(s)
        if m:
            heading = m.group(1).strip()
            if any(h in heading for h in STOP_SECTIONS):
                drop_section = True
            else:
                drop_section = False
            continue
        if drop_section:
            continue
        if s[0] in "|!*#;:" or s.startswith("{{") or s.startswith("[["):
            continue
        if any(k in s for k in ("参考文献", "外部链接", "延伸阅读", "参见")):
            continue
        out_lines.append(s)

    text = "\n".join(out_lines)
    text = EMPTY_PAREN_RE.sub("", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = text.replace("|", "").replace("==", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_relevant(title: str, text: str) -> bool:
    hay = title + " " + text
    if any(k in hay for k in STRONG):
        return True
    weak_hits = sum(1 for k in WEAK if k in hay)
    return weak_hits >= 2


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
    if not parts and text.strip():
        parts = [text.strip()]
    return parts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(DEFAULT_DUMP))
    ap.add_argument("--max-docs", type=int, default=12000)
    ap.add_argument("--max-chars", type=int, default=60_000_000)
    ap.add_argument("--min-chars", type=int, default=1500)
    ap.add_argument("--max-pages", type=int, default=1_600_000)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    dump = Path(args.dump)
    if not dump.exists():
        sys.exit(f"缺少 dump：{dump}（先下载 zhwiki-latest-pages-articles.xml.bz2）")

    quick_keys = STRONG + WEAK
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    t0 = time.time()
    docs = chars = pages = kept_pages = 0
    fh = out.open("w", encoding="utf-8", newline="\n")
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
                    text = rev.findtext(f"{NS}text") if rev is not None else ""
                    # 先做廉价预筛：raw wikitext 命中关键词才进入昂贵的清洗
                    if (ns == "0" and redirect is None and text
                            and len(text) <= 300_000
                            and any(k in text or k in title for k in quick_keys)):
                        clean = clean_wikitext(text)
                        if args.min_chars <= len(clean) <= 150_000 and is_relevant(title, clean):
                            kept_pages += 1
                            url = "https://zh.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
                            for k, part in enumerate(chunk(clean)):
                                if docs >= args.max_docs or chars >= args.max_chars:
                                    break
                                fh.write(json.dumps({
                                    "doc_id": f"zhwiki-dump-{pages}-{k:03d}",
                                    "source": "zh-wikipedia-dump",
                                    "license": "CC-BY-SA-4.0",
                                    "tier": "T1",
                                    "title": title,
                                    "url": url,
                                    "kind": "chunk",
                                    "group_key": f"zhwiki:{title}",
                                    "text": part,
                                    "retrieved_at": now(),
                                }, ensure_ascii=False) + "\n")
                                docs += 1
                                chars += len(part)
                        if len(stack) >= 2:
                            try:
                                stack[-2].remove(elem)
                            except ValueError:
                                pass
                    elem.clear()
                    if docs >= args.max_docs or chars >= args.max_chars or pages >= args.max_pages:
                        print(f"停止：pages={pages:,} docs={docs} chars={chars/1e6:.1f}M", flush=True)
                        break
                    if pages % 50000 == 0:
                        fh.flush()
                        print(f"  pages={pages:,} kept_pages={kept_pages:,} docs={docs:,} "
                              f"chars={chars/1e6:.1f}M {time.time()-t0:.0f}s", flush=True)
                if stack:
                    stack.pop()
    finally:
        fh.close()
    print(f"完成：pages={pages:,} kept_pages={kept_pages:,} docs={docs:,} chars={chars:,} "
          f"({chars/1e6:.1f}M) {time.time()-t0:.0f}s -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

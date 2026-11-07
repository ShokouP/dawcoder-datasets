#!/usr/bin/env python3
"""语料质量清洗与重平衡（v0.3 curated）。

问题（见 cpt/QA-REPORT.md）：
  - Gutenberg 通过 "Opera"/"Category: Music"/"Songs" 匹配了大量小说/诗集/歌本（War and Peace 等）
  - Stack Exchange 短帖、链接/协议 boilerplate 占比高
  - arXiv 摘要混入 ML 量化/语言模型噪声
  - 中文占比极低

处理：
  1. Gutenberg：按目录元数据严格过滤（排除 fiction/poetry/song-texts；要求乐理/声学/教学/乐器/录音主题）
  2. 去 PG 版权页/校对者残留；每本书设字符上限
  3. SE：去短帖、链接过多/协议文本帖；music SE 只保留制作相关关键词帖
  4. arXiv：要求音频/混音关键词，去除 ML 噪声
  5. 输出 cpt/raw-curated/ + summary.json，供 build.py --raw-dir 使用
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "cpt" / "raw"
OUT = ROOT / "cpt" / "raw-curated"

# Gutenberg 严格规则 ------------------------------------------------------
PG_EXCLUDE = ["fiction", "novel", "poetry", "poems", "short stories", "drama", "libretto",
              "-- texts", "song texts", "songs, scottish", "juvenile literature", "fairy tales",
              "operas -- librettos", "musical fiction", "biography & autobiography"]
PG_REQUIRE = ["music theory", "harmony", "counterpoint", "acoustics", "sound -- recording",
              "recording and reproducing", "music -- instruction", "musical analysis", "orchestration",
              "instrumentation (music)", "singing -- instruction", "voice culture",
              "piano -- instruction", "violin -- instruction", "organ (musical instrument)",
              "tuning", "music appreciation", "musical form", "ear training", "conducting",
              "composition (music)", "musical instruments", "music -- history and criticism",
              "music -- philosophy", "sound", "speech", "elocution"]
PG_TITLE_OK = ["theory", "harmony", "acoustics", "method", "instruction", "treatise", "grammar",
               "counterpoint", "orchestration", "recording", "music", "musical", "sound", "voice",
               "piano", "organ", "violin", "singing", "elocution", "speech"]
PG_CHUNK_BOILER = ["project gutenberg", "produced by", "distributed proofreading", "etext",
                   "copyright", "transcriber", "end of this", "start of this"]
PG_BOOK_CHAR_CAP = 500_000  # 单本书最多保留字符，避免个别书主导

# Stack Exchange ----------------------------------------------------------
SE_MIN_CHARS = 400
SE_MAX_LINKS = 4
SE_MUSIC_KEYWORDS = ["mix", "record", "master", "eq", "equaliz", "compress", "reverb", "audio",
                     "microphone", "monitor", "sample", "plugin", "daw", "midi", "stereo", "phase",
                     "loudness", "headroom", "fader", "pan", "vocal", "amp", "distortion",
                     "clipping", "gain", "bus", "track", "session", "interface", "preamp",
                     "acoustic", "frequency", "noise", "signal"]
SE_MUSIC_TITLE_KEYWORDS = ["mix", "record", "master", "eq", "compress", "reverb", "audio",
                           "microphone", "monitor", "plugin", "daw", "midi", "sample", "phase",
                           "stereo", "loudness", "amp", "distortion", "gain", "track", "vocal"]

# arXiv -------------------------------------------------------------------
ARXIV_REQUIRE = ["mix", "source separation", "audio effect", "equaliz", "compress", "reverb",
                 "loudness", "spatial audio", "music production", "daw", "plugin", "reverberation",
                 "automix", "music information retrieval", "audio signal", "sound"]
ARXIV_EXCLUDE = ["quantization", "bert", "language model", "nlp", "llm", "fine-tun", "dataset distillation"]

TAG_RE = re.compile(r"<[^>]+>")


def strip_html(s: str) -> str:
    s = TAG_RE.sub(" ", s or "")
    import html as _h
    s = _h.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def load_catalog() -> dict[str, dict]:
    path = RAW / "pg_catalog.csv"
    out = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            out[row.get("Text#", "")] = row
    return out


def gutenberg_keep(book_id: str, catalog: dict[str, dict]) -> tuple[bool, str]:
    row = catalog.get(book_id)
    if not row:
        return False, "no-catalog-entry"
    hay = " ".join([row.get("Subjects") or "", row.get("Bookshelves") or "", row.get("LoCC") or ""]).lower()
    title = (row.get("Title") or "").lower()
    if any(x in hay for x in PG_EXCLUDE):
        return False, "excluded-fiction/poetry"
    if not any(x in hay for x in PG_REQUIRE):
        if not any(x in title for x in PG_TITLE_OK):
            return False, "not-music-nonfiction"
    if any(x in title for x in ["novel", "poems", "poetry", "songs of", "minstrel", "war and peace",
                                "byron", "jean-christophe", "pamela"]):
        return False, "excluded-title"
    return True, "ok"


def clean_gutenberg(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        low = line.lower()
        if any(b in low for b in PG_CHUNK_BOILER):
            continue
        lines.append(line)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "cpt"))
    from build import est_tokens  # noqa: E402

    sources = {s["id"]: s for s in yaml.safe_load((ROOT / "cpt" / "sources.yaml").read_text(encoding="utf-8"))["sources"]}
    catalog = load_catalog()
    OUT.mkdir(parents=True, exist_ok=True)

    summary: dict[str, dict] = {}
    for sid in sources:
        src = sources[sid]
        raw = RAW / f"{sid}.jsonl"
        if not raw.exists():
            continue
        kept: list[dict] = []
        seen: set[str] = set()
        drop: dict[str, int] = defaultdict(int)
        book_chars: dict[str, int] = defaultdict(int)
        for line in raw.open(encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            text = d.get("text", "") or ""
            doc_id = d.get("doc_id", "")
            if sid == "gutenberg-music":
                m = re.match(r"gutenberg-(\d+)-", doc_id)
                book_id = m.group(1) if m else ""
                ok, why = gutenberg_keep(book_id, catalog)
                if not ok:
                    drop[why] += 1
                    continue
                text = clean_gutenberg(text)
                if any(b in text.lower() for b in PG_CHUNK_BOILER[:2]):
                    drop["residual-boilerplate"] += 1
                    continue
                if book_chars[book_id] > PG_BOOK_CHAR_CAP:
                    drop["book-cap"] += 1
                    continue
                book_chars[book_id] += len(text)
            elif sid.startswith("stackexchange"):
                text = strip_html(text)
                if len(text) < SE_MIN_CHARS:
                    drop["too-short"] += 1
                    continue
                if text.lower().count("http") > SE_MAX_LINKS:
                    drop["too-many-links"] += 1
                    continue
                if sid == "stackexchange-music":
                    hay = (d.get("title", "") + " " + text).lower()
                    if not any(k in hay for k in SE_MUSIC_KEYWORDS):
                        drop["not-production"] += 1
                        continue
            elif sid == "arxiv-audio":
                hay = (d.get("title", "") + " " + text).lower()
                if not any(k in hay for k in ARXIV_REQUIRE):
                    drop["off-domain"] += 1
                    continue
                if any(k in hay for k in ARXIV_EXCLUDE):
                    drop["ml-noise"] += 1
                    continue
            elif sid == "dawproject-spec":
                text = strip_html(text)
            if len(text) < 200:
                drop["empty"] += 1
                continue
            h = d.get("text_sha256") or ""
            key = doc_id or text[:80]
            if key in seen:
                drop["duplicate"] += 1
                continue
            seen.add(key)
            d["text"] = text
            kept.append(d)
        out = OUT / f"{sid}.jsonl"
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept),
                       encoding="utf-8", newline="\n")
        chars = sum(len(r["text"]) for r in kept)
        summary[sid] = {"docs": len(kept), "chars": chars, "est_tokens": sum(est_tokens(r["text"]) for r in kept),
                        "dropped": dict(drop)}
        print(f"{sid}: {len(kept)} docs / {chars/1e6:.1f}M chars  dropped={dict(drop)}")

    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8", newline="\n")
    total = sum(v["est_tokens"] for v in summary.values())
    print(f"\ncurated total: ~{total/1e6:.1f}M tokens")


if __name__ == "__main__":
    main()

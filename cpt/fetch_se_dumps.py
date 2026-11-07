#!/usr/bin/env python3
"""把 Stack Exchange 官方数据转储（7z → Posts.xml）转成 CPT 原始 JSONL。

  python cpt/fetch_se_dumps.py --site sound
  python cpt/fetch_se_dumps.py --site all      # sound / music / avp

依赖：7z 在 PATH 上（Windows 用 7-Zip 安装目录的 7z.exe 亦可）。
输出：cpt/raw/stackexchange-<site>.jsonl（gitignored）
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "cpt" / "raw"
DUMPS = RAW / "dumps"
SITES = {"sound": "stackexchange-sound", "music": "stackexchange-music", "avp": "stackexchange-avp"}
TAG_RE = re.compile(r"<[^>]+>")
UA_NOTE = "Stack Exchange Inc. user contributions, CC BY-SA 4.0"


def log(msg: str) -> None:
    print(msg, flush=True)


def strip_html(s: str) -> str:
    s = TAG_RE.sub(" ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_xml(site: str) -> Path:
    archive = DUMPS / f"{site}.stackexchange.com.7z"
    if not archive.exists():
        sys.exit(f"缺少转储文件：{archive}（先下载）")
    target_dir = DUMPS / site
    target_dir.mkdir(parents=True, exist_ok=True)
    posts = target_dir / "Posts.xml"
    if posts.exists():
        return posts
    log(f"  解压 {archive.name} ...")
    subprocess.run(["7z", "x", "-y", f"-o{target_dir}", str(archive), "Posts.xml"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not posts.exists():
        # 有些转储里文件在根目录之外，直接整体解压
        subprocess.run(["7z", "x", "-y", f"-o{target_dir}", str(archive)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return posts


def convert(site: str) -> int:
    source_id = SITES[site]
    posts = extract_xml(site)
    out = RAW / f"{source_id}.jsonl"
    if out.exists():
        out.unlink()
    n = 0
    url_base = f"https://{site}.stackexchange.com"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for _, elem in ET.iterparse(str(posts), events=("end",)):
            if elem.tag != "row":
                continue
            post_type = elem.get("PostTypeId")
            if post_type not in ("1", "2"):
                elem.clear()
                continue
            body = strip_html(elem.get("Body", ""))
            if len(body) < 200:
                elem.clear()
                continue
            pid = elem.get("Id")
            parent = elem.get("ParentId", "")
            title = html.unescape(elem.get("Title") or "")
            if post_type == "1":
                doc_id = f"se-{site}-q{pid}"
                url = f"{url_base}/q/{pid}"
            else:
                doc_id = f"se-{site}-a{pid}"
                url = f"{url_base}/a/{pid}"
            fh.write(json.dumps({
                "doc_id": doc_id, "source": source_id, "license": "CC-BY-SA-4.0", "tier": "T1",
                "title": title, "url": url,
                "author": elem.get("OwnerDisplayName", ""),
                "kind": "question" if post_type == "1" else "answer",
                "score": int(elem.get("Score") or 0),
                "parent_id": parent,
                "text": body, "retrieved_at": now(),
                "attribution": UA_NOTE,
            }, ensure_ascii=False) + "\n")
            n += 1
            if n % 50000 == 0:
                log(f"    {site}: {n} posts")
            elem.clear()
    log(f"  {site}: {n} posts -> {out.name}")
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="all", choices=["all", *SITES])
    args = ap.parse_args()
    DUMPS.mkdir(parents=True, exist_ok=True)
    sites = list(SITES) if args.site == "all" else [args.site]
    for site in sites:
        log(f"转换 {site} ...")
        convert(site)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

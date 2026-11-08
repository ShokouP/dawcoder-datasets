#!/usr/bin/env python3
"""抓取 CPT 语料源（只抓原始数据到 cpt/raw/，不构建语料）。

  python cpt/fetch.py --source all            # 公开源（T0/T1）
  python cpt/fetch.py --source stackexchange-sound
  python cpt/fetch.py --source reaper-user-guide --accept-license   # T2 仅本地

抓取结果写入 cpt/raw/<source>.jsonl（gitignored）。单个源失败不阻塞其他源。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "cpt" / "raw"
UA = {"User-Agent": "DAWcoder-dataset-builder/0.1 (research; contact: Shokoup)"}


def log(msg: str) -> None:
    print(msg, flush=True)


def load_sources() -> dict:
    import yaml
    with (ROOT / "cpt" / "sources.yaml").open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {s["id"]: s for s in data["sources"]}


def fetch_json(url: str, retries: int = 4) -> dict:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:  # 429/503：退避
            last = exc
            if exc.code in (429, 503):
                wait = int(exc.headers.get("Retry-After") or 0) or 10 * (attempt + 1)
                log(f"    限速 {exc.code}，等待 {min(wait, 45)}s ...")
                time.sleep(min(wait, 45))
                continue
            time.sleep(2.0 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"请求失败：{url}：{last}")


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.read()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


# ------------------------------------------------------------------ wikipedia

def fetch_wikipedia(source: dict, out: Path) -> int:
    cfg = source["fetch"]
    titles: list[str] = []
    for category in cfg["categories"]:
        try:
            url = ("https://en.wikipedia.org/w/api.php?action=query&list=categorymembers"
                   f"&cmtitle={urllib.parse.quote('Category:' + category)}&cmlimit=200&format=json")
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  category 失败（跳过）：{category}：{exc}")
            continue
        for m in data.get("query", {}).get("categorymembers", []):
            if m.get("ns") == 0 and m["title"] not in titles:
                titles.append(m["title"])
        time.sleep(1.5)
    titles = titles[: cfg.get("max_pages", 200)]
    docs: dict[str, dict] = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        url = ("https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1"
               f"&exlimit=20&format=json&titles={urllib.parse.quote('|'.join(batch))}")
        try:
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  batch 失败（跳过）：{exc}")
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            if len(text) < 300:
                continue
            doc_id = f"wiki-{page.get('pageid')}"
            docs[doc_id] = {
                "doc_id": doc_id, "source": source["id"], "license": source["license"],
                "tier": source["tier"], "title": page.get("title", ""),
                "url": f"https://en.wikipedia.org/?curid={page.get('pageid')}",
                "kind": "intro", "text": text, "retrieved_at": now(),
            }
        log(f"  wikipedia intro: {min(i + 20, len(titles))}/{len(titles)}")
        time.sleep(1.5)
    full_n = int(cfg.get("full_text_pages", 0))
    for title in titles[:full_n]:
        try:
            url = ("https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1"
                   f"&exlimit=1&format=json&titles={urllib.parse.quote(title)}")
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  full-text 失败（跳过）：{title}：{exc}")
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            doc_id = f"wiki-{page.get('pageid')}"
            if len(text) >= 300 and (doc_id not in docs or len(text) > len(docs[doc_id]["text"])):
                docs[doc_id] = {
                    "doc_id": doc_id, "source": source["id"], "license": source["license"],
                    "tier": source["tier"], "title": page.get("title", ""),
                    "url": f"https://en.wikipedia.org/?curid={page.get('pageid')}",
                    "kind": "full", "text": text, "retrieved_at": now(),
                }
        time.sleep(2.0)
    log(f"  wikipedia 最终 {len(docs)} 篇")
    return append(out, list(docs.values()))


# --------------------------------------------------------------- stackexchange

TAG_RE = re.compile(r"<[^>]+>")


def strip_html(s: str) -> str:
    s = TAG_RE.sub(" ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def fetch_stackexchange(source: dict, out: Path) -> int:
    cfg = source["fetch"]
    site = cfg["site"]
    rows: list[dict] = []
    for tag in cfg["tags"]:
        try:
            url = (f"https://api.stackexchange.com/2.3/questions?site={site}&tagged={urllib.parse.quote(tag)}"
                   f"&sort=votes&order=desc&pagesize={cfg.get('questions_per_tag', 60)}&filter=withbody")
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  {site}/{tag} 失败（跳过）：{exc}")
            continue
        items = data.get("items", [])
        ids = [str(q["question_id"]) for q in items]
        answers: dict[int, list[dict]] = {}
        if ids:
            page = 1
            while page <= 2:
                try:
                    aurl = (f"https://api.stackexchange.com/2.3/questions/{';'.join(ids)}/answers"
                            f"?site={site}&sort=votes&order=desc&pagesize=100&filter=withbody&page={page}")
                    adata = fetch_json(aurl)
                except RuntimeError as exc:
                    log(f"  answers 失败（跳过）：{exc}")
                    break
                for a in adata.get("items", []):
                    answers.setdefault(a["question_id"], []).append(a)
                if not adata.get("has_more") or page == 2:
                    break
                page += 1
                time.sleep(0.6)
        for q in items:
            body = strip_html(q.get("body", ""))
            if len(body) >= 200:
                rows.append({
                    "doc_id": f"se-{site}-q{q['question_id']}", "source": source["id"],
                    "license": source["license"], "tier": source["tier"],
                    "title": html.unescape(q.get("title", "")), "url": q.get("link", ""),
                    "author": q.get("owner", {}).get("display_name", ""),
                    "kind": "question", "score": q.get("score", 0),
                    "text": body, "retrieved_at": now(),
                })
            for a in answers.get(q["question_id"], []):
                abody = strip_html(a.get("body", ""))
                if len(abody) >= 200:
                    rows.append({
                        "doc_id": f"se-{site}-a{a['answer_id']}", "source": source["id"],
                        "license": source["license"], "tier": source["tier"],
                        "title": html.unescape(q.get("title", "")), "url": q.get("link", ""),
                        "author": a.get("owner", {}).get("display_name", ""),
                        "kind": "answer", "score": a.get("score", 0),
                        "text": abody, "retrieved_at": now(),
                    })
        log(f"  {site}: tag={tag} questions={len(items)} docs_so_far={len(rows)}")
        time.sleep(0.4)
        if data.get("backoff"):
            time.sleep(float(data["backoff"]))
    return append(out, rows)


# ------------------------------------------------------------------ arxiv

ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(source: dict, out: Path) -> int:
    cfg = source["fetch"]
    rows: list[dict] = []
    for query in cfg["queries"]:
        url = ("http://export.arxiv.org/api/query?search_query=all:"
               f"{urllib.parse.quote(query)}&start=0&max_results={cfg.get('max_results_per_query', 40)}"
               "&sortBy=relevance")
        try:
            raw = fetch_bytes(url)
            root = ET.fromstring(raw)
        except Exception as exc:  # noqa: BLE001
            log(f"  arxiv 查询失败（跳过）：{query}：{exc}")
            continue
        for entry in root.findall(f"{ATOM}entry"):
            title = " ".join((entry.findtext(f"{ATOM}title") or "").split())
            summary = " ".join((entry.findtext(f"{ATOM}summary") or "").split())
            link = entry.findtext(f"{ATOM}id") or ""
            published = (entry.findtext(f"{ATOM}published") or "")[:10]
            if len(summary) < 200:
                continue
            rows.append({
                "doc_id": "arxiv-" + link.rsplit("/", 1)[-1],
                "source": source["id"], "license": source["license"], "tier": source["tier"],
                "title": title, "url": link, "kind": "abstract", "published": published,
                "text": f"{title}\n\n{summary}", "retrieved_at": now(),
            })
        log(f"  arxiv: {query} -> {len(rows)} docs")
        time.sleep(3.0)
    return append(out, rows)


# ------------------------------------------------------------------ wikipedia titles（中文）

def fetch_wikipedia_titles(source: dict, out: Path) -> int:
    cfg = source["fetch"]
    site = cfg.get("site", "zh.wikipedia.org")
    docs: list[dict] = []
    for title in cfg["titles"]:
        url = (f"https://{site}/w/api.php?action=query&prop=extracts&explaintext=1"
               f"&exlimit=1&redirects=1&format=json&titles={urllib.parse.quote(title)}")
        try:
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  条目失败（跳过）：{title}：{exc}")
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            if len(text) < 200:
                continue
            docs.append({
                "doc_id": f"zhwiki-{page.get('pageid')}", "source": source["id"],
                "license": source["license"], "tier": source["tier"],
                "title": page.get("title", ""),
                "url": f"https://{site}/?curid={page.get('pageid')}",
                "kind": "full", "text": text, "retrieved_at": now(),
            })
        time.sleep(2.0)
    log(f"  {site} 最终 {len(docs)} 篇")
    return append(out, docs)


def fetch_mediawiki_search(source: dict, out: Path) -> int:
    """通用 MediaWiki 搜索 + 全文抓取（维基文库 / 维基教科书等，CC BY-SA / 公版）。"""
    cfg = source["fetch"]
    site = cfg.get("site", "zh.wikisource.org")
    titles: list[str] = []
    for q in cfg["queries"]:
        url = (f"https://{site}/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(q)}"
               f"&srlimit={cfg.get('search_limit', 40)}&srnamespace=0&format=json")
        try:
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  搜索失败（跳过）：{q}：{exc}")
            continue
        for item in data.get("query", {}).get("search", []):
            if item["title"] not in titles:
                titles.append(item["title"])
        time.sleep(1.2)
    log(f"  {site} 搜索到 {len(titles)} 个标题")
    docs: list[dict] = []
    chars = 0
    for title in titles:
        if len(docs) >= cfg.get("max_docs", 250) or chars >= cfg.get("max_chars", 8_000_000):
            break
        url = (f"https://{site}/w/api.php?action=query&prop=extracts&explaintext=1"
               f"&exlimit=1&redirects=1&format=json&titles={urllib.parse.quote(title)}")
        try:
            data = fetch_json(url)
        except RuntimeError:
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            if len(text) < int(cfg.get("min_chars", 4000)):
                continue
            docs.append({
                "doc_id": f"mw-{site.split('.')[0]}-{page.get('pageid')}", "source": source["id"],
                "license": source["license"], "tier": source["tier"],
                "title": page.get("title", ""),
                "url": f"https://{site}/?curid={page.get('pageid')}",
                "kind": "text", "text": text, "retrieved_at": now(),
            })
            chars += len(text)
        time.sleep(1.2)
    log(f"  {site} 最终 {len(docs)} 篇 / {chars / 1e6:.1f}M 字符")
    return append(out, docs)


def fetch_mediawiki_search_intro(source: dict, out: Path) -> int:
    """搜索 + 批量导语抓取（20 条/请求，适合大批量轻量补充，CC BY-SA）。"""
    cfg = source["fetch"]
    site = cfg.get("site", "zh.wikipedia.org")
    titles: list[str] = []
    for q in cfg["queries"]:
        url = (f"https://{site}/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(q)}"
               f"&srlimit={cfg.get('search_limit', 40)}&srnamespace=0&format=json")
        try:
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  搜索失败（跳过）：{q}：{exc}")
            continue
        for item in data.get("query", {}).get("search", []):
            if item["title"] not in titles:
                titles.append(item["title"])
        time.sleep(2.0)
    titles = titles[: int(cfg.get("max_titles", 300))]
    log(f"  {site} 搜索到 {len(titles)} 个标题")
    docs: list[dict] = []
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        url = (f"https://{site}/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1"
               f"&exlimit=20&redirects=1&format=json&titles={urllib.parse.quote('|'.join(batch))}")
        try:
            data = fetch_json(url)
        except RuntimeError as exc:
            log(f"  batch 失败（跳过）：{exc}")
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            if len(text) < int(cfg.get("min_chars", 250)):
                continue
            docs.append({
                "doc_id": f"mwintro-{site.split('.')[0]}-{page.get('pageid')}",
                "source": source["id"], "license": source["license"], "tier": source["tier"],
                "title": page.get("title", ""),
                "url": f"https://{site}/?curid={page.get('pageid')}",
                "kind": "intro", "text": text, "retrieved_at": now(),
            })
        time.sleep(3.0)
    log(f"  {site} 最终 {len(docs)} 篇")
    return append(out, docs)


# ------------------------------------------------------------------ gutenberg

PG_KEYWORDS = ("music", "musical", "sound", "acoustic", "harmony", "counterpoint",
               "orchestra", "piano", "violin", "opera", "audio", "singing", "song")
CHUNK = 12000


def chunk_text(text: str) -> list[str]:
    """把长书拆成 3k–12k 字符的块，便于 CPT 打包。"""
    parts: list[str] = []
    i = 0
    while i < len(text):
        j = min(len(text), i + CHUNK)
        if j < len(text):
            cut = text.rfind(" ", i + CHUNK // 2, j)
            if cut > i:
                j = cut
        part = text[i:j].strip()
        if len(part) >= 3000:
            parts.append(part)
        i = j
    return parts


def fetch_gutenberg(source: dict, out: Path) -> int:
    import csv
    from concurrent.futures import ThreadPoolExecutor, as_completed
    cfg = source["fetch"]
    catalog = RAW / "pg_catalog.csv"
    if not catalog.exists():
        log("  下载 Gutenberg 目录 ...")
        catalog.write_bytes(fetch_bytes("https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"))
    max_books = int(cfg.get("max_books", 400))
    candidates: list[dict] = []
    with catalog.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("Type") != "Text" or "en" not in (row.get("Language") or ""):
                continue
            hay = " ".join([row.get("Subjects") or "", row.get("Bookshelves") or "", row.get("LoCC") or ""]).lower()
            if not any(k in hay for k in PG_KEYWORDS):
                continue
            candidates.append({"id": row.get("Text#", ""), "title": row.get("Title", ""),
                               "authors": row.get("Authors", "")})
    log(f"  gutenberg 候选 {len(candidates)} 本，下载上限 {max_books}")
    rows: list[dict] = []
    start_re = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.I | re.S)
    end_re = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.I | re.S)

    def one(book: dict) -> list[dict]:
        url = f"https://www.gutenberg.org/cache/epub/{book['id']}/pg{book['id']}.txt"
        try:
            raw = fetch_bytes(url)
        except Exception:  # noqa: BLE001
            return []
        if len(raw) > 8_000_000:
            return []
        text = raw.decode("utf-8", errors="replace")
        m = start_re.search(text)
        if m:
            text = text[m.end():]
        m = end_re.search(text)
        if m:
            text = text[:m.start()]
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 5000:
            return []
        out_rows = []
        for k, part in enumerate(chunk_text(text)):
            out_rows.append({
                "doc_id": f"gutenberg-{book['id']}-{k:03d}", "source": source["id"],
                "license": "Public-Domain", "tier": "T0",
                "title": book["title"], "url": f"https://www.gutenberg.org/ebooks/{book['id']}",
                "author": book["authors"], "kind": "book-chunk", "text": part, "retrieved_at": now(),
            })
        return out_rows

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(one, b): b for b in candidates[:max_books]}
        for fut in as_completed(futures):
            rows.extend(fut.result())
            if len(rows) % 200 < 5:
                log(f"    gutenberg: {len(rows)} chunks")
    return append(out, rows)


# ------------------------------------------------------------------ raw_url

def fetch_raw_url(source: dict, out: Path) -> int:
    rows = []
    for spec in source["fetch"]["files"]:
        try:
            text = fetch_bytes(spec["url"]).decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            log(f"  失败（跳过）：{spec['url']}：{exc}")
            continue
        if len(text) < 200:
            continue
        rows.append({
            "doc_id": f"raw-{source['id']}-{len(rows)}", "source": source["id"],
            "license": source["license"], "tier": source["tier"],
            "title": spec.get("title", spec["url"]), "url": spec["url"],
            "text": text, "retrieved_at": now(),
        })
    return append(out, rows)


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="all")
    ap.add_argument("--accept-license", action="store_true")
    ap.add_argument("--clean", action="store_true", help="先清空 cpt/raw")
    args = ap.parse_args()

    sources = load_sources()
    if args.clean and RAW.exists():
        for p in RAW.glob("*.jsonl"):
            p.unlink()

    targets = list(sources) if args.source == "all" else [args.source]
    for sid in targets:
        src = sources.get(sid)
        if not src:
            log(f"未知源：{sid}")
            continue
        tier = src["tier"]
        if tier == "T3":
            log(f"跳过 T3：{sid}")
            continue
        if tier == "T2" and not args.accept_license:
            log(f"跳过 T2（需 --accept-license）：{sid}")
            continue
        method = src["fetch"].get("method")
        out = RAW / f"{sid}.jsonl"
        log(f"抓取 {sid}（{src['license']}, {tier}）...")
        try:
            if method == "wikipedia":
                n = fetch_wikipedia(src, out)
            elif method == "wikipedia_titles":
                n = fetch_wikipedia_titles(src, out)
            elif method == "mediawiki_search":
                n = fetch_mediawiki_search(src, out)
            elif method == "mediawiki_search_intro":
                n = fetch_mediawiki_search_intro(src, out)
            elif method == "stackexchange_dump":
                log("  Stack Exchange 全量转储由 cpt/fetch_se_dumps.py 处理（先下载 7z）")
                continue
            elif method == "stackexchange":
                n = fetch_stackexchange(src, out)
            elif method == "arxiv":
                n = fetch_arxiv(src, out)
            elif method == "gutenberg":
                n = fetch_gutenberg(src, out)
            elif method == "raw_url":
                n = fetch_raw_url(src, out)
            elif method == "github_docs":
                import subprocess
                subprocess.run([sys.executable, str(ROOT / "cpt" / "collect_open_docs.py"), "--source", sid], check=True)
                n = sum(1 for line in out.open(encoding="utf-8") if line.strip())
            elif method == "synthetic":
                log("  合成源由 cpt/build.py 生成，跳过抓取")
                continue
            elif method == "manual_request":
                log(f"  需手动获取：{src['fetch'].get('url')}")
                continue
            else:
                log(f"  未知抓取方式：{method}")
                continue
        except Exception as exc:  # noqa: BLE001
            log(f"  !! {sid} 抓取失败：{exc}")
            if not src.get("optional"):
                log("  （非可选源失败，继续下一个）")
            continue
        log(f"  -> {out.relative_to(ROOT)}：追加 {n} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

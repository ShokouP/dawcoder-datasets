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
            elif method == "stackexchange":
                n = fetch_stackexchange(src, out)
            elif method == "arxiv":
                n = fetch_arxiv(src, out)
            elif method == "raw_url":
                n = fetch_raw_url(src, out)
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

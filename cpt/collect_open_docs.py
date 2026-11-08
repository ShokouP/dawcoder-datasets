#!/usr/bin/env python3
"""Fetch pinned, allowlisted documentation; never execute downloaded code.

python cpt/collect_open_docs.py --source all
Git metadata and HTTP blobs are cached under cpt/raw/. Commit pins and the
original license texts are retained outside the cache for reproducibility.
"""
from __future__ import annotations
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
CPT = ROOT / "cpt"
RAW = CPT / "raw"
CONFIG = CPT / "open_docs_sources.json"
LOCK = CPT / "open_docs.lock.json"
HEADERS = {"User-Agent": "DAWcoder-open-docs/1.0 (+https://github.com/ShokouP/dawcoder-datasets)"}


def request(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError(f"Text file too large: {url}")
            return data
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404) or attempt == 2:
                raise
        except OSError:
            if attempt == 2:
                raise
        time.sleep(2 * (attempt + 1))


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.PIPE, timeout=180).decode("utf-8").strip()


def tree_for(spec, commit):
    repository = spec["repo"]
    try:
        data = json.loads(request(f"https://api.github.com/repos/{repository}/git/trees/{commit}?recursive=1"))
        if data.get("truncated"):
            raise ValueError("GitHub tree truncated")
        return [(item["path"], item["sha"]) for item in data["tree"] if item["type"] == "blob"]
    except (OSError, ValueError):
        cache = RAW / "git-metadata" / repository.replace("/", "--")
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            git("clone", "--depth", "1", "--filter=blob:none", "--no-checkout", "https://github.com/" + repository + ".git", str(cache))
        if git("-C", str(cache), "rev-parse", "HEAD") != commit:
            git("-C", str(cache), "fetch", "--depth", "1", "--filter=blob:none", "origin", commit)
        data = subprocess.check_output(["git", "-C", str(cache), "ls-tree", "-rz", commit], timeout=60)
        result = []
        for entry in data.split(b"\0"):
            if not entry:
                continue
            meta, path = entry.split(b"\t", 1)
            _, kind, sha = meta.split()
            if kind == b"blob":
                result.append((path.decode("utf-8"), sha.decode()))
        return result


def chunk_text(text, size=10000):
    text = text.strip()
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", size // 2, size)
        if cut < 0:
            cut = text.rfind(" ", size // 2, size)
        if cut < 0:
            cut = size
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if len(text) < 300 and parts:
        parts[-1] += "\n" + text
    elif len(text) >= 300:
        parts.append(text)
    return parts


def clean_markup(text):
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"^\s*\.\.\s+(image|figure|include|automodule|autoclass|autofunction|toctree)::[^\n]*", "", text, flags=re.M)
    text = re.sub(r":(?:ref|doc|class|func|meth|attr|mod):\x60([^\x60]+)\x60", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def documents(path, text):
    if path.endswith(".py"):
        # AST parsing only; importing third-party source would execute it.
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                if doc and len(doc) >= 300:
                    yield f"{getattr(node, 'name', 'module')}:{getattr(node, 'lineno', 0)}", doc
    elif path.endswith(".po"):
        import polib
        entries = polib.pofile(text)
        translated = [entry.msgstr for entry in entries if entry.translated() and not entry.obsolete]
        if translated:
            yield "translation", "\n\n".join(translated)
    else:
        yield "page", clean_markup(text)


def group_key(spec, path):
    if spec["id"] == "sonic-pi-tutorial":
        # PO files contain many chapters: keep the entire translated book together.
        return f"{spec['repo']}:tutorial"
    return f"{spec['repo']}:{path}"


def collect_source(spec, pinned=None, workers=4):
    repository, sid = spec["repo"], spec["id"]
    commit = pinned or git("ls-remote", "https://github.com/" + repository + ".git", "HEAD").split()[0]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid pinned revision")
    paths = tree_for(spec, commit)
    blob_map = dict(paths)
    license_path = spec["license_path"]
    if license_path not in blob_map:
        raise ValueError(f"Missing license: {repository}/{license_path}")
    cache = RAW / "open-doc-blobs" / sid / commit
    cache.mkdir(parents=True, exist_ok=True)

    def fetch_blob(path, expected):
        key = hashlib.sha256(path.encode()).hexdigest()
        dest = cache / key
        data = dest.read_bytes() if dest.exists() else request(f"https://raw.githubusercontent.com/{repository}/{commit}/{urllib.parse.quote(path)}")
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != expected:
            raise ValueError(f"Git blob hash mismatch: {path}")
        if not dest.exists():
            dest.write_bytes(data)
        return data

    license_bytes = fetch_blob(license_path, blob_map[license_path])
    license_text = license_bytes.decode("utf-8-sig")
    if spec["license_marker"].lower() not in license_text.lower():
        raise ValueError(f"License marker changed: {sid}")
    license_dir = CPT / "licenses"
    license_dir.mkdir(exist_ok=True)
    (license_dir / (sid + ".txt")).write_bytes(license_bytes)
    overrides = [p.rsplit("/", 1)[0] + "/" for p, _ in paths if p != license_path and "/" in p and p.rsplit("/", 1)[-1].lower().startswith(("license", "copying"))]
    chosen = [(p, sha) for p, sha in paths if any(fnmatch.fnmatchcase(p, pattern) for pattern in spec["include"]) and not any(fnmatch.fnmatchcase(p, pattern) for pattern in spec.get("exclude", ["*/tests/*", "*/test_*.py", "*/changelog*", "*/changes*", "*/conf.py"])) and not any(p.startswith(prefix) for prefix in overrides)]
    errors, records, downloaded = [], [], []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def one(item):
        path, sha = item
        try:
            data = fetch_blob(path, sha)
            text = data.decode("utf-8-sig")
            rows = []
            for fragment, content in documents(path, text):
                for index, chunk in enumerate(chunk_text(content)):
                    identity = f"{path}#{fragment}:{index}"
                    rows.append({"doc_id": sid + "-" + hashlib.sha256(identity.encode()).hexdigest()[:20], "source": sid,
                                 "license": spec["license"], "tier": "T0" if spec["license"] == "CC0-1.0" else "T1",
                                 "title": f"{spec['title']} / {path} / {fragment}",
                                 "url": f"https://github.com/{repository}/blob/{commit}/{urllib.parse.quote(path)}",
                                 "author": spec.get("author", repository + " contributors"), "kind": "documentation",
                                 "revision": commit, "source_path": path, "source_blob_sha": sha,
                                 "license_url": f"https://github.com/{repository}/blob/{commit}/{license_path}",
                                 "license_text_path": f"cpt/licenses/{sid}.txt", "group_key": group_key(spec, path),
                                 "text": chunk, "retrieved_at": stamp})
            return rows, {"path": path, "git_blob_sha": sha, "sha256": hashlib.sha256(data).hexdigest(), "docs": len(rows)}, None
        except Exception as exc:
            return [], None, {"path": path, "error": str(exc)}

    print(f"{sid}: {repository}@{commit}, {len(chosen)} candidate files", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, (rows, file_meta, error) in enumerate(pool.map(one, chosen)):
            records.extend(rows)
            if error:
                errors.append(error)
            if file_meta:
                downloaded.append(file_meta)
            if (index + 1) % 100 == 0:
                print(f"  {sid}: {index+1}/{len(chosen)} files, {len(records)} docs", flush=True)
    if not records:
        raise ValueError(f"No documentation extracted: {sid}; errors={errors[:3]}")
    output = RAW / (sid + ".jsonl")
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8", newline="\n")
    result = {"repo": repository, "commit": commit, "license": spec["license"], "license_path": license_path,
              "license_sha256": hashlib.sha256(license_bytes).hexdigest(), "license_url": f"https://github.com/{repository}/blob/{commit}/{license_path}",
              "retrieved_at": stamp, "docs": len(records), "chars": sum(len(row["text"]) for row in records),
              "raw_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "files": downloaded, "errors": errors, "complete": not errors}
    print(f"  -> {len(records)} docs / {result['chars']:,} chars / {len(errors)} errors", flush=True)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="all", help="comma-separated source IDs or all")
    ap.add_argument("--refresh", action="store_true", help="explicitly update pinned commits")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if not 1 <= args.workers <= 8:
        ap.error("--workers must be 1..8")
    specs = json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {"version": 1, "sources": {}}
    requested = {spec["id"] for spec in specs} if args.source == "all" else set(args.source.split(","))
    if requested - {spec["id"] for spec in specs}:
        ap.error("Unknown source ID")
    failed = False
    for spec in specs:
        sid = spec["id"]
        if sid not in requested:
            continue
        try:
            pinned = None if args.refresh else lock["sources"].get(sid, {}).get("commit")
            result = collect_source(spec, pinned, args.workers)
            lock["sources"][sid] = result
            failed |= not result["complete"]
        except Exception as exc:
            failed = True
            print(f"FAILED {sid}: {exc}", flush=True)
            # Retain the last successful snapshot; record failure separately.
            lock.setdefault("last_errors", {})[sid] = str(exc)
        else:
            lock.setdefault("last_errors", {}).pop(sid, None)
        LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())


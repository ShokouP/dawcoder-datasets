#!/usr/bin/env python3
"""DAWcoder dataset registry validator.

Usage:
    python tools/validate.py            # 结构 + 许可一致性
    python tools/validate.py --strict   # 额外检查 evidence / fetch / 文件守卫
    python tools/validate.py --release  # 发布前：要求 sha256 齐全
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖：pip install pyyaml jsonschema")

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

ROOT = Path(__file__).resolve().parent.parent
MEDIA_EXT = {".wav", ".flac", ".mp3", ".m4a", ".aif", ".aiff", ".ogg", ".flp", ".als", ".rpp", ".mid", ".midi", ".mxl", ".zip"}
MAX_BLOB = 5 * 1024 * 1024  # 5MB
MAX_TEXT_BLOB = 20 * 1024 * 1024  # jsonl/json 等训练数据文本放宽到 20MB
TEXT_EXT = {".jsonl", ".json", ".md", ".py", ".yaml", ".yml", ".txt", ".toml"}
FIXTURE_DIR = "fixtures"


class Result:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def check_files(res: Result) -> None:
    """仓库文件守卫：禁止提交媒体/工程二进制，大文件告警。"""
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in MEDIA_EXT and not rel.startswith(FIXTURE_DIR + "/"):
            res.error(f"[file] 禁止提交媒体/工程文件：{rel}（应走 fetch 脚本）")
        limit = MAX_TEXT_BLOB if path.suffix.lower() in TEXT_EXT else MAX_BLOB
        if path.stat().st_size > limit:
            res.error(f"[file] 文件超过上限 {limit // 1024 // 1024}MB：{rel}")


def check_registry(res: Result, strict: bool, release: bool) -> None:
    reg = load_yaml(ROOT / "registry" / "datasets.yaml")
    lic = load_yaml(ROOT / "registry" / "licenses.yaml")["licenses"]
    schema = json.loads((ROOT / "schemas" / "dataset.schema.json").read_text(encoding="utf-8"))
    seen: set[str] = set()

    for ds in reg.get("datasets", []):
        did = ds.get("id", "<missing-id>")
        where = f"[{did}]"
        if did in seen:
            res.error(f"{where} id 重复")
        seen.add(did)

        if jsonschema is not None:
            try:
                jsonschema.validate(ds, schema)
            except jsonschema.ValidationError as exc:
                res.error(f"{where} schema: {exc.message}")
                continue

        spdx = ds["license"]["spdx"]
        if spdx not in lic:
            res.error(f"{where} 未知许可 SPDX：{spdx}（先加到 registry/licenses.yaml）")
            continue
        meta = lic[spdx]
        if meta["tier"] == "T3" and ds.get("fetch", {}).get("method") not in (None, "none"):
            # T3 只允许本地，不存在可执行 fetch
            if ds["fetch"].get("url"):
                res.warn(f"{where} T3 数据不应提供可执行 fetch URL")

        ev = ds["license"].get("evidence", {})
        if strict and meta["tier"] in {"T1", "T2"}:
            if not (ev.get("url") and ev.get("captured_at") and ev.get("reviewer")):
                res.error(f"{where} 缺少许可证据（url/captured_at/reviewer）")

        fetch = ds.get("fetch", {})
        if strict and meta["tier"] in {"T1", "T2"} and not ds.get("in_repo"):
            if fetch.get("method") in (None, "none") or not fetch.get("url"):
                res.error(f"{where} T1/T2 必须提供 fetch 脚本与 URL")
        if release and fetch.get("method") in {"zenodo", "url", "git"} and not fetch.get("sha256"):
            res.error(f"{where} 发布前必须填写 sha256")

        card = ROOT / "cards" / f"{did}.md"
        if strict and not card.exists():
            res.error(f"{where} 缺少数据卡 cards/{did}.md")
        if strict and card.exists():
            text = card.read_text(encoding="utf-8")
            for key in ("## 许可", "## 引用", "## 已知问题"):
                if key not in text:
                    res.error(f"{where} 数据卡缺少小节：{key}")

        split = ds.get("splits", {})
        if split.get("policy") == "song_level" and not split.get("group_key"):
            res.error(f"{where} song_level 切分必须给 group_key")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args()
    res = Result()
    check_registry(res, args.strict, args.release)
    check_files(res)
    for w in res.warnings:
        print("WARN ", w)
    for e in res.errors:
        print("ERROR", e)
    print(f"\n{len(res.errors)} error(s), {len(res.warnings)} warning(s)")
    return 1 if res.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

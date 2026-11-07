#!/usr/bin/env python3
"""按 registry 下载第三方数据；T2 必须显式接受非商用条款，T3 拒绝。

Usage:
    python tools/fetch.py slakh2100 --dest D:/data --accept-license
    python tools/fetch.py musdb18 --dest D:/data --accept-license   # 仅研究用途
    python tools/fetch.py slakh2100 --dest D:/data --sha256 abc123...
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LICENSE_NOTE = """\
注意：该数据集为非商用/研究许可（T2）。
- 不得用于商业产品或商用训练集；
- 不得再分发数据本体；
- 下载即表示你已阅读并接受其原始许可条款。
"""


def load_registry() -> dict:
    with (ROOT / "registry" / "datasets.yaml").open(encoding="utf-8") as fh:
        return {d["id"]: d for d in yaml.safe_load(fh)["datasets"]}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset_id")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--accept-license", action="store_true")
    ap.add_argument("--sha256", default="")
    args = ap.parse_args()

    entry = load_registry().get(args.dataset_id)
    if not entry:
        sys.exit(f"未注册的数据集：{args.dataset_id}")
    tier = entry["license"].get("tier") or ""
    fetch = entry.get("fetch", {})
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    # 档位来自 licenses.yaml 推导；这里从 fetch 信息与许可证据判断
    sys.path.insert(0, str(ROOT / "tools"))
    from validate import load_yaml  # noqa: E402

    lic = load_yaml(ROOT / "registry" / "licenses.yaml")["licenses"]
    tier = lic[entry["license"]["spdx"]]["tier"]

    if tier == "T3":
        sys.exit("T3 数据禁止获取/分发，仅可本地自行准备。")
    if tier == "T2" and not args.accept_license:
        sys.exit("T2 数据需要 --accept-license 显式确认：" + LICENSE_NOTE)

    method = fetch.get("method", "none")
    if method in ("manual_request", "none"):
        print(f"{args.dataset_id}：请按说明手动申请：{fetch.get('url')}")
        print(f"备注：{entry.get('notes', '')}")
        return 0

    url = fetch["url"]
    name = url.rstrip("/").split("/")[-1] or f"{args.dataset_id}.bin"
    out = dest / name
    print(f"下载 {url}\n -> {out}")
    urllib.request.urlretrieve(url, out)  # 大文件建议改用 aria2/wget

    want = args.sha256 or fetch.get("sha256", "")
    if want:
        got = sha256_of(out)
        if got != want:
            sys.exit(f"sha256 不匹配：{got} != {want}")
        print("sha256 校验通过")
    else:
        print("提示：未提供 sha256，发布前请补 registry 并重跑校验")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

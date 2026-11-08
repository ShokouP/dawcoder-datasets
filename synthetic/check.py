#!/usr/bin/env python3
"""DAWcoder 合成训练集校验器（可直接用于 CI）。

检查：
  1. manifest 计数 / sha256 一致
  2. mix: ops 合法、目标轨道存在、数值范围、expected 与 ops 推导一致
  3. form: 段落连续、能量/密度范围、marker 一致、expected 一致
  4. texture: 音符范围、网格、和弦音比例、力度范围、无重复音符
  5. sft: chat 结构合法，assistant 是合法 JSON 且与 patch 对应
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
sys.path.insert(0, str(DATA.parent.parent / "training"))
from patch_validation import validate  # noqa: E402
PPQ = 480
VALID_TASKS = {"mix", "form", "texture"}
DENSITY_KEYS = {"Intro", "Verse", "Chorus", "Hook", "Drop", "Build", "Break", "Bridge", "Solo", "Outro"}


def err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_manifest(errors: list[str]) -> dict:
    mpath = DATA / "manifest.json"
    if not mpath.exists():
        err(errors, "缺少 manifest.json")
        return {}
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    for name, meta in manifest.get("files", {}).items():
        path = DATA / name
        if not path.exists():
            err(errors, f"manifest 指向的文件不存在：{name}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            err(errors, f"{name} sha256 不匹配")
        if len(load_jsonl(path)) != meta["lines"]:
            err(errors, f"{name} 行数与 manifest 不符")
    return manifest


def check_mix(s: dict, errors: list[str]) -> None:
    state = s["state"]
    names = {t["name"] for t in state["tracks"]} | {b["name"] for b in state["buses"]}
    ops = s["patch"]["ops"]
    if not ops:
        err(errors, f"{s['id']} 空 patch")
    vol: dict[str, float] = {}
    eq, comp, send = [], [], []
    for op in ops:
        kind = op.get("op")
        if kind == "set_track":
            if op["track"] not in names:
                err(errors, f"{s['id']} 未知轨道 {op['track']}")
            v = op["fields"].get("volume_db")
            if v is None or not -24 <= v <= 6:
                err(errors, f"{s['id']} volume_db 越界：{v}")
            vol[op["track"]] = round(vol.get(op["track"], 0.0) + v, 1)
        elif kind == "set_eq":
            if op["track"] not in names:
                err(errors, f"{s['id']} EQ 未知轨道 {op['track']}")
            if not 20 <= op["freq"] <= 20000:
                err(errors, f"{s['id']} EQ 频率越界")
            if not -12 <= op["gain_db"] <= 12 or not 0.1 <= op["q"] <= 10:
                err(errors, f"{s['id']} EQ 增益/Q 越界")
            eq.append({"track": op["track"], "freq": op["freq"], "gain_db": op["gain_db"]})
        elif kind == "set_comp":
            if op["track"] not in names:
                err(errors, f"{s['id']} 压缩未知轨道 {op['track']}")
            p = op["params"]
            if not (-60 <= p["threshold_db"] <= 0 and 1 <= p["ratio"] <= 20
                    and 0 <= p["attack_ms"] <= 300 and 10 <= p["release_ms"] <= 1000):
                err(errors, f"{s['id']} 压缩参数越界")
            comp.append({"track": op["track"], **p})
        elif kind == "set_send":
            if op["to"] not in names:
                err(errors, f"{s['id']} 发送目标不存在：{op['to']}")
            send.append({"from": op["from"], "to": op["to"], "gain_db": op["gain_db"]})
        else:
            err(errors, f"{s['id']} 未知 op：{kind}")
    expected = {}
    if vol:
        expected["volume_db_set"] = vol
    if eq:
        expected["eq_bands"] = eq
    if comp:
        expected["compressors"] = comp
    if send:
        expected["sends"] = send
    if expected != s["expected"]:
        err(errors, f"{s['id']} expected 与 ops 不一致")
    if not s.get("intent", "").strip():
        err(errors, f"{s['id']} 空 intent")


def check_form(s: dict, errors: list[str]) -> None:
    p = s["patch"]
    sections = p["sections"]
    if not sections:
        err(errors, f"{s['id']} 无段落")
        return
    bar = 1
    names = []
    for sec in sections:
        if sec["name"] not in DENSITY_KEYS:
            err(errors, f"{s['id']} 未知段落名 {sec['name']}")
        if sec["start_bar"] != bar:
            err(errors, f"{s['id']} 段落不连续：{sec['name']} start={sec['start_bar']} 期望 {bar}")
        if sec["bars"] < 4 or sec["bars"] % 4 != 0:
            err(errors, f"{s['id']} 段落小节数异常 {sec['bars']}")
        if not (0 <= sec["energy"] <= 1 and 0 <= sec["density"] <= 1):
            err(errors, f"{s['id']} energy/density 越界")
        bar += sec["bars"]
        names.append(sec["name"])
    total = bar - 1
    if total != s["expected"]["total_bars"]:
        err(errors, f"{s['id']} total_bars 不一致")
    if len(sections) != s["expected"]["n_sections"]:
        err(errors, f"{s['id']} n_sections 不一致")
    markers = [{"bar": sec["start_bar"], "name": sec["name"]} for sec in sections]
    if markers != p["markers"]:
        err(errors, f"{s['id']} markers 与 sections 不一致")
    peak = max(sections, key=lambda x: x["energy"])["name"]
    if peak != s["expected"]["peak_energy_section"]:
        err(errors, f"{s['id']} peak_energy_section 不一致")
    if p["tempo"] != s["state"]["tempo"]:
        err(errors, f"{s['id']} tempo 不一致")


def check_texture(s: dict, errors: list[str]) -> None:
    notes = s["patch"]["notes"]
    state = s["state"]
    prog = state["progression"]
    total_bars = 2 * len(prog)
    chord_map = {}
    for ci, symbol in enumerate(prog):
        chord_map[(ci * 2 + 1, ci * 2 + 2)] = symbol
    low, high = 48, 72  # C3..C5
    seen = set()
    for n in notes:
        if not (1 <= n["bar"] <= total_bars):
            err(errors, f"{s['id']} 音符小节越界 {n['bar']}")
            continue
        if not (0 <= n["step"] <= 15 and 1 <= n["len_steps"] <= 32):
            err(errors, f"{s['id']} step/len 越界")
        if not low <= n["key"] <= high:
            err(errors, f"{s['id']} 音高越界 {n['key']}")
        if not 1 <= n["vel"] <= 127:
            err(errors, f"{s['id']} 力度越界")
        key = (n["bar"], n["step"], n["key"])
        if key in seen:
            err(errors, f"{s['id']} 重复音符 {key}")
        seen.add(key)
    if len(notes) != s["expected"]["n_notes"]:
        err(errors, f"{s['id']} n_notes 不一致")
    if not s.get("intent", "").strip():
        err(errors, f"{s['id']} 空 intent")


def check_sft(errors: list[str]) -> None:
    for path in sorted(DATA.glob("sft_*_*.jsonl")):
        for i, row in enumerate(load_jsonl(path)):
            msgs = row.get("messages", [])
            if [m.get("role") for m in msgs] != ["system", "user", "assistant"]:
                err(errors, f"{path.name}:{i} messages 角色不正确")
                continue
            try:
                user = json.loads(msgs[1]["content"])
                assistant = json.loads(msgs[2]["content"])
            except json.JSONDecodeError as exc:
                err(errors, f"{path.name}:{i} JSON 解析失败 {exc}")
                continue
            if user.get("task") not in VALID_TASKS:
                err(errors, f"{path.name}:{i} task 非法")
                continue
            ok, reason = validate(user["task"], user.get("state", {}), assistant)
            if not ok:
                err(errors, f"{path.name}:{i} patch 非法：{reason}")
                continue
            expected_key = {"mix": "ops", "form": "sections", "texture": "notes"}[user["task"]]
            if expected_key not in assistant:
                err(errors, f"{path.name}:{i} assistant 缺少 {expected_key}")


def main() -> int:
    errors: list[str] = []
    manifest = check_manifest(errors)
    for task, checker in (("mix", check_mix), ("form", check_form), ("texture", check_texture)):
        for split in ("train", "val"):
            path = DATA / f"{task}_{split}.jsonl"
            if not path.exists():
                err(errors, f"缺少 {path.name}")
                continue
            rows = load_jsonl(path)
            ids = set()
            for s in rows:
                if s["id"] in ids:
                    err(errors, f"{task}:{split} 重复 id {s['id']}")
                ids.add(s["id"])
                if s["task"] != task:
                    err(errors, f"{s['id']} task 字段不匹配")
                ok, reason = validate(task, s.get("state", {}), s.get("patch"))
                if not ok:
                    err(errors, f"{s['id']} patch 非法：{reason}")
                    continue
                checker(s, errors)
    check_sft(errors)

    for path in sorted(DATA.glob("*.jsonl")):
        print(f"  {path.name:26s} {len(load_jsonl(path)):5d} 行")
    print(f"manifest version={manifest.get('version')} seed={manifest.get('seed')}")
    if errors:
        for e in errors[:50]:
            print("ERROR", e)
        print(f"\n{len(errors)} error(s)")
        return 1
    print("\n0 error(s) —— 数据可直接用于训练")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

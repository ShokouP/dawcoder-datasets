#!/usr/bin/env python3
"""DAWcoder 合成训练集生成器（CC0-1.0）。

生成三类**可直接用于 SFT** 的样本：
  mix     : 工程状态 + 制作意图 -> 混音参数补丁（JSON ops）
  form    : 风格/时长约束 -> 曲式结构方案（段落/marker/密度）
  texture : 和弦进行 + 织体意图 -> MIDI 音符补丁

输出：
  synthetic/data/{task}_{split}.jsonl   结构化样本（含 state / intent / patch / expected）
  synthetic/data/sft_{split}.jsonl      chat 格式（system / user / assistant），可直接喂 SFT
  synthetic/data/manifest.json          计数与 sha256

用法：
  python synthetic/generate.py                # 默认 seed=20261107
  python synthetic/generate.py --seed 7       # 换随机种子
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

PPQ = 480
DATA_DIR = Path(__file__).resolve().parent / "data"
VERSION = "0.1.0"

SYSTEM_PROMPT = (
    "你是 DAWcoder，一个把音乐制作意图翻译成 DAW 工程参数补丁的助手。"
    "只输出一个 JSON 对象，不要输出解释、Markdown 或代码块。"
    "mix 任务输出 {\"ops\": [...]}，form 任务输出 {\"sections\": [...], \"markers\": [...]}，"
    "texture 任务输出 {\"notes\": [...]}。所有数值用工程单位（dB、ms、Hz、MIDI note）。"
)

# ---------------------------------------------------------------- mix 任务

GENRE_TRACKS = {
    "pop": [("Kick", "kick"), ("Snare", "snare"), ("Hats", "hats"), ("Bass", "bass"),
            ("Piano", "keys"), ("Pad", "pad"), ("Lead Vocal", "vocal"), ("Backing Vox", "vocal")],
    "rock": [("Kick", "kick"), ("Snare", "snare"), ("Hats", "hats"), ("Bass", "bass"),
             ("Rhythm Gtr", "gtr"), ("Lead Gtr", "gtr"), ("Lead Vocal", "vocal")],
    "hiphop": [("Kick", "kick"), ("808", "bass"), ("Snare", "snare"), ("Hats", "hats"),
               ("Keys", "keys"), ("Lead Vocal", "vocal")],
    "edm": [("Kick", "kick"), ("Clap", "snare"), ("Hats", "hats"), ("Bass", "bass"),
            ("Lead Synth", "keys"), ("Pad", "pad"), ("Vocal Chop", "vocal")],
    "ballad": [("Piano", "keys"), ("Strings", "pad"), ("Bass", "bass"), ("Kick", "kick"),
               ("Lead Vocal", "vocal"), ("Backing Vox", "vocal")],
}

BASE_GAIN = {"kick": -4.0, "snare": -6.0, "hats": -14.0, "bass": -6.0,
             "keys": -10.0, "pad": -16.0, "vocal": -8.0, "gtr": -12.0}
TRACK_CN = {"Lead Vocal": "主唱", "Backing Vox": "和声", "Vocal Chop": "人声切片",
            "Rhythm Gtr": "节奏吉他", "Lead Gtr": "主音吉他", "Lead Synth": "主音合成器",
            "Piano": "钢琴", "Keys": "键盘", "Pad": "铺底", "Strings": "弦乐",
            "Bass": "贝斯", "808": "808 贝斯", "Kick": "底鼓", "Snare": "军鼓",
            "Clap": "拍手", "Hats": "踩镲"}


def cn(name: str) -> str:
    return TRACK_CN.get(name, name)


def base_state(rng: random.Random, genre: str) -> dict:
    tracks = []
    for name, role in GENRE_TRACKS[genre]:
        track = {
            "name": name,
            "role": role,
            "kind": "audio" if role in ("kick", "snare", "hats", "vocal", "gtr") else "midi",
            "volume_db": round(BASE_GAIN[role] + rng.uniform(-1.5, 1.5), 1),
            "pan": round(rng.uniform(-0.15, 0.15), 2),
            "fx": [],
            "sends": [],
        }
        if role in ("vocal", "keys", "pad", "gtr"):
            track["sends"].append({"to": "Plate Reverb", "gain_db": round(rng.uniform(-18, -10), 1)})
        if role == "vocal":
            track["fx"].append({"type": "comp", "params": {"threshold_db": -18, "ratio": 3.0,
                                                           "attack_ms": 5, "release_ms": 80}})
        tracks.append(track)
    return {
        "genre": genre,
        "tempo": rng.choice([90, 100, 110, 120, 124, 128]),
        "sample_rate": 48000,
        "tracks": tracks,
        "buses": [{"name": "Drum Bus", "volume_db": -2.0},
                  {"name": "Vocal Bus", "volume_db": -2.0},
                  {"name": "Plate Reverb", "volume_db": -6.0}],
        "master": {"target_lufs": rng.choice([-9.0, -8.0, -7.0]), "headroom_db": -6.0},
    }


def _track(state: dict, name: str) -> dict:
    for t in state["tracks"]:
        if t["name"] == name:
            return t
    raise KeyError(name)


ISSUES = [
    {"id": "vocal_buried", "role": "vocal", "intents": [
        "{t}被鼓盖住了，帮我推出来一点，别太亮",
        "{t}听不清，稍微提一点电平，顺手把中低频收一下",
        "人声太靠后了，往前提 1-2 dB",
    ]},
    {"id": "lowmid_mud", "role": "vocal", "intents": [
        "{t}听起来有点闷，300Hz 附近糊了，收一点",
        "中低频太浑，帮我在 250-400Hz 减一点",
    ]},
    {"id": "harsh", "role": "vocal", "intents": [
        "{t}有点刺耳，3k 附近收一下",
        "高频太扎，压一压 3-4k",
    ]},
    {"id": "dull", "role": "vocal", "intents": [
        "{t}高频发闷，加一点空气感",
        "整体太暗，10k 提一点",
    ]},
    {"id": "mask", "role": "bass", "intents": [
        "底鼓和贝斯打架，低频让一让",
        "贝斯太厚，把 60-100Hz 收一点",
    ]},
    {"id": "pad_loud", "role": "pad", "intents": [
        "铺底太满了，压下去一点",
        "Pad 抢了人声频段，收一点",
    ]},
    {"id": "drum_glue", "role": "kick", "intents": [
        "鼓组听起来散，总线加个 glue 压缩粘一下",
        "鼓总线做个胶水压缩",
    ]},
    {"id": "bus_quiet", "role": "kick", "intents": [
        "鼓总线偏小，提一点",
        "整体鼓有点弱，鼓总线推 1-2 dB",
    ]},
    {"id": "verb_wash", "role": "vocal", "intents": [
        "混响太湿了，收一点",
        "人声混响糊了，发送量降一点",
    ]},
    {"id": "boom", "role": "kick", "intents": [
        "底鼓太轰，50-70Hz 收一下",
    ]},
    {"id": "sibilance", "role": "vocal", "intents": [
        "齿音有点重，6-8k 收一下",
    ]},
]


def _make_issue(rng: random.Random, state: dict, issue: dict) -> tuple[list, dict]:
    """按问题类型生成修复 ops，并返回受影响的轨道。"""
    candidates = [t for t in state["tracks"] if t["role"] == issue["role"]]
    target = rng.choice(candidates)
    name = target["name"]
    ops: list[dict] = []
    iid = issue["id"]

    if iid == "vocal_buried":
        delta = round(rng.uniform(1.5, 3.0), 1)
        ops.append({"op": "set_track", "track": name, "fields": {"volume_db": round(rng.uniform(-9, -5), 1)}})
        if rng.random() < 0.6:
            other = rng.choice([t for t in state["tracks"] if t["role"] in ("pad", "keys", "gtr")])
            ops.append({"op": "set_eq", "track": other["name"], "band": 2, "type": "bell",
                        "freq": rng.choice([250, 315, 400]), "gain_db": round(rng.uniform(-2.0, -1.0), 1), "q": 1.0})
    elif iid == "lowmid_mud":
        ops.append({"op": "set_eq", "track": name, "band": 2, "type": "bell",
                    "freq": rng.choice([250, 315, 400]), "gain_db": round(rng.uniform(-4.0, -2.0), 1), "q": 1.2})
    elif iid == "harsh":
        ops.append({"op": "set_eq", "track": name, "band": 4, "type": "bell",
                    "freq": rng.choice([2500, 3150, 4000]), "gain_db": round(rng.uniform(-3.0, -1.5), 1), "q": 1.5})
    elif iid == "dull":
        ops.append({"op": "set_eq", "track": name, "band": 6, "type": "high_shelf",
                    "freq": rng.choice([8000, 10000, 12000]), "gain_db": round(rng.uniform(1.0, 2.5), 1), "q": 0.7})
    elif iid == "mask":
        ops.append({"op": "set_eq", "track": name, "band": 1, "type": "bell",
                    "freq": rng.choice([60, 80, 100]), "gain_db": round(rng.uniform(-3.0, -1.5), 1), "q": 0.8})
    elif iid == "pad_loud":
        ops.append({"op": "set_track", "track": name, "fields": {"volume_db": round(rng.uniform(-20, -14), 1)}})
    elif iid == "drum_glue":
        ops.append({"op": "set_comp", "track": "Drum Bus",
                    "params": {"threshold_db": rng.choice([-20, -18, -16]), "ratio": rng.choice([2.0, 2.5, 3.0]),
                               "attack_ms": rng.choice([20, 30, 40]), "release_ms": rng.choice([120, 150, 200])}})
    elif iid == "bus_quiet":
        ops.append({"op": "set_track", "track": "Drum Bus", "fields": {"volume_db": round(rng.uniform(-1.5, 0.5), 1)}})
    elif iid == "verb_wash":
        ops.append({"op": "set_send", "from": name, "to": "Plate Reverb", "gain_db": round(rng.uniform(-20, -14), 1)})
    elif iid == "boom":
        ops.append({"op": "set_eq", "track": name, "band": 1, "type": "bell",
                    "freq": rng.choice([50, 60, 70]), "gain_db": round(rng.uniform(-4.0, -2.0), 1), "q": 0.9})
    elif iid == "sibilance":
        ops.append({"op": "set_eq", "track": name, "band": 5, "type": "bell",
                    "freq": rng.choice([6500, 7000, 8000]), "gain_db": round(rng.uniform(-3.5, -1.5), 1), "q": 2.0})
    return ops, target


def derive_expected(ops: list[dict]) -> dict:
    """从 patch ops 推导期望变化（训练集与校验器共用同一套规则）。"""
    vol: dict[str, float] = {}
    eq: list[dict] = []
    comp: list[dict] = []
    send: list[dict] = []
    for op in ops:
        if op["op"] == "set_track":
            track = op["track"]
            if "volume_db" in op["fields"]:
                vol[track] = round(vol.get(track, 0.0) + op["fields"]["volume_db"], 1)
        elif op["op"] == "set_eq":
            eq.append({"track": op["track"], "freq": op["freq"], "gain_db": op["gain_db"]})
        elif op["op"] == "set_comp":
            comp.append({"track": op["track"], **op["params"]})
        elif op["op"] == "set_send":
            send.append({"from": op["from"], "to": op["to"], "gain_db": op["gain_db"]})
    out = {}
    if vol:
        out["volume_db_set"] = vol
    if eq:
        out["eq_bands"] = eq
    if comp:
        out["compressors"] = comp
    if send:
        out["sends"] = send
    return out


def gen_mix(rng: random.Random, idx: int) -> dict:
    genre = rng.choice(list(GENRE_TRACKS))
    state = base_state(rng, genre)
    roles = {t["role"] for t in state["tracks"]}
    available = [i for i in ISSUES if i["role"] in roles]
    issue = rng.choice(available)
    ops, target = _make_issue(rng, state, issue)
    intent = rng.choice(issue["intents"]).format(t=target["name"])
    return {
        "id": f"mix-{idx:06d}",
        "task": "mix",
        "meta": {"genre": genre, "issue": issue["id"], "n_ops": len(ops), "sample_index": idx},
        "state": state,
        "intent": intent,
        "patch": {"ops": ops},
        "expected": derive_expected(ops),
    }


# ---------------------------------------------------------------- form 任务

FORM_TEMPLATES = {
    "pop": {"tempo": (95, 128), "sections": [("Intro", 8), ("Verse", 16), ("Chorus", 16), ("Verse", 16),
                                             ("Chorus", 16), ("Bridge", 8), ("Chorus", 16), ("Outro", 8)]},
    "house": {"tempo": (120, 128), "sections": [("Intro", 16), ("Build", 16), ("Drop", 32), ("Break", 16),
                                                ("Drop", 32), ("Outro", 16)]},
    "hiphop": {"tempo": (80, 100), "sections": [("Intro", 8), ("Hook", 16), ("Verse", 16), ("Hook", 16),
                                                ("Verse", 16), ("Hook", 16), ("Outro", 8)]},
    "rock": {"tempo": (100, 160), "sections": [("Intro", 8), ("Verse", 16), ("Chorus", 16), ("Verse", 16),
                                               ("Chorus", 16), ("Solo", 16), ("Chorus", 16), ("Outro", 8)]},
    "ballad": {"tempo": (60, 90), "sections": [("Intro", 8), ("Verse", 16), ("Chorus", 16), ("Verse", 16),
                                               ("Chorus", 16), ("Bridge", 8), ("Chorus", 16), ("Outro", 8)]},
}
DENSITY = {"Intro": (0.15, 0.35), "Verse": (0.45, 0.65), "Chorus": (0.8, 0.95), "Hook": (0.8, 0.95),
           "Drop": (0.9, 1.0), "Build": (0.4, 0.85), "Break": (0.2, 0.45), "Bridge": (0.35, 0.6),
           "Solo": (0.65, 0.85), "Outro": (0.15, 0.35)}


def gen_form(rng: random.Random, idx: int) -> dict:
    genre = rng.choice(list(FORM_TEMPLATES))
    tpl = FORM_TEMPLATES[genre]
    tempo = rng.randrange(*tpl["tempo"], 2)
    sections = []
    bar = 1
    for name, base_bars in tpl["sections"]:
        bars = max(4, base_bars + rng.choice([-4, 0, 0, 0, 4]))
        lo, hi = DENSITY[name]
        sections.append({"name": name, "start_bar": bar, "bars": bars,
                         "energy": round(rng.uniform(lo, hi), 2),
                         "density": round(rng.uniform(lo, hi), 2)})
        bar += bars
    total_bars = bar - 1
    seconds = round(total_bars * 4 * 60 / tempo, 1)
    markers = [{"bar": s["start_bar"], "name": s["name"]} for s in sections]
    drops = [s for s in sections if s["name"] == "Drop"]
    intent = (
        f"做一首 {genre}，速度约 {tempo} BPM，总长约 {round(seconds)} 秒；"
        f"{'需要 drop 段落' if genre in ('house', 'edm') else '需要有记忆点的副歌'}，"
        f"段落之间能量要有对比，最后自然收尾。"
    )
    return {
        "id": f"form-{idx:06d}",
        "task": "form",
        "meta": {"genre": genre, "n_sections": len(sections), "sample_index": idx},
        "state": {"genre": genre, "tempo": tempo, "time_signature": "4/4", "target_seconds": round(seconds)},
        "intent": intent,
        "patch": {"tempo": tempo, "time_signature": "4/4", "sections": sections, "markers": markers},
        "expected": {
            "total_bars": total_bars,
            "n_sections": len(sections),
            "drop_bars": [s["bars"] for s in drops],
            "peak_energy_section": max(sections, key=lambda s: s["energy"])["name"],
            "duration_seconds": seconds,
        },
    }


# ---------------------------------------------------------------- texture 任务

CHORD_DEFS = {
    "C": [0, 4, 7], "Cmaj7": [0, 4, 7, 11], "Am": [9, 0, 4], "Am7": [9, 0, 4, 7],
    "F": [5, 9, 0], "G": [7, 11, 2], "Em": [4, 7, 11], "Dm": [2, 5, 9],
    "Cm": [0, 3, 7], "Cm7": [0, 3, 7, 10], "Ab": [8, 0, 3], "Eb": [3, 7, 10],
    "Bb": [10, 2, 5], "Ebmaj7": [3, 7, 10, 2],
}
PROGRESSIONS = {
    "pop": [["Cmaj7", "G", "Am7", "F"], ["C", "Am", "F", "G"], ["F", "G", "Em", "Am"]],
    "house": [["Am7", "F", "Cmaj7", "G"], ["Am", "F", "C", "G"]],
    "hiphop": [["Cm7", "Ab", "Eb", "Bb"], ["Cm", "Ab", "Eb", "Bb"]],
    "rock": [["C", "G", "Am", "F"], ["Em", "C", "G", "Dm"]],
    "ballad": [["Am7", "F", "Cmaj7", "G"], ["F", "C", "G", "Am"]],
}
STYLES = {
    "arp_16": {"grid": 1, "notes_per_bar": 16, "vel": (70, 95), "intent": "16 分音符上行琶音"},
    "broken_8": {"grid": 2, "notes_per_bar": 8, "vel": (60, 90), "intent": "8 分音符分解和弦"},
    "block": {"grid": 4, "notes_per_bar": 4, "vel": (70, 100), "intent": "柱式和弦"},
    "ostinato": {"grid": 2, "notes_per_bar": 8, "vel": (55, 85), "intent": "8 分音符固定音型"},
    "pad": {"grid": 16, "notes_per_bar": 2, "vel": (40, 65), "intent": "长音铺底"},
}


def _chord_notes(symbol: str, octave: int = 4) -> list[int]:
    notes = sorted(12 * octave + n for n in CHORD_DEFS[symbol])
    while min(notes) < 48:            # 保证落在 C3..C5（MIDI 48..72）
        notes = [n + 12 for n in notes]
    while max(notes) > 72:
        notes = [n - 12 for n in notes]
    return notes


def gen_texture(rng: random.Random, idx: int) -> dict:
    genre = rng.choice(list(PROGRESSIONS))
    prog = rng.choice(PROGRESSIONS[genre])
    style_name = rng.choice(list(STYLES))
    style = STYLES[style_name]
    bars_per_chord = 2
    notes: list[dict] = []
    for ci, symbol in enumerate(prog):
        chord_notes = _chord_notes(symbol, rng.choice([3, 4]))
        chord_notes = sorted(chord_notes)
        start_bar = ci * bars_per_chord + 1
        for bar in range(start_bar, start_bar + bars_per_chord):
            if style_name == "arp_16":
                seq = (chord_notes + chord_notes[1:-1]) * 2
                for step in range(16):
                    if rng.random() < 0.08:
                        continue
                    notes.append({"bar": bar, "step": step * 1, "key": seq[step % len(seq)],
                                  "len_steps": 1, "vel": rng.randint(*style["vel"])})
            elif style_name in ("broken_8", "ostinato"):
                seq = chord_notes if style_name == "ostinato" else chord_notes + chord_notes[::-1]
                for step in range(8):
                    notes.append({"bar": bar, "step": step * 2, "key": seq[step % len(seq)],
                                  "len_steps": 2, "vel": rng.randint(*style["vel"])})
            elif style_name == "block":
                for step in range(4):
                    for key in chord_notes:
                        notes.append({"bar": bar, "step": step * 4, "key": key,
                                      "len_steps": 4, "vel": rng.randint(*style["vel"])})
            elif style_name == "pad":
                for key in chord_notes:
                    notes.append({"bar": bar, "step": 0, "key": key, "len_steps": 16,
                                  "vel": rng.randint(*style["vel"])})
    lo, hi = "C3", "C5"
    intent = (f"{' - '.join(prog)} 进行，用 {style['intent']}，音域 {lo}–{hi}，"
              f"力度 {style['vel'][0]}–{style['vel'][1]}，不要出现和弦外音。")
    return {
        "id": f"texture-{idx:06d}",
        "task": "texture",
        "meta": {"genre": genre, "style": style_name, "progression": prog, "sample_index": idx},
        "state": {"tempo": rng.choice([90, 100, 110, 120, 124]), "time_signature": "4/4",
                  "progression": prog, "style": style_name, "range": [lo, hi]},
        "intent": intent,
        "patch": {"notes": notes},
        "expected": {
            "n_notes": len(notes),
            "chord_tone_ratio": 1.0,
            "range": [lo, hi],
        },
    }


# ---------------------------------------------------------------- chat 格式与输出

def to_chat(sample: dict) -> dict:
    user = json.dumps(
        {"task": sample["task"], "state": sample["state"], "intent": sample["intent"]},
        ensure_ascii=False, separators=(",", ":"),
    )
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": json.dumps(sample["patch"], ensure_ascii=False, separators=(",", ":"))},
        ]
    }


def write_jsonl(path: Path, rows: list[dict]) -> dict:
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    # 强制 LF：保证 Windows 生成的 sha256 与 Linux checkout 一致
    path.write_text(data, encoding="utf-8", newline="\n")
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
            "lines": len(rows)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261107)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    specs = [("mix", gen_mix, 1200), ("form", gen_form, 600), ("texture", gen_texture, 1800)]
    files: dict[str, dict] = {}
    for task, fn, total in specs:
        samples = [fn(rng, i) for i in range(total)]
        rng.shuffle(samples)
        cut = max(1, int(total * 0.1))
        train, val = samples[cut:], samples[:cut]
        for split, rows in (("train", train), ("val", val)):
            files[f"{task}_{split}.jsonl"] = write_jsonl(DATA_DIR / f"{task}_{split}.jsonl", rows)
            chat = [to_chat(s) for s in rows]
            files[f"sft_{task}_{split}.jsonl"] = write_jsonl(DATA_DIR / f"sft_{task}_{split}.jsonl", chat)

    manifest = {"version": VERSION, "created": "2026-11-07", "seed": args.seed,
                "license": "CC0-1.0", "generator": "synthetic/generate.py", "files": files,
                "counts": {k: v["lines"] for k, v in files.items()}}
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                            encoding="utf-8", newline="\n")
    total = sum(v["lines"] for k, v in files.items() if not k.startswith("sft_"))
    print(f"生成完成：{total} 条结构化样本，{sum(v['lines'] for k, v in files.items() if k.startswith('sft_'))} 条 chat 样本")
    for name, meta in files.items():
        print(f"  {name:24s} {meta['lines']:5d} 行  {meta['bytes']/1024:8.1f} KB")


if __name__ == "__main__":
    main()

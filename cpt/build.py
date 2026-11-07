#!/usr/bin/env python3
"""构建 CPT 语料（只使用 redistributable 源）。

  python cpt/build.py                     # 公开语料（T0/T1，可进仓库）
  python cpt/build.py --profile private   # 私有语料（额外读取本地 T2 原文，不入库）

输入：cpt/raw/*.jsonl（fetch.py 抓取）+ synthetic/data（自建 CC0）
输出：cpt/data/corpus_{train,val}.jsonl、manifest.json、stats.md、ATTRIBUTIONS.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CPT = ROOT / "cpt"
RAW = CPT / "raw"
OUT = CPT / "data"
SYN = ROOT / "synthetic" / "data"
MIN_CHARS = 300
MAX_CHARS = 120_000

TASK_DESC = [
    ("task-mix", "DAWcoder 混音任务说明",
     "混音任务：输入是 DAW 工程状态（轨道名、音量、声像、EQ、压缩、发送、总线）和一句制作意图，"
     "输出是 JSON patch，包含 set_track、set_eq、set_comp、set_send 四类操作。"
     "patch 必须是合法 JSON，数值使用工程单位：音量 dB、EQ 频率 Hz、增益 dB、Q 值、压缩阈值 dB、压缩比、起音与释放毫秒。"
     "混音原则：先做增益架构保证总线余量；人声与主奏优先；用 EQ 处理频段掩蔽而不是一味提升音量；"
     "压缩用于控制动态与增加粘合感；发送混响用于空间感而不是掩盖问题。"),
    ("task-form", "DAWcoder 曲式任务说明",
     "曲式任务：输入是风格、时长、能量要求，输出是 JSON 结构方案，包含 tempo、拍号、段落列表（名称、起始小节、小节数、"
     "能量 0-1、密度 0-1）和 marker 列表。段落之间必须连续、小节数为 4 的倍数，段落名称限定为 Intro、Verse、Chorus、"
     "Hook、Drop、Build、Break、Bridge、Solo、Outro。能量曲线要有对比：intro 低、build 递增、drop / chorus 最高、outro 收尾。"),
    ("task-texture", "DAWcoder 织体任务说明",
     "织体任务：输入是和弦进行、风格、音域与力度要求，输出是 JSON 音符补丁，单位为 1/16 音符网格："
     "bar 从 1 开始，step 为 0-15，len_steps 以 16 分音符计，key 为 MIDI 音高，vel 为 1-127。"
     "织体类型包括：arp_16（16 分音符琶音）、broken_8（8 分音符分解和弦）、block（柱式和弦）、ostinato（固定音型）、"
     "pad（长音铺底）。写织体时音符应落在和弦音上，音域集中在中音区，力度有自然起伏。"),
]


def load_sources() -> dict:
    with (CPT / "sources.yaml").open(encoding="utf-8") as fh:
        return {s["id"]: s for s in yaml.safe_load(fh)["sources"]}


def clean(text: str) -> str:
    text = re.sub(r"[ \t\u3000]+", " ", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def est_tokens(text: str) -> int:
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return int(cjk / 1.6 + (len(text) - cjk) / 4)


def describe_op(op: dict) -> str:
    kind = op["op"]
    if kind == "set_track":
        fields = op["fields"]
        parts = []
        if "volume_db" in fields:
            parts.append(f"音量设为 {fields['volume_db']} dB")
        if "pan" in fields:
            parts.append(f"声像设为 {fields['pan']}")
        return f"把 {op['track']} 的" + "、".join(parts)
    if kind == "set_eq":
        return f"在 {op['track']} 的 {op['freq']} Hz 做 {op['gain_db']} dB 的 {op['type']} 处理（Q={op['q']}）"
    if kind == "set_comp":
        p = op["params"]
        return (f"给 {op['track']} 加压缩：阈值 {p['threshold_db']} dB、比率 {p['ratio']}:1、"
                f"起音 {p['attack_ms']} ms、释放 {p['release_ms']} ms")
    if kind == "set_send":
        return f"把 {op['from']} 发送到 {op['to']} 的量改为 {op['gain_db']} dB"
    return json.dumps(op, ensure_ascii=False)


def handbook_docs(limit: int) -> list[dict]:
    docs: list[dict] = []
    for doc_id, title, text in TASK_DESC:
        docs.append({"doc_id": doc_id, "source": "dawcoder-ir-handbook", "title": title,
                     "license": "CC0-1.0", "tier": "T0", "url": "", "text": text})
    per_task = max(1, limit // 3)
    for task in ("mix", "form", "texture"):
        path = SYN / f"{task}_train.jsonl"
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if i >= per_task:
                break
            s = json.loads(line)
            if task == "mix":
                ops = "；".join(describe_op(op) for op in s["patch"]["ops"])
                text = (f"混音任务示例。工程风格：{s['state']['genre']}，速度 {s['state']['tempo']} BPM。"
                        f"用户意图：{s['intent']}。DAWcoder 输出 patch：{json.dumps(s['patch'], ensure_ascii=False)}。"
                        f"操作解释：{ops}。")
            elif task == "form":
                p = s["patch"]
                secs = "；".join(f"{x['name']} 从第 {x['start_bar']} 小节起共 {x['bars']} 小节，"
                                 f"能量 {x['energy']}，密度 {x['density']}" for x in p["sections"])
                text = (f"曲式任务示例。用户意图：{s['intent']}。DAWcoder 输出结构方案：tempo {p['tempo']}，"
                        f"拍号 {p['time_signature']}。段落安排：{secs}。")
            else:
                notes = s["patch"]["notes"]
                text = (f"织体任务示例。和弦进行：{' - '.join(s['state']['progression'])}，"
                        f"风格：{s['state']['style']}，共 {len(notes)} 个音符。"
                        f"用户意图：{s['intent']}。DAWcoder 输出音符补丁：{json.dumps(notes[:40], ensure_ascii=False)}"
                        + ("……" if len(notes) > 40 else "") + "。")
            docs.append({"doc_id": f"hb-{task}-{i:05d}", "source": "dawcoder-ir-handbook",
                         "title": f"DAWcoder {task} 示例 {i}", "license": "CC0-1.0", "tier": "T0",
                         "url": "", "text": text})
    return docs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["public", "private"], default="public")
    args = ap.parse_args()

    sources = load_sources()
    OUT.mkdir(parents=True, exist_ok=True)
    docs: list[dict] = []
    included: dict[str, dict] = {}

    for sid, src in sources.items():
        if not src.get("redistributable") and args.profile == "public":
            continue
        if src["fetch"].get("method") == "synthetic":
            rows = handbook_docs(int(src["fetch"].get("max_docs", 900)))
            for r in rows:
                r["source"] = sid
                r["license"] = src["license"]
                r["tier"] = src["tier"]
            docs.extend(rows)
            included[sid] = src
            continue
        raw = RAW / f"{sid}.jsonl"
        if not raw.exists():
            print(f"跳过 {sid}：无抓取数据（先跑 cpt/fetch.py）")
            continue
        n = 0
        for line in raw.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            text = clean(row.get("text", ""))
            if not (MIN_CHARS <= len(text) <= MAX_CHARS):
                continue
            row["text"] = text
            docs.append(row)
            n += 1
        included[sid] = src
        print(f"{sid}: {n} docs")

    # 去重：长度过滤 + 精确 hash + doc_id
    seen_text: set[str] = set()
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for d in docs:
        text = d.get("text", "")
        if not (MIN_CHARS <= len(text) <= MAX_CHARS):
            continue
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if h in seen_text or d["doc_id"] in seen_ids:
            continue
        seen_text.add(h)
        seen_ids.add(d["doc_id"])
        d["text_sha256"] = h
        unique.append(d)

    # 切分：按 hash 后两位 98/2
    train, val = [], []
    for d in unique:
        bucket = int(d["text_sha256"][:4], 16) % 100
        (val if bucket < 2 else train).append(d)

    def dump(name: str, rows: list[dict]) -> dict:
        path = OUT / name
        data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        path.write_text(data, encoding="utf-8", newline="\n")
        return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size, "lines": len(rows)}

    files = {"corpus_train.jsonl": dump("corpus_train.jsonl", train),
             "corpus_val.jsonl": dump("corpus_val.jsonl", val)}

    per_source: dict[str, dict] = {}
    for d in unique:
        st = per_source.setdefault(d["source"], {"docs": 0, "chars": 0, "tokens": 0})
        st["docs"] += 1
        st["chars"] += len(d["text"])
        st["tokens"] += est_tokens(d["text"])

    total_chars = sum(len(d["text"]) for d in unique)
    total_tokens = sum(est_tokens(d["text"]) for d in unique)
    manifest = {
        "corpus": "dawcoder-cpt-v0.1",
        "profile": args.profile,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "docs": len(unique),
        "chars": total_chars,
        "est_tokens": total_tokens,
        "train_docs": len(train),
        "val_docs": len(val),
        "sources": {sid: {"license": included[sid]["license"], "tier": included[sid]["tier"], **st}
                    for sid, st in per_source.items()},
        "files": files,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                      encoding="utf-8", newline="\n")

    stats = ["# CPT 语料统计", "",
             f"- 语料版本：`dawcoder-cpt-v0.1`（{args.profile}）",
             f"- 文档数：**{len(unique)}**（train {len(train)} / val {len(val)}）",
             f"- 字符数：**{total_chars:,}**；估算 tokens：**{total_tokens:,}**", "",
             "| 源 | 许可 | 文档 | 字符 | 估算 tokens |", "|---|---|---:|---:|---:|"]
    for sid, st in sorted(per_source.items()):
        src = included[sid]
        stats.append(f"| {sid} | {src['license']} | {st['docs']} | {st['chars']:,} | {st['tokens']:,} |")
    stats += ["", "> 估算方式：CJK 字符 / 1.6 + 其他字符 / 4。正式训练前用 Qwen 分词器实测。"]
    (OUT / "stats.md").write_text("\n".join(stats) + "\n", encoding="utf-8", newline="\n")

    attr = ["# 语料署名与许可（ATTRIBUTIONS）", "",
            "本语料由多个开放许可来源构成，逐源声明如下；语料记录中保留 `source` / `license` / `url` 字段。", ""]
    for sid, st in sorted(per_source.items()):
        src = included[sid]
        attr.append(f"## {src['title']}（`{sid}`）")
        attr.append(f"- 许可：**{src['license']}**（tier {src['tier']}）")
        attr.append(f"- 来源：{src['fetch'].get('url') or src['fetch'].get('method')}")
        if src["license"] == "CC-BY-SA-4.0":
            attr.append("- 要求：署名 + 相同方式共享；本语料按 CC BY-SA 4.0 分发。")
        if src["license"] == "MIT":
            attr.append("- 要求：保留版权与许可声明；语料中该源文本按 MIT 使用。")
        if src["license"] == "CC0-1.0":
            attr.append("- 要求：无（CC0）；本仓库自建内容。")
        attr.append("")
    (OUT / "ATTRIBUTIONS.md").write_text("\n".join(attr), encoding="utf-8", newline="\n")

    print(f"完成：{len(unique)} docs / {total_chars:,} chars / ~{total_tokens:,} tokens")
    print(f"输出：{OUT}")


if __name__ == "__main__":
    main()

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

DAW = ["equaliz", "compressor", "compression", "reverb", "delay", "plugin", "vst", "daw",
       "digital audio workstation", "midi", "automation", "lufs", "headroom", "clipping",
       "fader", "pan", "bus", "aux", "send", "return", "preamp", "audio interface", "sample rate",
       "bit depth", "stereo", "mono", "phase", "microphone", "monitor", "mixing", "mastering",
       "mix bus", "sidechain", "saturation", "limiter", "gate", "gain staging", "tracking",
       "recording session", "signal chain", "frequency response", "dynamic range"]
BOILER = ["project gutenberg", "gutenberg", "ebook", "produced by", "distributed proofreading",
          "creative commons", "attribution", "http://", "https://", "www.", "retrieved from",
          "categories:", "wikisource", "wikipedia"]


def stream(path, limit=None):
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit and i >= limit:
                break
            yield json.loads(line)


def analyze(path, limit=None, label=""):
    per_source = defaultdict(lambda: {"n": 0, "chars": 0, "daw": 0, "boil": 0, "zh": 0, "len": []})
    n = chars = daw_docs = 0
    for d in stream(path, limit):
        n += 1
        t = d.get("text", "")
        chars += len(t)
        sid = d.get("source", "?")
        st = per_source[sid]
        st["n"] += 1
        st["chars"] += len(t)
        st["len"].append(len(t))
        low = t.lower()
        if any(k in low for k in DAW):
            st["daw"] += 1
            daw_docs += 1
        if any(k in low for k in BOILER):
            st["boil"] += 1
        cjk = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
        if cjk / max(1, len(t)) > 0.3:
            st["zh"] += 1
    print(f"== {label} docs={n:,} chars={chars:,} ~tokens={chars/4:,.0f}")
    print(f"{'source':28s} {'docs':>8s} {'avg_len':>8s} {'DAW%':>6s} {'boiler%':>7s} {'zh%':>5s}")
    for sid, st in sorted(per_source.items()):
        ln = statistics.mean(st["len"]) if st["len"] else 0
        pct = lambda x: 100 * x / max(1, st["n"])
        print(f"{sid:28s} {st['n']:8d} {ln:8.0f} {pct(st['daw']):6.1f} {pct(st['boil']):7.1f} {pct(st['zh']):5.1f}")
    print(f"DAW 关键词（严格）覆盖：{100*daw_docs/max(1,n):.1f}% 文档")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    analyze(Path(a.path), a.limit, a.label or a.path)

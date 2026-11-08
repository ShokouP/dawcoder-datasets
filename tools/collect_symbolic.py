"""Download and prepare Groove MIDI and SALAMI annotations using CPU only.

Third-party originals and derived JSONL stay in ignored data/symbolic/.
These are performance/annotation records, not fabricated intent-to-patch pairs.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "symbolic"
LOCK = ROOT / "registry" / "symbolic.lock.json"
GROOVE_URL = "https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip"
GROOVE_SHA = "651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def download(url, dest, expected=None):
    if dest.exists() and (not expected or sha256(dest.read_bytes()) == expected):
        return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "DAWcoder-datasets/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        data = response.read(50_000_001)
    if len(data) > 50_000_000:
        raise ValueError("Archive exceeds the 50 MB limit")
    if expected and sha256(data) != expected:
        raise ValueError(f"Archive SHA-256 mismatch: {url}")
    dest.write_bytes(data)
    return data


def dump_rows(directory, name, rows):
    path = directory / name
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")
    return {"rows": len(rows), "sha256": sha256(path.read_bytes()), "bytes": path.stat().st_size}


def midi_hits(data):
    import mido
    midi = mido.MidiFile(file=io.BytesIO(data))
    tick, hits = 0, []
    for message in mido.merge_tracks(midi.tracks):
        tick += message.time
        if message.type == "note_on" and message.velocity > 0:
            hits.append([tick, message.note, message.velocity])
    return midi.ticks_per_beat, tick, hits


def groove():
    directory = OUT / "groove-midi"
    directory.mkdir(parents=True, exist_ok=True)
    data = download(GROOVE_URL, OUT / "downloads" / "groove-midionly.zip", GROOVE_SHA)
    records, windows, skipped = [], [], []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = next(name for name in archive.namelist() if name.endswith("/info.csv") or name == "info.csv")
        prefix = info[:-len("info.csv")]
        metadata = list(csv.DictReader(io.StringIO(archive.read(info).decode("utf-8-sig"))))
        # Prefer evaluation copies when exactly identical performances recur.
        priority = {"test": 0, "validation": 1, "train": 2}
        metadata.sort(key=lambda row: (priority[row["split"]], row["midi_filename"]))
        seen = set()
        for row in metadata:
            path = prefix + row["midi_filename"]
            raw = archive.read(path)
            ppq, total_ticks, hits = midi_hits(raw)
            signature = sha256(json.dumps([row["bpm"], ppq, hits], separators=(",", ":")).encode())
            if signature in seen:
                skipped.append({"file": row["midi_filename"], "reason": "duplicate-performance"})
                continue
            seen.add(signature)
            split = {"validation": "val", "train": "train", "test": "test"}[row["split"]]
            group = "groove:" + row["midi_filename"]
            record = {"dataset_id": "groove-midi", "task": "drum_performance", "group_key": group,
                      "provenance": [{"dataset_id": "groove-midi", "spdx": "CC-BY-4.0", "tier": "T1"}],
                      "split": split, "license": "CC-BY-4.0", "url": "https://magenta.tensorflow.org/datasets/groove",
                      "source_path": row["midi_filename"], "source_sha256": sha256(raw),
                      "metadata": row, "ticks_per_beat": ppq, "total_ticks": total_ticks, "hits": hits}
            records.append(record)
            if row["time_signature"] not in ("4-4", "4/4"):
                continue
            width = ppq * 8
            buckets = {}
            for tick, key, velocity in hits:
                start = tick // width * width
                if start + width <= total_ticks:
                    buckets.setdefault(start, []).append([tick - start, key, velocity])
            for start, window_hits in sorted(buckets.items()):
                windows.append({"dataset_id": "groove-midi", "task": "drum_pattern", "group_key": group,
                                "provenance": [{"dataset_id": "groove-midi", "spdx": "CC-BY-4.0", "tier": "T1"}],
                                "split": split, "license": "CC-BY-4.0", "source_sha256": sha256(raw),
                                "source_path": row["midi_filename"], "start_tick": start, "bars": 2,
                                "ticks_per_beat": ppq, "bpm": int(row["bpm"]), "style": row["style"],
                                "beat_type": row["beat_type"], "hits": window_hits})
    files = {}
    for split in ("train", "val", "test"):
        files[f"performances_{split}.jsonl"] = dump_rows(directory, f"performances_{split}.jsonl", [r for r in records if r["split"] == split])
        files[f"windows_{split}.jsonl"] = dump_rows(directory, f"windows_{split}.jsonl", [r for r in windows if r["split"] == split])
    attribution = ("Groove MIDI Dataset, Google LLC, CC BY 4.0.\n"
                   "Gillick, Roberts, Engel, Eck and Bamman, Learning to Groove with Inverse Sequence Transformations, ICML 2019.\n"
                   "https://magenta.tensorflow.org/datasets/groove\nhttps://creativecommons.org/licenses/by/4.0/\n"
                   "Changes: parsed MIDI note-on events, retained original ticks/pitches/velocities, excluded exact duplicate performances, and created complete two-bar windows.\n"
                   "Original official splits are retained; all windows from a performance stay together.\n"
                   "Drum pitches use Roland TD-11 mapping, not remapped to General MIDI.\n")
    (directory / "ATTRIBUTIONS.md").write_text(attribution, encoding="utf-8")
    result = {"url": GROOVE_URL, "archive_sha256": GROOVE_SHA, "license": "CC-BY-4.0", "input_performances": len(metadata),
              "performances": len(records), "hits": sum(len(r["hits"]) for r in records), "windows": len(windows),
              "split_policy": "official_performance_split", "files": files, "skipped": skipped}
    (directory / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"dataset": "groove-midi", **{k: result[k] for k in ("input_performances", "performances", "hits", "windows")}}, ensure_ascii=False), flush=True)
    return result


def salami(previous=None):
    directory = OUT / "salami-annotations"
    directory.mkdir(parents=True, exist_ok=True)
    repository = "DDMAL/salami-data-public"
    commit = (previous or {}).get("commit")
    if not commit:
        commit = subprocess.check_output(["git", "ls-remote", f"https://github.com/{repository}.git", "HEAD"], timeout=60).decode().split()[0]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid SALAMI revision")
    url = f"https://codeload.github.com/{repository}/tar.gz/{commit}"
    data = download(url, OUT / "downloads" / f"salami-{commit}.tar.gz", (previous or {}).get("archive_sha256"))
    records = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        readme = next(member for member in archive.getmembers() if member.name.endswith("/readme.md"))
        license_text = archive.extractfile(readme).read().decode("utf-8-sig")
        if "Creative Commons 0" not in license_text:
            raise ValueError("SALAMI license statement changed")
        (directory / "UPSTREAM-README.md").write_text(license_text, encoding="utf-8")
        for member in sorted(archive.getmembers(), key=lambda m: m.name):
            match = re.search(r"/annotations/(\d+)/parsed/textfile(\d+)_functions\.txt$", member.name)
            if not member.isfile() or not match:
                continue
            song, annotator = match.groups()
            text = archive.extractfile(member).read().decode("utf-8-sig")
            boundaries = []
            for line in text.splitlines():
                if not line.strip():
                    continue
                when, label = line.split(maxsplit=1)
                boundaries.append({"time_seconds": float(when), "label": label.strip()})
            if not boundaries or any(a["time_seconds"] > b["time_seconds"] for a, b in zip(boundaries, boundaries[1:])):
                raise ValueError(f"Invalid SALAMI timeline: {member.name}")
            bucket = int(sha256(("salami:" + song).encode())[:8], 16) % 100
            split = "test" if bucket < 5 else "val" if bucket < 10 else "train"
            path = member.name.split("/", 1)[1]
            records.append({"dataset_id": "salami-annotations", "task": "section_annotations", "song_id": song,
                            "provenance": [{"dataset_id": "salami-annotations", "spdx": "CC0-1.0", "tier": "T0"}],
                            "annotator": annotator, "group_key": "salami:" + song, "split": split, "license": "CC0-1.0",
                            "revision": commit, "source_path": path, "source_sha256": sha256(text.encode()),
                            "url": f"https://github.com/{repository}/blob/{commit}/{path}", "boundaries": boundaries})
    if not records:
        raise ValueError("No SALAMI annotations found")
    files = {f"sections_{split}.jsonl": dump_rows(directory, f"sections_{split}.jsonl", [r for r in records if r["split"] == split]) for split in ("train", "val", "test")}
    attribution = ("SALAMI Data Set 2.0, CC0 1.0. DDMAL / SALAMI annotators.\n"
                   "Smith, Burgoyne, Fujinaga, De Roure and Downie, Design and creation of a large-scale database of structural annotations, ISMIR 2011.\n"
                   "https://github.com/DDMAL/salami-data-public\n"
                   "Changes: parsed functional boundaries; deterministic 90/5/5 split by song ID.\n"
                   "No audio is included; times remain seconds, not inferred bar or tempo labels.\n")
    (directory / "ATTRIBUTIONS.md").write_text(attribution, encoding="utf-8")
    result = {"url": url, "commit": commit, "archive_sha256": sha256(data), "license": "CC0-1.0",
              "songs": len({r["song_id"] for r in records}), "annotations": len(records),
              "boundaries": sum(len(r["boundaries"]) for r in records), "split_policy": "song_sha256_90_5_5", "files": files}
    (directory / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"dataset": "salami-annotations", **{k: result[k] for k in ("songs", "annotations", "boundaries")}}), flush=True)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("all", "groove-midi", "salami-annotations"), default="all")
    args = ap.parse_args()
    snapshot = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {"version": 1, "sources": {}}
    for sid, collect in (("groove-midi", groove), ("salami-annotations", lambda: salami(snapshot["sources"].get("salami-annotations")))):
        if args.source in ("all", sid):
            snapshot["sources"][sid] = collect()
            LOCK.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

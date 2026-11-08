"""Verify downloaded symbolic data, hashes, values, counts and split isolation."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    errors, splits, counts, identities = [], {}, Counter(), set()
    songs, hits, boundaries = set(), 0, 0
    for name, meta in manifest["files"].items():
        path = directory / name
        if not path.exists():
            errors.append(f"Missing file: {name}")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            errors.append(f"Hash mismatch: {name}")
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        if len(rows) != meta["rows"] or len(data) != meta["bytes"]:
            errors.append(f"Count/size mismatch: {name}")
        kind, split = name.rsplit("_", 1)
        split = split.removesuffix(".jsonl")
        for row in rows:
            group = row["group_key"]
            if row["split"] != split or (group in splits and splits[group] != split):
                errors.append(f"Cross-split group: {group}")
            splits[group] = split
            if row["license"] != manifest["license"] or not row.get("source_sha256"):
                errors.append(f"Missing/mismatched provenance: {group}")
            identity = kind, group, row.get("start_tick", row.get("annotator", ""))
            if identity in identities:
                errors.append(f"Duplicate record: {identity}")
            identities.add(identity)
            counts[kind] += 1
            if kind in ("performances", "windows"):
                notes = row["hits"]
                end = row["total_ticks"] if kind == "performances" else row["ticks_per_beat"] * 8
                if not notes or any(len(note) != 3 or any(type(x) is not int for x in note) or not (0 <= note[0] <= end and 0 <= note[1] <= 127 and 1 <= note[2] <= 127) for note in notes):
                    errors.append(f"Invalid drum hits: {group}")
                if any(a[0] > b[0] for a, b in zip(notes, notes[1:])):
                    errors.append(f"Unsorted drum hits: {group}")
                if kind == "performances":
                    hits += len(notes)
            elif kind == "sections":
                songs.add(row["song_id"])
                values = row["boundaries"]
                boundaries += len(values)
                if any(not isinstance(v["label"], str) or not math.isfinite(v["time_seconds"]) or v["time_seconds"] < 0 for v in values) or any(a["time_seconds"] > b["time_seconds"] for a, b in zip(values, values[1:])):
                    errors.append(f"Invalid section boundaries: {group}")
    if "performances" in manifest and (counts["performances"] != manifest["performances"] or counts["windows"] != manifest["windows"] or hits != manifest["hits"]):
        errors.append("Groove manifest totals mismatch")
    if "annotations" in manifest and (counts["sections"] != manifest["annotations"] or len(songs) != manifest["songs"] or boundaries != manifest["boundaries"]):
        errors.append("SALAMI manifest totals mismatch")
    return errors, dict(counts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "symbolic")
    args = ap.parse_args()
    errors = []
    for dataset in ("groove-midi", "salami-annotations"):
        found, counts = check(args.data / dataset)
        errors.extend(found)
        print(f"{dataset}: {counts}, {len(found)} error(s)")
    for error in errors[:30]:
        print("ERROR", error)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())

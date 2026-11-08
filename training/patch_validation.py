"""Validate the supported DAWcoder JSON contract; does not judge audio quality."""
from __future__ import annotations

import math
import re

TASKS = ("mix", "form", "texture")
SECTION_NAMES = {"Intro", "Verse", "Chorus", "Hook", "Drop", "Build", "Break", "Bridge", "Solo", "Outro"}


def number(value, low, high):
    return type(value) in (int, float) and (type(value) is int or math.isfinite(value)) and low <= value <= high


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def keys(value, required, optional=()):
    return isinstance(value, dict) and set(required) <= value.keys() and value.keys() <= set(required) | set(optional)


def midi_key(value):
    if integer(value, 0, 127):
        return value
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d+)", value)
    if not match:
        return None
    note, accidental, octave = match.groups()
    key = (int(octave) + 1) * 12 + {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[note.upper()]
    key += {"": 0, "#": 1, "b": -1}[accidental]
    return key if 0 <= key <= 127 else None


def validate(task, state, patch):
    if not isinstance(state, dict):
        return False, "invalid-state"
    if not isinstance(patch, dict):
        return False, "not-object"
    if task == "mix":
        return validate_mix(state, patch)
    if task == "form":
        return validate_form(state, patch)
    if task == "texture":
        return validate_texture(state, patch)
    return False, "unknown-task"


def validate_mix(state, patch):
    if not keys(patch, {"ops"}) or not isinstance(patch["ops"], list) or not patch["ops"]:
        return False, "no-ops"
    tracks, buses = state.get("tracks", []), state.get("buses", [])
    if not isinstance(tracks, list) or not isinstance(buses, list):
        return False, "invalid-state"
    entries = tracks + buses
    if any(not isinstance(t, dict) or not isinstance(t.get("name"), str) for t in entries):
        return False, "invalid-state"
    names = {t["name"] for t in entries}
    if len(names) != len(entries):
        return False, "ambiguous-track"
    graph = {name: set() for name in names}
    for t in entries:
        for send in t.get("sends", []):
            if isinstance(send, dict) and isinstance(send.get("to"), str) and send["to"] in names:
                graph[t["name"]].add(send["to"])
    for op in patch["ops"]:
        if not isinstance(op, dict) or not isinstance(op.get("op"), str):
            return False, "bad-op"
        kind = op["op"]
        if kind not in {"set_track", "set_eq", "set_comp", "set_send"}:
            return False, "bad-op"
        if kind != "set_send" and (not isinstance(op.get("track"), str) or op["track"] not in names):
            return False, "unknown-track"
        if kind == "set_track":
            fields = op.get("fields")
            if not keys(op, {"op", "track", "fields"}) or not keys(fields, set(), {"volume_db", "pan"}) or not fields:
                return False, "bad-track-fields"
            if "volume_db" in fields and not number(fields["volume_db"], -60, 6):
                return False, "bad-volume"
            if "pan" in fields and not number(fields["pan"], -1, 1):
                return False, "bad-pan"
        elif kind == "set_eq":
            if not keys(op, {"op", "track", "band", "type", "freq", "gain_db", "q"}):
                return False, "bad-eq-fields"
            if not integer(op["band"], 1, 7) or op["type"] not in ("bell", "low_shelf", "high_shelf", "high_pass", "low_pass"):
                return False, "bad-eq-band"
            if not (number(op["freq"], 20, 20000) and number(op["gain_db"], -12, 12) and number(op["q"], 0.1, 10)):
                return False, "bad-eq-range"
        elif kind == "set_comp":
            params = op.get("params")
            if not keys(op, {"op", "track", "params"}) or not keys(params, {"threshold_db", "ratio", "attack_ms", "release_ms"}, {"makeup_db"}):
                return False, "bad-comp-fields"
            bounds = {"threshold_db": (-60, 0), "ratio": (1, 20), "attack_ms": (0, 300), "release_ms": (10, 1000), "makeup_db": (-24, 24)}
            if any(not number(value, *bounds[key]) for key, value in params.items()):
                return False, "bad-comp-range"
        else:
            if not keys(op, {"op", "from", "to", "gain_db"}):
                return False, "bad-send-fields"
            if any(not isinstance(op[key], str) or op[key] not in names for key in ("from", "to")):
                return False, "unknown-send-track"
            if not number(op["gain_db"], -60, 6):
                return False, "bad-send-gain"
            start, target = op["from"], op["to"]
            pending, seen = [target], set()
            while pending:
                node = pending.pop()
                if node == start:
                    return False, "send-cycle"
                if node not in seen:
                    seen.add(node)
                    pending.extend(graph[node])
            graph[start].add(target)
    return True, "ok"


def validate_form(state, patch):
    if not keys(patch, {"tempo", "time_signature", "sections", "markers"}):
        return False, "bad-form-fields"
    if not number(patch["tempo"], 20, 300) or ("tempo" in state and patch["tempo"] != state["tempo"]):
        return False, "bad-tempo"
    # The current IR defines four beats and sixteen steps per bar.
    if patch["time_signature"] != "4/4" or state.get("time_signature", "4/4") != "4/4":
        return False, "unsupported-meter"
    sections = patch["sections"]
    if not isinstance(sections, list) or not sections:
        return False, "no-sections"
    bar, markers = 1, []
    for section in sections:
        if not keys(section, {"name", "start_bar", "bars", "energy", "density"}):
            return False, "bad-section-fields"
        if not isinstance(section["name"], str) or section["name"] not in SECTION_NAMES:
            return False, "bad-section-name"
        if not integer(section["start_bar"], 1, 100000) or section["start_bar"] != bar or not integer(section["bars"], 4, 4096) or section["bars"] % 4:
            return False, "bad-section-grid"
        if not number(section["energy"], 0, 1) or not number(section["density"], 0, 1):
            return False, "bad-section-range"
        markers.append({"bar": bar, "name": section["name"]})
        bar += section["bars"]
    if not isinstance(patch["markers"], list) or any(not keys(m, {"bar", "name"}) or not integer(m["bar"], 1, 100000) for m in patch["markers"]) or patch["markers"] != markers:
        return False, "marker-mismatch"
    return True, "ok"


def validate_texture(state, patch):
    if not keys(patch, {"notes"}) or not isinstance(patch["notes"], list) or not patch["notes"]:
        return False, "no-notes"
    if state.get("time_signature", "4/4") != "4/4":
        return False, "unsupported-meter"
    progression = state.get("progression", [])
    if not isinstance(progression, list):
        return False, "invalid-progression"
    bars = state.get("bars", 2 * len(progression) if progression else 8)
    limits = state.get("range", ["C3", "C5"])
    if not integer(bars, 1, 4096) or not isinstance(limits, list) or len(limits) != 2:
        return False, "invalid-state"
    low, high = (midi_key(value) for value in limits)
    if low is None or high is None or low > high:
        return False, "invalid-range"
    seen = set()
    for note in patch["notes"]:
        if not keys(note, {"bar", "step", "key", "len_steps", "vel"}):
            return False, "bad-note-fields"
        if not integer(note["bar"], 1, bars):
            return False, "bad-bar"
        if not integer(note["step"], 0, 15) or not integer(note["len_steps"], 1, 32):
            return False, "bad-grid"
        if (note["bar"] - 1) * 16 + note["step"] + note["len_steps"] > bars * 16:
            return False, "note-past-end"
        if not integer(note["key"], low, high) or not integer(note["vel"], 1, 127):
            return False, "bad-note-range"
        identity = note["bar"], note["step"], note["key"]
        if identity in seen:
            return False, "duplicate-note"
        seen.add(identity)
    return True, "ok"

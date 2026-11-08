"""Training-only, schema-gated patch similarity; fixed evaluation is unchanged."""
import json
import math

try:
    from .patch_validation import validate
except ImportError:
    from patch_validation import validate


def close(a, b, scale):
    return max(0., 1. - abs(float(a) - float(b)) / scale)


def value_score(key, a, b):
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return float(a == b)
    if key == "freq":
        return max(0., 1. - abs(math.log2(max(a, 1) / max(b, 1))) / 2.)
    scales = {"volume_db": 6., "gain_db": 6., "pan": .5, "threshold_db": 12.,
              "ratio": 6., "attack_ms": 50., "release_ms": 300., "q": 3.,
              "tempo": 20., "bars": 16., "start_bar": 16., "energy": .5, "density": .5,
              "len_steps": 8., "vel": 64.}
    return close(a, b, scales.get(key, 1.))


def fields_score(gold, pred):
    if not gold:
        return float(not pred)
    quality = 0.
    for key, value in gold.items():
        if key not in pred:
            continue
        if isinstance(value, dict):
            quality += fields_score(value, pred[key]) if isinstance(pred[key], dict) else 0.
        else:
            quality += value_score(key, value, pred[key])
    return quality / max(len(gold), len(pred), 1)


def operation_identity(op):
    if op["op"] == "set_send":
        return op["op"], op["from"], op["to"]
    if op["op"] == "set_eq":
        return op["op"], op["track"], op["band"], op["type"]
    return op["op"], op["track"]


def mix_score(gold, pred):
    remaining = list(pred["ops"])
    quality = 0.
    for op in gold["ops"]:
        matches = [(fields_score(op, item), index) for index, item in enumerate(remaining)
                   if operation_identity(item) == operation_identity(op)]
        if matches:
            score, index = max(matches)
            quality += score
            remaining.pop(index)
    # Symmetric denominator penalizes both omissions and gratuitous operations.
    return 2 * quality / max(1, len(gold["ops"]) + len(pred["ops"]))


def form_score(gold, pred):
    sections = sum(fields_score(a, b) for a, b in zip(gold["sections"], pred["sections"]))
    sections /= max(len(gold["sections"]), len(pred["sections"]), 1)
    return .9 * sections + .1 * value_score("tempo", gold["tempo"], pred["tempo"])


def texture_score(gold, pred):
    g = {(n["bar"], n["step"], n["key"]): n for n in gold["notes"]}
    p = {(n["bar"], n["step"], n["key"]): n for n in pred["notes"]}
    quality = 0.
    for key in g.keys() & p.keys():
        quality += .8 + .15 * value_score("len_steps", g[key]["len_steps"], p[key]["len_steps"]) + .05 * value_score("vel", g[key]["vel"], p[key]["vel"])
    return 2 * quality / max(len(g) + len(p), 1)


def score(task, state, gold, output):
    try:
        pred = json.loads(output)
    except (ValueError, TypeError):
        return {"reward": 0., "valid": False, "reason": "invalid-json", "similarity": 0.}
    valid, reason = validate(task, state, pred)
    if not valid:
        return {"reward": .05, "valid": False, "reason": reason, "similarity": 0.}
    similarity = {"mix": mix_score, "form": form_score, "texture": texture_score}[task](gold, pred)
    similarity = max(0., min(1., similarity))
    return {"reward": .3 + .7 * similarity, "valid": True, "reason": "ok", "similarity": similarity}

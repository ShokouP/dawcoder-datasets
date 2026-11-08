"""CPU-only audit of existing DAWcoder artifacts; never loads model weights.

The optional tokenizer is local-only. Safetensors are hashed as bytes, without
importing torch or deserializing tensors. External scripts are read, not run;
only the reviewed, pure-Python reward module is imported for counterexamples.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import importlib.metadata
import json
import math
import os
from pathlib import Path
import struct
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
from patch_validation import validate


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tensor_hashes(path):
    """Hash tensor payloads separately from safetensors metadata/order."""
    result = {}
    with path.open("rb") as stream:
        header_size = struct.unpack("<Q", stream.read(8))[0]
        header = json.loads(stream.read(header_size))
        for name, item in header.items():
            if name == "__metadata__":
                continue
            start, end = item["data_offsets"]
            stream.seek(8 + header_size + start)
            digest, left = hashlib.sha256(), end - start
            while left:
                block = stream.read(min(left, 1024 * 1024))
                if not block:
                    raise ValueError(f"Truncated tensor: {path}: {name}")
                digest.update(block)
                left -= len(block)
            result[name] = (item["dtype"], item["shape"], digest.hexdigest())
    return result


def quantiles(values):
    vals = sorted(values)
    return {name: vals[max(0, math.ceil(q * len(vals)) - 1)]
            for name, q in (("p50", .5), ("p95", .95), ("p99", .99), ("max", 1))}


def reference_precision_probe(base_file, ref_file):
    """Check whether reference differences are exactly an FP32->BF16->FP32 cast."""
    import numpy as np

    def mapped(path):
        with path.open("rb") as stream:
            size = struct.unpack("<Q", stream.read(8))[0]
            header = json.loads(stream.read(size))
        return header, np.memmap(path, mode="r", dtype=np.uint8, offset=8 + size)

    base, base_data = mapped(base_file)
    ref, ref_data = mapped(ref_file)
    matched = total = 0
    for key, value in base.items():
        if key == "__metadata__":
            continue
        if value["dtype"] != "F32" or ref[key]["dtype"] != "F32":
            raise ValueError("Precision probe requires F32 tensors")
        start, end = value["data_offsets"]
        src = base_data[start:end].view("<u4")
        start, end = ref[key]["data_offsets"]
        dst = ref_data[start:end].view("<u4")
        rounded = (src + np.uint32(0x7fff) + ((src >> 16) & 1)) & np.uint32(0xffff0000)
        matched += int(np.array_equal(rounded, dst))
        total += 1
    return {"reference_tensors": total, "equal_to_sft_after_bfloat16_roundtrip": matched,
            "cpu_only": True}


def ids(value):
    if hasattr(value, "ids"):
        return list(value.ids)
    if hasattr(value, "keys"):
        value = value["input_ids"]
    return list(value)


def length_audit(sft, pairs, tokenizer_dir):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(tokenizer_dir, local_files_only=True, trust_remote_code=False)
    prompt_cache = {}

    def prompt(row):
        key = (row.get("system", ""), row["instruction"])
        if key not in prompt_cache:
            msgs = [{"role": "system", "content": key[0]}, {"role": "user", "content": key[1]}]
            prompt_cache[key] = ids(tok.apply_chat_template(msgs, tokenize=True,
                                   add_generation_prompt=True, enable_thinking=False))
        return prompt_cache[key]

    result, counts, lens = {}, defaultdict(Counter), defaultdict(lambda: defaultdict(list))
    for row in sft:
        task, p = row["task"], prompt(row)
        msgs = [{"role": "system", "content": row["system"]},
                {"role": "user", "content": row["instruction"]},
                {"role": "assistant", "content": row["output"]}]
        full = ids(tok.apply_chat_template(msgs, tokenize=True, add_generation_prompt=False,
                                          enable_thinking=False))
        completion = len(full) - len(p)
        lens[task]["prompt"].append(len(p))
        lens[task]["completion"].append(completion)
        lens[task]["full"].append(len(full))
        counts[task]["n"] += 1
        for seq in (1536, 2048, 4096, 8192):
            counts[task][f"sft_truncated_at_{seq}"] += len(full) > seq
            counts[task][f"no_target_at_{seq}"] += len(p) >= seq
        counts[task]["dpo_prompt_truncated_at_512"] += len(p) > 512
    for task in counts:
        result[task] = {**counts[task], "lengths": {k: quantiles(v) for k, v in lens[task].items()}}
    dpo = defaultdict(Counter)
    for row in pairs:
        task, p = row["task"], prompt(row)
        dpo[task]["n"] += 1
        dpo[task]["prompt_truncated"] += len(p) > 512
        prefix = p[:512]
        comps = {k: tok(row[k], add_special_tokens=False)["input_ids"] + [tok.eos_token_id]
                 for k in ("chosen", "rejected")}
        for key, comp in comps.items():
            dpo[task][f"{key}_truncated"] += len(prefix) + len(comp) > 1024
        dpo[task]["identical_after_truncation"] += (
            (prefix + comps["chosen"])[:1024] == (prefix + comps["rejected"])[:1024])
    return {"sft": result, "dpo_seq1024": dict(dpo)}


def reward_probes(sft, reward_path):
    spec = importlib.util.spec_from_file_location("audited_legacy_reward", reward_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = {}
    for row in sft:
        task = row["task"]
        instruction = json.loads(row["instruction"])
        gold = json.loads(row["output"])
        changed = json.loads(row["output"])
        if task == "mix":
            op = changed["ops"][0]
            kind = op["op"]
            if kind == "set_eq":
                op["freq"] = 20000 if op["freq"] < 10000 else 20
                op["gain_db"] = -op["gain_db"] or 6
            elif kind == "set_comp":
                op["params"]["ratio"] = 20 if op["params"]["ratio"] < 10 else 1
            elif kind == "set_send":
                op["gain_db"] = -60 if op["gain_db"] > -40 else 0
            else:
                continue
        elif task == "texture":
            kind = "texture_velocity"
            for note in changed["notes"]:
                note["vel"] = 1 if note["vel"] > 64 else 127
        else:
            kind = "form_energy"
            for section in changed["sections"]:
                section["energy"] = 1 - section["energy"]
        if kind in found or changed == gold:
            continue
        ok, why = validate(task, instruction.get("state", {}), changed)
        if not ok:
            continue
        found[kind] = {"valid": ok, "reason": why,
                       "gold_reward": module.reward(task, instruction, instruction.get("state", {}),
                                                     gold, json.dumps(gold))["reward"],
                       "changed_reward": module.reward(task, instruction, instruction.get("state", {}),
                                                        gold, json.dumps(changed))["reward"],
                       "gold_first": (gold.get("ops") or gold.get("notes") or gold.get("sections"))[0],
                       "changed_first": (changed.get("ops") or changed.get("notes") or changed.get("sections"))[0]}
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-root", type=Path, default=Path(r"D:\train"))
    ap.add_argument("--tokenizer", type=Path)
    ap.add_argument("--reference-precision", action="store_true", help="requires numpy; CPU byte comparison")
    ap.add_argument("--out", type=Path, default=ROOT / "training/posttrain-audit.json")
    args = ap.parse_args()
    tr = args.train_root
    sources = [tr / "scripts" / name for name in (
        "train_dpo_dawcoder.py", "grpo_train_dawcoder.py", "lib_dawcoder_reward.py", "train_sft.py")]
    train_file = ROOT / "training/data/dawcoder_sft_train.jsonl"
    val_file = ROOT / "training/data/dawcoder_sft_val.jsonl"
    pair_file = tr / "data/dpo-dawcoder/dpo_train.jsonl"
    sft, val, pairs = rows(train_file), rows(val_file), rows(pair_file)
    extras = [tr / "runs" / name for name in ("dawcoder_dpo.log", "dawcoder_grpo.log", "dawcoder_grpo_v2.log")]
    if args.tokenizer:
        extras.extend(p for p in args.tokenizer.iterdir() if p.is_file() and
                      ("token" in p.name or "template" in p.name or p.name == "config.json"))
    packages = {}
    for package in ("torch", "peft", "transformers", "trl", "numpy"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "cpu_only": True,
              "model_loaded": False, "gpu_training_started": False,
              "packages": packages,
              "input_sha256": {str(p): sha(p) for p in sources + [train_file, val_file, pair_file] + extras}}
    base_file = tr / "models/dawcoder_sft_v1/adapter_model.safetensors"
    base = tensor_hashes(base_file)
    weights = {}
    for label, rel in (("dpo_policy", "dpo_dawcoder_v1/policy"),
                       ("dpo_reference", "dpo_dawcoder_v1/ref"),
                       ("grpo_v1_policy", "grpo_dawcoder_v1/policy"),
                       ("grpo_v2_policy", "grpo_dawcoder_v2/policy")):
        file = tr / "models" / rel / "adapter_model.safetensors"
        current = tensor_hashes(file)
        common = base.keys() & current.keys()
        weights[label] = {"path": str(file), "sha256": sha(file), "tensors": len(current),
                          "changed_vs_sft": sum(base[k] != current[k] for k in common),
                          "missing_keys": len(base.keys() - current.keys()),
                          "extra_keys": len(current.keys() - base.keys())}
    report["weights"] = {"sft_sha256": sha(base_file), "comparisons": weights}
    if args.reference_precision:
        report["reference_precision_probe"] = reference_precision_probe(
            base_file, tr / "models/dpo_dawcoder_v1/ref/adapter_model.safetensors")
    stats = defaultdict(Counter)
    for row in pairs:
        task = row["task"]
        state = json.loads(row["instruction"])["state"]
        chosen, rejected = json.loads(row["chosen"]), json.loads(row["rejected"])
        stats[task]["n"] += 1
        stats[task]["identical_pairs"] += chosen == rejected
        stats[task]["chosen_valid"] += validate(task, state, chosen)[0]
        stats[task]["rejected_valid"] += validate(task, state, rejected)[0]
    report["dpo_data"] = dict(stats)
    report["sft_exact_prompt_overlap_train_val"] = len(
        {r["instruction"] for r in sft} & {r["instruction"] for r in val})
    report["legacy_reward_counterexamples"] = reward_probes(sft, sources[2])
    if args.tokenizer:
        report["token_lengths"] = length_audit(sft, pairs, args.tokenizer)
    report["eval"] = {}
    for path in sorted((ROOT / "training").glob("eval-report-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        n = item["total"]
        failures = sum(x["reason"] == "request-error" for x in item["results"])
        valid_count = sum(x["valid"] for x in item["results"])
        report["eval"][path.name] = {"sha256": sha(path), "n": n, "request_errors": failures,
                                    "valid_count": valid_count, "end_to_end_valid_rate": valid_count / n,
                                    "conditional_valid_rate": valid_count / (n - failures) if n > failures else None,
                                    "quality_comparison_eligible": failures == 0}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "weights": report["weights"], "dpo_data": report["dpo_data"],
                      "token_lengths": report.get("token_lengths"), "eval": report["eval"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

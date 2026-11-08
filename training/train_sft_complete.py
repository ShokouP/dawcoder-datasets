"""DAWcoder complete-output SFT continuation, with bounded-memory exact CE.

Uses only the training file. Validation and model comparison belong to the
evaluation side. --prepare-only uses the local tokenizer without loading a model.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def token_ids(value):
    if hasattr(value, "ids"):
        return list(value.ids)
    if hasattr(value, "keys"):
        value = value["input_ids"]
    return list(value)


def encode(tok, row, max_length):
    messages = [{"role": "system", "content": row["system"]},
                {"role": "user", "content": row["instruction"]}]
    prefix = token_ids(tok.apply_chat_template(messages, tokenize=True,
                       add_generation_prompt=True, enable_thinking=False))
    full = token_ids(tok.apply_chat_template(messages + [{"role": "assistant", "content": row["output"]}],
                     tokenize=True, add_generation_prompt=False, enable_thinking=False))
    if full[:len(prefix)] != prefix:
        raise ValueError("Training/inference chat template prefix mismatch")
    if len(full) > max_length:
        raise ValueError(f"Complete example exceeds max length: {len(full)} > {max_length}; no truncation allowed")
    if len(full) <= len(prefix):
        raise ValueError("Example has no completion tokens")
    return {"task": row["task"], "ids": full, "prompt_length": len(prefix),
            "input_sha256": hashlib.sha256(row["instruction"].encode()).hexdigest()}


def chunked_cross_entropy(head, hidden, targets, chunk_size=128, recompute=True):
    """Exact token-mean CE; checkpoint the vocabulary projection per chunk."""
    import torch
    import torch.nn.functional as F
    from torch.utils.checkpoint import checkpoint

    if not len(targets):
        raise ValueError("No supervised targets")

    def block(h, y):
        return F.cross_entropy(head(h).float(), y, reduction="sum")

    total = hidden.new_zeros((), dtype=torch.float32)
    for start in range(0, len(targets), chunk_size):
        h, y = hidden[start:start + chunk_size], targets[start:start + chunk_size]
        part = checkpoint(block, h, y, use_reentrant=False) if recompute else block(h, y)
        total = total + part
    return total / len(targets)


def model_loss(model, feature, pad_token, chunk_size):
    import torch

    full = feature["ids"]
    padding = (-len(full)) % 64
    input_ids = torch.tensor([full + [pad_token] * padding], dtype=torch.long, device="cuda")
    attention = torch.tensor([[1] * len(full) + [0] * padding], dtype=torch.long, device="cuda")
    labels = torch.tensor([[-100] * feature["prompt_length"] + full[feature["prompt_length"]:]
                           + [-100] * padding], dtype=torch.long, device="cuda")
    core = model.get_base_model()
    hidden = core.model(input_ids=input_ids, attention_mask=attention, use_cache=False).last_hidden_state
    targets = labels[:, 1:].reshape(-1)
    valid = targets != -100
    states = hidden[:, :-1, :].reshape(-1, hidden.shape[-1])[valid]
    return chunked_cross_entropy(core.lm_head, states, targets[valid], chunk_size,
                                 recompute=model.training)


def balanced_schedule(features, total, seed):
    """Cycle tasks equally; shuffle independently and exhaust each before reuse."""
    rng = random.Random(seed)
    pools = {task: [] for task in ("mix", "form", "texture")}
    for index, feature in enumerate(features):
        pools[feature["task"]].append(index)
    if any(not pool for pool in pools.values()):
        raise ValueError("All three tasks must be present")
    for pool in pools.values():
        rng.shuffle(pool)
    cursors = Counter()
    schedule = []
    for index in range(total):
        task = ("mix", "form", "texture")[index % 3]
        pool = pools[task]
        if cursors[task] == len(pool):
            rng.shuffle(pool)
            cursors[task] = 0
        schedule.append(pool[cursors[task]])
        cursors[task] += 1
    return schedule


def idle_snapshot():
    response = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, check=True, timeout=15)
    lines = response.stdout.strip().splitlines()
    if len(lines) != 1:
        raise RuntimeError("This run expects exactly one GPU")
    memory, utilization = [int(value.strip()) for value in lines[0].split(",")]
    if memory > 1024 or utilization > 5:
        raise RuntimeError(f"GPU not idle: {memory} MiB, {utilization}%; no model loaded")
    return {"memory_mib": memory, "utilization_percent": utilization,
            "at": datetime.now(timezone.utc).isoformat()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=Path(r"D:\train\models\Qwen3.5-4B"))
    ap.add_argument("--adapter", type=Path, default=Path(r"D:\train\models\dawcoder_sft_v1"))
    ap.add_argument("--data", type=Path, default=ROOT / "training/data/dawcoder_sft_train.jsonl")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--max-length", type=int, default=4096)
    ap.add_argument("--chunk", type=int, default=128)
    ap.add_argument("--save-every", type=int, default=25)
    ap.add_argument("--seed", type=int, default=20261108)
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()
    if min(args.steps, args.accum, args.max_length, args.chunk, args.save_every) < 1:
        ap.error("Positive steps, accumulation, lengths and save interval required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    runtime_root = ROOT / "_tmp/posttrain/runtime-cache"
    for name, leaf in (("TRITON_CACHE_DIR", "triton"), ("TORCHINDUCTOR_CACHE_DIR", "inductor"),
                       ("TEMP", "temp"), ("TMP", "temp")):
        directory = runtime_root / leaf
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(directory)
    if args.prepare_only:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer, Qwen3_5ForCausalLM

    torch.set_num_threads(4)
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "adapter_model.safetensors").exists() or (args.output / "metrics.jsonl").exists():
        raise ValueError("Output already contains a run; select a new directory")
    tok = AutoTokenizer.from_pretrained(args.base, local_files_only=True, trust_remote_code=False)
    rows = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines() if line.strip()]
    system = (ROOT / "preview/system_prompt.txt").read_text(encoding="utf-8").strip()
    if any(row["system"] != system for row in rows):
        raise ValueError("SFT system prompt differs from deployment prompt")
    features = [encode(tok, row, args.max_length) for row in rows]
    schedule = balanced_schedule(features, args.steps * args.accum, args.seed)
    if args.prepare_only:
        selected = Counter(features[i]["task"] for i in schedule)
        print(json.dumps({"cpu_only": True, "examples": len(features), "max_length": max(len(f["ids"]) for f in features),
                          "scheduled": dict(selected), "truncated": 0, "system_prompt_matches": True}))
        return
    idle = [idle_snapshot()]
    time.sleep(5)
    idle.append(idle_snapshot())
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    manifest = {"started_at": datetime.now(timezone.utc).isoformat(),
                "args": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
                "idle_before_load": idle, "method": "SFT complete-output continuation, balanced tasks, exact chunked CE",
                "data_sha256": digest(args.data), "parent_adapter_sha256": digest(args.adapter / "adapter_model.safetensors"),
                "system_prompt_sha256": digest(ROOT / "preview/system_prompt.txt"), "script_sha256": digest(__file__),
                "packages": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft")},
                "training_rows": len(features), "max_observed_length": max(len(f["ids"]) for f in features),
                "runtime_cache": str(runtime_root),
                "schedule": [{"task": features[i]["task"], "input_sha256": features[i]["input_sha256"]} for i in schedule],
                "validation_file_read_by_trainer": False, "truncated_examples": 0}
    (args.output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Loading base and SFT adapter", flush=True)
    base = Qwen3_5ForCausalLM.from_pretrained(args.base, local_files_only=True,
                                            trust_remote_code=False, dtype=torch.bfloat16, device_map={"": 0})
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=True, local_files_only=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    model.train()
    trainable = [p for p in model.parameters() if p.requires_grad]
    if not trainable:
        raise RuntimeError("No trainable parameters")
    opt = torch.optim.AdamW(trainable, lr=args.lr, betas=(.9, .95), weight_decay=0)
    warmup = min(5, max(1, args.steps // 10))
    t0 = time.time()
    metrics_path = args.output / "metrics.jsonl"
    initial_probe = [p.detach().flatten()[:32].float().cpu().clone() for p in trainable]
    for step in range(1, args.steps + 1):
        scale = step / warmup if step <= warmup else .1 + .9 * .5 * (1 + math.cos(math.pi * (step - warmup) / max(1, args.steps - warmup)))
        for group in opt.param_groups:
            group["lr"] = args.lr * scale
        opt.zero_grad(set_to_none=True)
        losses = defaultdict(list)
        for index in schedule[(step - 1) * args.accum:step * args.accum]:
            feature = features[index]
            loss = model_loss(model, feature, tok.pad_token_id or tok.eos_token_id, args.chunk)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite loss")
            (loss / args.accum).backward()
            losses[feature["task"]].append(float(loss.detach()))
        grad_norm = torch.nn.utils.clip_grad_norm_(trainable, 1.)
        if not torch.isfinite(grad_norm) or float(grad_norm) == 0:
            raise RuntimeError("Non-finite or zero policy gradients")
        opt.step()
        changed_probe = sum(not torch.equal(old, param.detach().flatten()[:32].float().cpu())
                            for old, param in zip(initial_probe, trainable)) if step == 1 else None
        if step == 1 and not changed_probe:
            raise RuntimeError("Optimizer did not update adapter probe values")
        record = {"step": step, "lr": args.lr * scale,
                  "loss_by_task": {task: sum(vals) / len(vals) for task, vals in losses.items()},
                  "grad_norm": float(grad_norm), "elapsed_seconds": round(time.time() - t0, 2),
                  "allocated_gib": round(torch.cuda.memory_allocated() / 2**30, 3),
                  "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3)}
        if changed_probe is not None:
            record["changed_adapter_tensor_probes"] = changed_probe
        with metrics_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)
        if step % args.save_every == 0:
            checkpoint_dir = args.output / f"checkpoint-{step}"
            model.save_pretrained(checkpoint_dir)
            torch.save({"step": step, "optimizer": opt.state_dict(), "torch_rng": torch.get_rng_state(),
                        "cuda_rng": torch.cuda.get_rng_state(), "python_rng": random.getstate()}, checkpoint_dir / "optimizer_state.pt")
    model.save_pretrained(args.output)
    manifest.update({"finished_at": datetime.now(timezone.utc).isoformat(), "completed_steps": args.steps,
                     "adapter_sha256": digest(args.output / "adapter_model.safetensors"),
                     "elapsed_seconds": round(time.time() - t0, 2)})
    (args.output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SAVED " + str(args.output), flush=True)


if __name__ == "__main__":
    main()

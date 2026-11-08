"""Small, auditable single-GPU GRPO + SFT replay experiment from SFT v2.

One question -> G independently sampled completions -> within-question advantages.
Uses token-level clipped loss / k3 KL, frozen reference, and full-output replay.
No fixed validation data is read. Evaluation protocol and scorer are untouched.
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
import shutil
import subprocess
import time

from grpo_math import advantages, token_logps, token_objective
from grpo_reward import score
from patch_validation import validate
from train_sft_complete import ROOT, digest, encode, model_loss

TASKS = ("mix", "form", "texture")
STYLES = ("arp_16", "broken_8", "block", "ostinato", "pad")


def compact_texture(row):
    """A coherent two-bar, first-chord task; preserve every original style."""
    result = dict(row)
    instruction = json.loads(row["instruction"])
    state = instruction["state"]
    state["progression"] = state["progression"][:1]
    state["bars"] = 2
    tail = instruction["intent"].split("进行", 1)[1]
    instruction["intent"] = state["progression"][0] + " 进行" + tail + "仅生成 2 小节，每个和弦占 2 小节。"
    gold = json.loads(row["output"])
    gold["notes"] = [dict(note) for note in gold["notes"] if note["bar"] <= 2]
    for note in gold["notes"]:
        note["len_steps"] = min(note["len_steps"], 32 - ((note["bar"] - 1) * 16 + note["step"]))
    if not validate("texture", state, gold)[0]:
        raise ValueError("Invalid compact texture target")
    result["instruction"] = json.dumps(instruction, ensure_ascii=False, separators=(",", ":"))
    result["output"] = json.dumps(gold, ensure_ascii=False, separators=(",", ":"))
    return result


def prepare(tok, rows, max_length):
    result = []
    for row in rows:
        parsed = json.loads(row["instruction"])
        if not validate(row["task"], parsed["state"], json.loads(row["output"]))[0]:
            raise ValueError("Invalid training target")
        item = {"row": row, "feature": encode(tok, row, max_length), "instruction": parsed,
                "gold": json.loads(row["output"]), "variant": "original"}
        if row["task"] == "texture":
            short = compact_texture(row)
            item["compact"] = {"row": short, "feature": encode(tok, short, max_length),
                               "instruction": json.loads(short["instruction"]),
                               "gold": json.loads(short["output"]), "variant": "two_bar"}
        result.append(item)
    return result


def disable_dropout(model):
    import torch
    for module in model.modules():
        if isinstance(module, torch.nn.Dropout):
            module.p = 0.


def select(model, adapter, training):
    model.set_adapter(adapter)
    # set_adapter also changes requires_grad; assert our own policy explicitly.
    for name, param in model.named_parameters():
        param.requires_grad_(adapter == "default" and ".default." in name)
    model.train(training)
    disable_dropout(model)


def completion_logps(model, ids, prompt_length, chunk, recompute, temperature):
    import torch
    core = model.get_base_model()
    hidden = core.model(input_ids=ids.unsqueeze(0), attention_mask=torch.ones_like(ids).unsqueeze(0),
                        use_cache=False).last_hidden_state[0]
    return token_logps(core.lm_head, hidden[prompt_length - 1:-1], ids[prompt_length:], chunk, recompute, temperature)


def fingerprint(named):
    checksum = hashlib.sha256()
    for name, param in named:
        checksum.update(name.encode())
        checksum.update(param.detach().float().cpu().numpy().tobytes())
    return checksum.hexdigest()


def grad_norm(params):
    import torch
    gradients = [torch.linalg.vector_norm(p.grad.detach().float()) for p in params if p.grad is not None]
    return float(torch.linalg.vector_norm(torch.stack(gradients))) if gradients else 0.


def wait_for_idle(timeout=600):
    start, snapshots = time.monotonic(), []
    while len(snapshots) < 2:
        try:
            query = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, check=True, timeout=15)
            lines = query.stdout.strip().splitlines()
            if len(lines) != 1:
                raise RuntimeError("Expected exactly one GPU")
            memory, utilization = [int(value.strip()) for value in lines[0].split(",")]
            # The user authorized GPU use; allow the verified QQ/Codex desktop load.
            # Require >23 GB free on this 24 GB card and no sustained high utilization.
            if memory > 1024 or utilization > 25:
                raise RuntimeError(f"GPU occupied: {memory} MiB, {utilization}%; no model loaded")
            snapshots.append({"memory_mib": memory, "utilization_percent": utilization,
                              "at": datetime.now(timezone.utc).isoformat()})
        except RuntimeError as exc:
            snapshots = []
            print(json.dumps({"event": "waiting_for_gpu", "reason": str(exc)}), flush=True)
        if time.monotonic() - start > timeout:
            raise RuntimeError("GPU did not become idle within the bounded wait; no model loaded")
        if len(snapshots) < 2:
            time.sleep(5)
    return snapshots


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=Path(r"D:\train\models\Qwen3.5-4B"))
    ap.add_argument("--adapter", type=Path, default=Path(r"D:\LLM\models\dawcoder-sft-v2"))
    ap.add_argument("--data", type=Path, default=ROOT / "training/data/dawcoder_sft_train.jsonl")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--group", type=int, default=4)
    ap.add_argument("--generation-batch-size", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-6)
    ap.add_argument("--beta", type=float, default=.05)
    ap.add_argument("--replay-weight", type=float, default=.1)
    ap.add_argument("--std-floor", type=float, default=.02)
    ap.add_argument("--temperature", type=float, default=.8)
    ap.add_argument("--compact-texture", action="store_true", help="experimental; full original tasks are the default")
    ap.add_argument("--start-task", choices=TASKS, default="mix")
    ap.add_argument("--max-length", type=int, default=4096)
    ap.add_argument("--chunk", type=int, default=128)
    ap.add_argument("--save-every", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()
    if args.group < 2 or min(args.steps, args.chunk, args.save_every, args.generation_batch_size) < 1 or args.temperature <= 0:
        ap.error("At least two completions, positive steps/chunk/save interval required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    runtime = ROOT / "_tmp/posttrain/runtime-cache"
    for variable, leaf in (("TRITON_CACHE_DIR", "triton"), ("TORCHINDUCTOR_CACHE_DIR", "inductor"),
                           ("TEMP", "temp"), ("TMP", "temp")):
        target = runtime / leaf
        target.mkdir(parents=True, exist_ok=True)
        os.environ[variable] = str(target)
    if args.prepare_only:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer, Qwen3_5ForCausalLM, StoppingCriteria, StoppingCriteriaList

    torch.set_num_threads(4)
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Use a fresh output directory")
    rows = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines() if line.strip()]
    system_file = ROOT / "preview/system_prompt.txt"
    system = system_file.read_text(encoding="utf-8").strip()
    if any(row["system"] != system for row in rows):
        raise ValueError("System prompt mismatch")
    tok = AutoTokenizer.from_pretrained(args.base, local_files_only=True, trust_remote_code=False)
    items = prepare(tok, rows, args.max_length)
    pools = {task: [item for item in items if item["row"]["task"] == task] for task in TASKS}
    styles = {style: [item for item in pools["texture"] if item["instruction"]["state"]["style"] == style] for style in STYLES}
    if not all(styles.values()):
        raise ValueError("Missing texture style")
    rng = random.Random(args.seed)
    for pool in list(pools.values()) + list(styles.values()):
        rng.shuffle(pool)
    if args.prepare_only:
        print(json.dumps({"cpu_only": True, "original": {task: len(pool) for task, pool in pools.items()},
                          "compact_texture_styles": {style: len(pool) for style, pool in styles.items()},
                          "max_original_tokens": max(len(item["feature"]["ids"]) for item in items),
                          "max_compact_tokens": max(len(item["compact"]["feature"]["ids"]) for item in pools["texture"]),
                          "group": args.group, "truncated_targets": 0}))
        return
    idle = wait_for_idle()
    torch.manual_seed(args.seed)
    args.output.mkdir(parents=True)
    manifest = {"method": "GRPO token BNPO + k3 KL + complete-output SFT replay",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                "idle_before_load": idle, "data_sha256": digest(args.data),
                "parent_adapter_sha256": digest(args.adapter / "adapter_model.safetensors"),
                "system_prompt_sha256": digest(system_file),
                "source_sha256": {name: digest(ROOT / "training" / name) for name in
                                  ("train_grpo_v3.py", "grpo_math.py", "grpo_reward.py", "train_sft_complete.py", "patch_validation.py")},
                "packages": {name: importlib.metadata.version(name) for name in ("torch", "peft", "transformers", "trl")},
                "validation_file_read_by_trainer": False, "sampling": {"temperature": args.temperature, "top_p": 1., "top_k": 0},
                "truncated_rollout_loss": "excluded; need at least two complete answers", "target_truncation": False}
    manifest_path = args.output / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    source_snapshot = args.output / "source"
    source_snapshot.mkdir()
    for name in manifest["source_sha256"]:
        shutil.copy2(ROOT / "training" / name, source_snapshot / name)
    print("Loading policy + reference", flush=True)
    core = Qwen3_5ForCausalLM.from_pretrained(args.base, local_files_only=True, trust_remote_code=False,
                                            dtype=torch.bfloat16, device_map={"": 0})
    model = PeftModel.from_pretrained(core, args.adapter, adapter_name="default", is_trainable=True, local_files_only=True)
    model.load_adapter(args.adapter, adapter_name="ref", is_trainable=False, local_files_only=True)
    named = dict(model.named_parameters())
    ref_params = [(name, param) for name, param in named.items() if ".ref." in name]
    # Eliminate load_adapter's BF16 round-trip on the reference's FP32 LoRA weights.
    with torch.no_grad():
        for name, param in ref_params:
            policy = named[name.replace(".ref.", ".default.")]
            param.copy_(policy)
            assert torch.equal(param, policy)
    ref_start = fingerprint(ref_params)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    select(model, "default", True)
    for config in model.peft_config.values():
        config.lora_dropout = 0.
    trainable = [p for name, p in named.items() if ".default." in name]
    optimizer = torch.optim.AdamW(trainable, lr=args.lr, betas=(.9, .95), weight_decay=0.)
    initial_probes = [p.detach().flatten()[:32].cpu().clone() for p in trainable]
    t0, total_rollouts = time.time(), 0
    schedule, metrics = [], []
    for step in range(1, args.steps + 1):
        task = TASKS[(step - 1 + TASKS.index(args.start_task)) % 3]
        round_index = (step - 1) // 3
        for attempt in range(3):
            if task == "texture":
                style = STYLES[round_index % len(STYLES)]
                pool = styles[style]
                item = pool[(round_index // len(STYLES) + attempt) % len(pool)]
                if args.compact_texture and round_index % 4 != 3:
                    item = item["compact"]
            else:
                item = pools[task][(round_index + attempt) % len(pools[task])]
            feat = item["feature"]
            prompt = feat["ids"][:feat["prompt_length"]]
            gold_length = len(feat["ids"]) - len(prompt)
            budget = min(args.max_length - len(prompt), max(256, math.ceil((gold_length + 256) / 128) * 128))
            input_ids = torch.tensor([prompt], device="cuda", dtype=torch.long)
            select(model, "default", False)
            print(json.dumps({"event": "generate", "step": step, "task": task, "variant": item["variant"],
                              "attempt": attempt, "group": args.group, "max_new_tokens": budget}), flush=True)
            generated = []
            # The underlying Qwen model already contains active LoRA layers. Calling
            # it directly exposes its cache/logits_to_keep generation contract.
            generation_model = model.get_base_model()
            generation_model.config.use_cache = True
            generation_model.generation_config.use_cache = True
            for offset in range(0, args.group, args.generation_batch_size):
                batch_size = min(args.generation_batch_size, args.group - offset)
                generation_start = time.time()
                cache_calls = [0]

                def check_cache(module, positional, keyword):
                    current_ids = keyword.get("input_ids")
                    if current_ids is not None:
                        length = current_ids.shape[-1]
                        if cache_calls[0] and length != 1:
                            raise RuntimeError(f"Generation KV cache ineffective: decoder received {length} tokens after prefill")
                        cache_calls[0] += 1

                class Progress(StoppingCriteria):
                    def __call__(self, current_ids, scores, **kwargs):
                        length = current_ids.shape[1] - len(prompt)
                        if length % 256 == 0:
                            reserved_before = torch.cuda.memory_reserved()
                            # Windows can spill cached blocks into shared memory as
                            # dynamic KV lengths accumulate many allocation sizes.
                            # Release only unused blocks; live KV tensors stay intact.
                            if reserved_before - torch.cuda.memory_allocated() > 512 * 2**20:
                                torch.cuda.empty_cache()
                            print(json.dumps({"event": "generation_progress", "step": step, "task": task,
                                              "offset": offset, "batch": batch_size, "tokens": length,
                                              "elapsed_seconds": round(time.time() - generation_start, 2),
                                              "allocated_gib": round(torch.cuda.memory_allocated() / 2**30, 3),
                                              "reserved_gib": round(torch.cuda.memory_reserved() / 2**30, 3),
                                              "released_cache_gib": round((reserved_before - torch.cuda.memory_reserved()) / 2**30, 3)}), flush=True)
                        return False

                handle = generation_model.model.register_forward_pre_hook(check_cache, with_kwargs=True)
                try:
                    with torch.no_grad():
                        batch = generation_model.generate(input_ids=input_ids, attention_mask=torch.ones_like(input_ids),
                                               do_sample=True, temperature=args.temperature, top_p=1., top_k=0,
                                               repetition_penalty=1., num_beams=1, num_return_sequences=batch_size,
                                               max_new_tokens=budget, use_cache=True, logits_to_keep=1,
                                               stopping_criteria=StoppingCriteriaList([Progress()]),
                                               pad_token_id=tok.eos_token_id, eos_token_id=tok.eos_token_id)
                    generated.extend(row for row in batch)
                    print(json.dumps({"event": "generation_done", "step": step, "offset": offset,
                                      "batch": batch_size, "cached_forward_calls": cache_calls[0],
                                      "elapsed_seconds": round(time.time() - generation_start, 2)}), flush=True)
                finally:
                    handle.remove()
                torch.cuda.empty_cache()
            generation_model.config.use_cache = False
            if len(generated) != args.group:
                raise RuntimeError("Wrong number of same-prompt rollouts")
            records = []
            for generated_ids in generated:
                completion = generated_ids[len(prompt):]
                ends = (completion == tok.eos_token_id).nonzero()
                truncated = len(ends) == 0
                if not truncated:
                    completion = completion[:int(ends[0]) + 1]
                text = tok.decode(completion, skip_special_tokens=True)
                reward = score(task, item["instruction"]["state"], item["gold"], text)
                records.append({"ids": torch.cat((input_ids[0], completion)), "output": text,
                                "truncated": truncated, "length": len(completion), **reward})
            total_rollouts += len(records)
            complete = [r for r in records if not r["truncated"]]
            adv, std = advantages([r["reward"] for r in complete], args.std_floor) if len(complete) >= 2 else ([], 0.)
            trace = {"step": step, "attempt": attempt, "task": task, "variant": item["variant"],
                     "instruction": item["row"]["instruction"], "std": std,
                     "rollouts": [{k: v for k, v in r.items() if k != "ids"} for r in records]}
            with (args.output / "rollouts.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
            if len(complete) >= 2 and std > 1e-6:
                break
            print(json.dumps({"event": "retry_no_signal", "step": step, "complete": len(complete), "std": std}), flush=True)
        else:
            raise RuntimeError("No usable within-prompt advantage after 3 groups; inspect rollouts")
        # Finish all reference scoring before building any policy backward graph.
        select(model, "default", True)
        with torch.no_grad():
            for record in complete:
                record["old"] = completion_logps(model, record["ids"], len(prompt), args.chunk, False, args.temperature).detach()
        select(model, "ref", True)
        with torch.no_grad():
            for record in complete:
                record["ref"] = completion_logps(model, record["ids"], len(prompt), args.chunk, False, args.temperature).detach()
        select(model, "default", True)
        torch.cuda.empty_cache()
        optimizer.zero_grad(set_to_none=True)
        denominator = sum(record["length"] for record in complete)
        loss_total = kl_total = max_old_difference = 0.
        for record, advantage in zip(complete, adv):
            new = completion_logps(model, record["ids"], len(prompt), args.chunk, True, args.temperature)
            difference = float((new.detach() - record["old"]).abs().max())
            max_old_difference = max(max_old_difference, difference)
            if difference > .25:
                raise RuntimeError(f"Train/behavior logp mismatch: {difference}")
            loss, kl = token_objective(new, record["old"], record["ref"], advantage, args.beta)
            scaled = loss.sum() / denominator
            if not torch.isfinite(scaled):
                raise RuntimeError("Non-finite GRPO loss")
            scaled.backward()
            loss_total += float(scaled.detach())
            kl_total += float(kl.detach().sum()) / denominator
        rl_grad = grad_norm(trainable)
        if not math.isfinite(rl_grad) or rl_grad <= 0:
            raise RuntimeError("GRPO gradient is zero or non-finite")
        replay_task = TASKS[(step + TASKS.index(args.start_task)) % 3]
        replay = pools[replay_task][round_index % len(pools[replay_task])]
        replay_loss = model_loss(model, replay["feature"], tok.pad_token_id or tok.eos_token_id, args.chunk)
        (args.replay_weight * replay_loss).backward()
        if any(param.grad is not None for _, param in ref_params):
            raise RuntimeError("Reference received gradients")
        norm = torch.nn.utils.clip_grad_norm_(trainable, 1.)
        if not torch.isfinite(norm):
            raise RuntimeError("Non-finite total gradient")
        warmup = min(3, args.steps)
        lr = args.lr * (step / warmup if step <= warmup else .1 + .9 * .5 * (1 + math.cos(math.pi * (step - warmup) / max(1, args.steps - warmup))))
        for group in optimizer.param_groups:
            group["lr"] = lr
        optimizer.step()
        changed = sum(not torch.equal(a, b.detach().flatten()[:32].cpu()) for a, b in zip(initial_probes, trainable))
        if not changed:
            raise RuntimeError("Policy weights did not update")
        record = {"step": step, "task": task, "variant": item["variant"], "group_size": len(records),
                  "complete_rollouts": len(complete), "reward_mean": sum(r["reward"] for r in complete) / len(complete),
                  "reward_std": std, "advantages": adv, "valid_rate": sum(r["valid"] for r in records) / len(records),
                  "grpo_loss": loss_total, "mean_k3_kl": kl_total, "rl_grad_norm": rl_grad,
                  "total_grad_norm": float(norm), "replay_task": replay_task, "replay_loss": float(replay_loss.detach()),
                  "max_old_logp_difference": max_old_difference, "changed_tensor_probes": changed,
                  "lr": lr, "elapsed_seconds": round(time.time() - t0, 2),
                  "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3)}
        metrics.append(record)
        schedule.append({"task": task, "variant": item["variant"], "input_sha256": feat["input_sha256"],
                         "replay_task": replay_task, "replay_input_sha256": replay["feature"]["input_sha256"]})
        with (args.output / "metrics.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)
        if step % args.save_every == 0:
            checkpoint = args.output / f"checkpoint-{step}"
            model.save_pretrained(checkpoint, selected_adapters=["default"])
            torch.save({"step": step, "optimizer": optimizer.state_dict(), "cuda_rng": torch.cuda.get_rng_state(),
                        "torch_rng": torch.get_rng_state(), "random_rng": rng.getstate()}, checkpoint / "optimizer_state.pt")
    ref_end = fingerprint(ref_params)
    if ref_end != ref_start:
        raise RuntimeError("Frozen reference changed")
    model.save_pretrained(args.output, selected_adapters=["default"])
    manifest.update({"completed_steps": args.steps, "finished_at": datetime.now(timezone.utc).isoformat(),
                     "adapter_sha256": digest(args.output / "adapter_model.safetensors"),
                     "elapsed_seconds": round(time.time() - t0, 2), "total_rollouts": total_rollouts,
                     "reference_start_sha256": ref_start, "reference_end_sha256": ref_end,
                     "reference_unchanged": True, "schedule": schedule,
                     "rl_gradient_nonzero_steps": sum(m["rl_grad_norm"] > 0 for m in metrics)})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SAVED " + str(args.output), flush=True)


if __name__ == "__main__":
    main()

"""CPU-only local export: adapter -> merged HF -> bf16 GGUF -> Q4_K_M.

Does not register/deploy an Ollama model or run the fixed evaluation set.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--name", default="dawcoder-sft-v2")
    ap.add_argument("--base", type=Path, default=Path(r"D:\train\models\Qwen3.5-4B"))
    args = ap.parse_args()
    if not args.name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.name):
        raise ValueError("Model name must contain lowercase letters, digits or hyphens")
    adapter_file = args.adapter / "adapter_model.safetensors"
    manifest_file = args.adapter / "run_manifest.json"
    run = json.loads(manifest_file.read_text(encoding="utf-8"))
    if run.get("completed_steps") != run["args"]["steps"]:
        raise ValueError("Training run is incomplete")
    if sha(adapter_file) != run["adapter_sha256"]:
        raise ValueError("Adapter hash differs from completed run manifest")
    system_file = ROOT / "preview/system_prompt.txt"
    if sha(system_file) != run["system_prompt_sha256"]:
        raise ValueError("System prompt changed after training")
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Export directory is not empty")
    args.out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": "-1", "HF_HUB_OFFLINE": "1", "PYTHONUNBUFFERED": "1",
                "OMP_NUM_THREADS": "8", "MKL_NUM_THREADS": "8"})
    temp = ROOT / "_tmp/posttrain/runtime-cache/temp"
    temp.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = env["TMP"] = str(temp)
    stages = []

    def execute(name, command):
        log = args.out / f"{name}.log"
        print(f"START {name}", flush=True)
        with log.open("w", encoding="utf-8") as stream:
            subprocess.run([str(x) for x in command], stdout=stream, stderr=subprocess.STDOUT,
                           check=True, env=env, cwd=ROOT)
        stages.append({"name": name, "command": [str(x) for x in command], "log": str(log)})
        print(f"DONE {name}", flush=True)

    merged = args.out / "merged-hf"
    bf16 = args.out / f"{args.name}-bf16.gguf"
    q4 = args.out / f"{args.name}-Q4_K_M.gguf"
    merge_script = Path(r"D:\train\scripts\merge_lora.py")
    convert_script = Path(r"D:\llama\llama.cpp\convert_hf_to_gguf.py")
    quantizer = Path(r"D:\llama\b12110\llama-quantize.exe")
    started = datetime.now(timezone.utc).isoformat()
    execute("merge", [sys.executable, merge_script, "--base", args.base, "--adapter", args.adapter, "--output", merged])
    execute("convert", [sys.executable, convert_script, merged, "--outfile", bf16, "--outtype", "bf16"])
    execute("quantize", [quantizer, bf16, q4, "Q4_K_M", "8"])
    with q4.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("Export does not have a GGUF header")
    system = system_file.read_text(encoding="utf-8").strip()
    modelfile = args.out / "Modelfile"
    modelfile.write_text(f'FROM "{q4.as_posix()}"\nSYSTEM """\n{system}\n"""\n'
                         'PARAMETER num_ctx 16384\nPARAMETER temperature 0\n'
                         'PARAMETER top_p 0.95\nPARAMETER repeat_penalty 1.0\nPARAMETER num_predict 8192\n',
                         encoding="utf-8")
    report = {"model_name": args.name, "cpu_only_export": True, "started_at": started,
              "finished_at": datetime.now(timezone.utc).isoformat(), "adapter": str(args.adapter),
              "adapter_sha256": sha(adapter_file), "system_prompt_sha256": sha(system_file),
              "merged_hf": str(merged), "q4_gguf": str(q4), "q4_bytes": q4.stat().st_size,
              "q4_sha256": sha(q4), "bf16_gguf": str(bf16), "modelfile": str(modelfile),
              "tools_sha256": {str(p): sha(p) for p in (merge_script, convert_script, quantizer)},
              "stages": stages, "ollama_registered": False, "fixed_eval_run": False}
    (args.out / "export_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "stages"}), flush=True)


if __name__ == "__main__":
    main()

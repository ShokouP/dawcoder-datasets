"""Batch-evaluate one or more Ollama models with the standard DAWcoder protocol.

  python training/eval_all_models.py --models dawcoder-preview,dawcoder-dpo-v3 --limit 60
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ROOT / "training"
PY = sys.executable


def safe(name: str) -> str:
    return name.replace(":", "-").replace("/", "-").replace("\\", "-")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="comma-separated Ollama model names")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20261107)
    ap.add_argument("--num-predict", type=int, default=8192)
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results = []
    for model in models:
        out = TRAIN / f"eval-report-{safe(model)}.json"
        cmd = [PY, str(TRAIN / "eval_dawcoder.py"), "--model", model,
               "--limit", str(args.limit), "--seed", str(args.seed),
               "--num-predict", str(args.num_predict), "--out", str(out)]
        print("=" * 60)
        print("EVAL", model, flush=True)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        print(proc.stdout[-1500:])
        if proc.returncode != 0:
            print(proc.stderr[-1500:])
            results.append({"model": model, "ok": False})
        else:
            results.append({"model": model, "ok": True, "report": str(out)})

    print("\nDONE:")
    for r in results:
        print(" ", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

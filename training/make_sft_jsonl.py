"""把 synthetic/ 的 chat 格式转成 train_sft.py 需要的 {system, instruction, output} 格式。

用法：python training/make_sft_jsonl.py
输出：training/data/dawcoder_sft_{train,val}.jsonl
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "synthetic" / "data"
OUT = ROOT / "training" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def convert(split: str) -> tuple[int, int]:
    rows = []
    for task in ("mix", "form", "texture"):
        path = SRC / f"sft_{task}_{split}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            msgs = json.loads(line)["messages"]
            system = msgs[0]["content"] if msgs[0]["role"] == "system" else ""
            user = next(m["content"] for m in msgs if m["role"] == "user")
            assistant = next(m["content"] for m in msgs if m["role"] == "assistant")
            rows.append({"system": system, "instruction": user, "output": assistant, "task": task})
    path = OUT / f"dawcoder_sft_{split}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8", newline="\n")
    chars = sum(len(r["instruction"]) + len(r["output"]) for r in rows)
    print(f"{path.name}: {len(rows)} rows / {chars/1e6:.2f}M chars")
    return len(rows), chars


if __name__ == "__main__":
    convert("train")
    convert("val")

"""把 curated 语料转成 CPT 训练格式（仅保留 text 列，列结构统一）。

用法：
  python cpt/make_cpt_text.py cpt/data-curated
"""
import json
import sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "cpt/data-curated")
for split in ("train", "val"):
    inp = src / f"corpus_{split}.jsonl"
    out = src / f"cpt_{split}_text.jsonl"
    n = chars = 0
    with inp.open(encoding="utf-8") as fh, out.open("w", encoding="utf-8", newline="\n") as oh:
        for line in fh:
            if not line.strip():
                continue
            d = json.loads(line)
            text = d.get("text", "")
            if len(text) < 300:
                continue
            oh.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
            n += 1
            chars += len(text)
    print(f"{out}: {n} docs / {chars/1e6:.1f}M chars")

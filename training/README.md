# 用 DAWcoder 数据训练预览版

本仓库的数据已经是训练就绪格式。完整链路：**CPT（领域继续预训练）→ merge → SFT → 导出 GGUF/Ollama → 评测**。

## 0. 前置

- 基座：`Qwen3.5-4B`（本地 `D:\train\models\Qwen3.5-4B`）
- 环境：`D:\train\venv`（torch 2.11.0+cu128），RTX 5090 Laptop 24GB，Windows 原生

## 1. CPT（用 cpt/ 语料）

```powershell
# 构建 curated 语料 + 训练格式（见 cpt/README.md）
python cpt/build.py --max-tokens 30000000 --raw-dir cpt/raw-curated --out cpt/data-curated --corpus-name dawcoder-cpt-v0.3-curated-full
python cpt/make_cpt_text.py cpt/data-curated

D:\train\venv\Scripts\python.exe D:\train\scripts\train_cpt.py `
  --model D:\train\models\Qwen3.5-4B `
  --data cpt/data-curated/cpt_train_text.jsonl `
  --output D:\train\models\dawcoder_cpt_v1 `
  --seq 1024 --max-steps 400 --max-samples 24000 --lr 1e-4 --accum 16
```

记录见 [`../cpt/TRAINING.md`](../cpt/TRAINING.md)。

## 2. 合并 CPT adapter

```powershell
D:\train\venv\Scripts\python.exe D:\train\scripts\merge_lora.py `
  --base D:\train\models\Qwen3.5-4B `
  --adapter D:\train\models\dawcoder_cpt_v1 `
  --output D:\train\models\dawcoder_cpt_v1_merged
```

## 3. SFT（用 synthetic/ 数据）

先把 chat 格式转成训练脚本需要的 `{system, instruction, output}`：

```bash
python training/make_sft_jsonl.py    # -> training/data/dawcoder_sft_{train,val}.jsonl
```

```powershell
D:\train\venv\Scripts\python.exe D:\train\scripts\train_sft.py `
  --model D:\train\models\dawcoder_cpt_v1_merged `
  --data training/data/dawcoder_sft_train.jsonl `
  --output D:\train\models\dawcoder_sft_v1 `
  --seq 2048 --epochs 1 --lr 5e-5 --accum 16
```

## 4. 导出（GGUF + Ollama）

```powershell
powershell -File D:\train\scripts\export_deploy.ps1 -Adapter D:\train\models\dawcoder_sft_v1 -Name dawcoder-preview
```

链路：merge LoRA → bf16 GGUF → Q4_K_M → `ollama create dawcoder-preview` → 冒烟测试。

## 5. 评测

```powershell
python training/eval_dawcoder.py --model dawcoder-preview --limit 60 --out training/eval-report.json
```

输出 JSON 解析率、mix/form/texture 三任务 schema 合法率与样例。目标（预览版）：
- JSON 解析率 ≥ 95%
- 各任务 schema 合法率 ≥ 80%
- 与未微调基座在同样 val 上对比提升明显

## 6. 训练记录模板

| 项 | 值 |
|---|---|
| base | Qwen3.5-4B |
| CPT 数据 | curated v0.3（manifest sha256） |
| CPT 配置 | LoRA r=64, seq 1024, 400 steps |
| SFT 数据 | dawcoder-synth-v0.1（3,240 条） |
| SFT 配置 | LoRA r=64, seq 2048, 1 epoch |
| JSON 解析率 | __% |
| schema 合法率 | mix __% / form __% / texture __% |

# DAWcoder 预览版训练记录

> 目标：完成 CPT（继续预训练）→ SFT → 评测 → 导出 GGUF，形成 DAWcoder 预览版。

## 2026-11-07 训练批次 #1（进行中）

- **数据**：`cpt/data-curated/cpt_train_text.jsonl`（57,728 docs / 94.7M 字符 / ~23.7M tokens，curated v0.3）
- **基座**：`D:\train\models\Qwen3.5-4B`（bf16）
- **方式**：LoRA r=64 / all-linear，seq 1024，batch 1 × grad-accum 16，lr 1e-4，cosine，400 步（约 655 万 tokens，预览量级）
- **环境**：RTX 5090 Laptop 24GB，Windows 原生，`D:\train\venv`（torch 2.11.0+cu128）
- **输出**：`D:\train\models\dawcoder_cpt_v1`（adapter）
- **日志**：`D:\train\runs\dawcoder_cpt_v1.log`
- **启动命令**：
  ```powershell
  D:\train\venv\Scripts\python.exe D:\train\scripts\train_cpt.py `
    --model D:\train\models\Qwen3.5-4B `
    --data cpt/data-curated/cpt_train_text.jsonl `
    --output D:\train\models\dawcoder_cpt_v1 `
    --seq 1024 --max-steps 400 --max-samples 24000 --lr 1e-4 --accum 16
  ```
- **预计**：约 1–1.5 小时（1,500 tok/s 量级；GPU 实测 94% 利用率 / 19.3GB 显存）

## 后续步骤（自动流水线，已启动）

已启动 `D:\train\scripts\run_dawcoder_preview.ps1`（后台），流程：

1. 等待 CPT 训练完成（检测日志 `SAVED`）；
2. `merge_lora.py`：Qwen3.5-4B + `dawcoder_cpt_v1` → `dawcoder_cpt_v1_merged`（CPU）；
3. SFT：`train_sft.py`（merged + `training/data/dawcoder_sft_train.jsonl`，seq 1536，1 epoch）→ `dawcoder_sft_v1`；
4. `merge_lora.py`：`dawcoder_cpt_v1_merged` + `dawcoder_sft_v1` → `dawcoder_preview_merged`；
5. `convert_hf_to_gguf.py` → bf16 GGUF → `llama-quantize` → Q4_K_M；
6. `ollama create dawcoder-preview`（Modelfile：num_ctx 16384 / temp 0 / top_p 0.95）；
7. `training/eval_dawcoder.py` 跑 30 条 val（JSON 解析率 + schema 合法率）→ `training/eval-report.json`。

日志：
- 流水线：`D:\train\runs\dawcoder-preview-pipeline.log`
- SFT：`D:\train\runs\dawcoder_sft_v1.log`
- 导出/评测：`D:\train\runs\{merge,convert,quant,ollama-create,eval}-dawcoder*.log`

**当前状态（14:55）**：CPT 训练中（step ~34/400，约 10.3s/step，预计 ~16:00 完成）；流水线已就绪等待。

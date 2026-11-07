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

## 后续步骤（待执行）

1. CPT 完成后：合并 LoRA → `dawcoder_cpt_v1_merged`
2. SFT：用 `synthetic/data/sft_*_train.jsonl`（3,240 条 chat 样本）训练 adapter `dawcoder_sft_v1`
3. 评测：`synthetic/check.py` 同款规则检查 patch 合法率；mix/form/texture 各抽 20 条人检；与基座 instruct 对拍
4. 导出：merge → bf16 GGUF / Q4_K_M → Ollama 模型 `dawcoder-preview`（参考 `D:\train\scripts\export_deploy.ps1`）
5. 更新 `cpt/README`、`README` 与数据卡，发布 preview release

# 直接用 DAWcoder 数据训练

本仓库的数据已经是**训练就绪**的 chat 格式，包含 3,600 条样本（train/val 已切分）。

## 1. 数据在哪

```
synthetic/data/sft_mix_train.jsonl      1080 条   (mix)
synthetic/data/sft_form_train.jsonl      540 条   (form)
synthetic/data/sft_texture_train.jsonl 1620 条   (texture)
synthetic/data/sft_*_val.jsonl           360 条   (验证)
```

每行：

```json
{"messages":[
  {"role":"system","content":"…你是 DAWcoder…只输出 JSON…"},
  {"role":"user","content":"{\"task\":\"mix\",\"state\":{…},\"intent\":\"…\"}"},
  {"role":"assistant","content":"{\"ops\":[…]}"}
]}
```

合并训练（推荐一次学三种任务）：

```bash
# Windows PowerShell
Get-Content synthetic/data/sft_mix_train.jsonl, synthetic/data/sft_form_train.jsonl, synthetic/data/sft_texture_train.jsonl |
  Set-Content synthetic/data/sft_all_train.jsonl
```

## 2. 用 LLaMA-Factory（示例）

`dataset_info.json`：

```json
{
  "dawcoder_sft": {
    "file_name": "sft_all_train.jsonl",
    "formatting": "sharegpt",
    "columns": {"messages": "messages"},
    "tags": {"role_tag": "role", "content_tag": "content", "user_tag": "user", "assistant_tag": "assistant", "system_tag": "system"}
  }
}
```

LoRA 配置（Qwen3.5-4B，参考你现有训练脚本）：

```yaml
model_name_or_path: Qwen/Qwen3.5-4B
stage: sft
do_train: true
finetuning_type: lora
lora_rank: 64
lora_target: all
dataset: dawcoder_sft
cutoff_len: 2048
per_device_train_batch_size: 1
gradient_accumulation_steps: 16
learning_rate: 5.0e-5
num_train_epochs: 3
bf16: true
gradient_checkpointing: true
# 注意：Windows 上务必定长 padding（见项目经验），否则显存 reserved 飙升
padding_side: right
train_on_prompt: false   # 只在 assistant 上算 loss
```

预计：3,240 条 × ~1.2k tokens，4B LoRA 在 5090 Laptop 24GB 上约 **40–70 分钟**（按 1,500 tok/s 粗估，定长 padding 后实测校准）。

## 3. 训练后必须做的三件事

1. **格式合法率**：用 `synthetic/check.py` 同款规则检查模型输出，目标 >95%。
2. **对拍基线**：与未微调的 Qwen3.5-4B（instruct）在同一批 val 上比较，确认 patch 合法率提升。
3. **别过拟合格式**：合成数据只教"输出结构 + 任务映射"，真实混音判断要靠后续 L1–L5 数据（见 `DATASETS.md`）。

## 4. 换更大数据时

- 保持同一 chat 格式与 ID 规范，直接替换 `sft_all_train.jsonl`；
- 商用训练集只能用 T0/T1 数据（`registry/datasets.yaml` + `tools/export.py` 的 commercial profile）；
- 每次换数据都更新 `manifest.json`（sha256 + 行数），训练记录里带上 manifest 版本号，保证可复现。

## 5. 指标记录模板

| 项 | 值 |
|---|---|
| base model | Qwen3.5-4B (Instruct) |
| 数据 | dawcoder-synth-v0.1（manifest sha256） |
| 训练配置 | LoRA r=64, seq 2048, 3 epoch |
| patch 合法率 | __% |
| val 上 JSON 解析失败率 | __% |
| 相对基线提升 | __ |

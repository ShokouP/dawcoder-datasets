# DAWcoder Preview v0.1 训练与评测结果（2026-11-08）

## 流水线

```
CPT (Qwen3.5-4B + LoRA r=64, corpus v1.0, 400 steps)
  → SFT (init from CPT adapter, 3,240 samples, 200 steps ≈ 1 epoch)
  → merge LoRA → bf16 GGUF → Q4_K_M (2.5GB)
  → ollama create dawcoder-preview
  → eval_dawcoder.py --limit 60
```

## 关键数字

| 阶段 | 用时 | 结果 |
|---|---|---|
| CPT | 78 min（11.98 s/step） | loss 2.67 → 2.57，train_loss 2.566（epoch 0.183） |
| SFT | 51 min（15.3 s/step） | train_loss 0.153（epoch 0.988） |
| merge + GGUF + quantize | ~1.4 min | bf16 7.9GB → Q4_K_M 2.5GB |
| eval | ~6 min | 60/60 valid |

## 评测结果（`training/eval-report-preview.json`）

| 任务 | n | parsed | valid | rate |
|---|---:|---:|---:|---:|
| mix | 20 | 20 | 20 | 100% |
| form | 20 | 20 | 20 | 100% |
| texture | 20 | 20 | 20 | 100% |
| **合计** | **60** | **60** | **60** | **100%** |

- json_parse_rate = 1.0
- valid_rate = 1.0
- macro_valid_rate = 1.0
- coverage_complete = true

## 手动抽查（temperature 0，3 个任务各 1 条）

- mix：`{"ops":[{"op":"set_track","track":"Drum Bus","fields":{"volume_db":-0.4}}]}` vs 期望 -0.3 → schema 合法，误差 0.1dB
- form：Intro/Build/Drop/Break/Drop 结构 → schema 合法，bars/energy/density 合理
- texture：琶音 note 序列 → schema 合法，参数范围正确

## 产物路径

| 产物 | 路径 |
|---|---|
| CPT adapter | `D:\train\models\dawcoder_cpt_v2`（520MB） |
| SFT adapter | `D:\train\models\dawcoder_sft_v1` |
| merged bf16 HF | `D:\train\models\dawcoder_preview_merged` |
| bf16 GGUF | `D:\train\models\dawcoder-preview-bf16.gguf`（7.9GB） |
| Q4_K_M GGUF | `D:\train\models\dawcoder-preview-Q4_K_M.gguf`（2.5GB） |
| Ollama 模型 | `dawcoder-preview:latest`（2.7GB） |
| 评测报告 | `training/eval-report-preview.json` |

## 注意

- 评测只验证 JSON 解析与 schema/参数范围，不代表混音语义或听感质量；
- 若要做语义评测，建议接 `daw-mcp-server` 的 `verify_patch`（apply → render → analyze → score）做闭环。

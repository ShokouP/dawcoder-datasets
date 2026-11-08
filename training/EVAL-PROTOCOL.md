# DAWcoder 评测协议（Evaluation Protocol）

本协议约定：**后训练由 GPTastra 执行**，本仓库（评测侧）负责统一评测与对比报告。

## 1. 交接内容（GPTastra → 评测侧）

每次实验提交一份完整、可复现的产物包：

```
submission/
├─ manifest.json            # 必填，见下
├─ adapter/                 # LoRA adapter（adapter_config.json + adapter_model.safetensors）
│  ├─ adapter_config.json
│  └─ adapter_model.safetensors
├─ merged/                  # 可选：已合并的 bf16 HF 模型（config.json + *.safetensors + tokenizer）
├─ model-Q4_K_M.gguf        # 可选：量化后 GGUF（如已导出）
├─ train.log                # 训练日志（loss/acc/reward 曲线）
└─ notes.md                 # 方法说明、超参、数据改动、已知问题
```

`manifest.json` 示例：

```json
{
  "name": "dawcoder-dpo-v3",
  "base_model": "Qwen3.5-4B",
  "stage": "dpo",
  "parent": "dawcoder-sft-v1",
  "data": {"path": "dpo_train.jsonl", "pairs": 3143, "generator": "..."},
  "hyperparams": {"lr": 2e-5, "beta": 0.1, "steps": 300, "seq": 1024, "accum": 8},
  "ollama_model": "dawcoder-dpo-v3",
  "system_prompt": "preview/system_prompt.txt",
  "sampling": {"temperature": 0.0, "top_p": 0.95, "num_ctx": 16384, "num_predict": 8192}
}
```

**命名约定**：`dawcoder-<stage>-<版本>`，例如 `dawcoder-dpo-v3`、`dawcoder-grpo-v2b`。
**系统提示词必须使用 `preview/system_prompt.txt`**（训练与评测必须一致，否则评测作废）。

## 2. 固定评测设置（评测侧执行，提交方不得修改）

| 项 | 值 |
|---|---|
| 验证集 | `training/data/dawcoder_sft_val.jsonl`（360 条，sha256 记录在报告里） |
| 采样 | balanced round-robin：mix 20 / form 20 / texture 20 = **60 条**，seed `20261107` |
| 解码 | temperature 0.0，top_p 0.95，num_ctx 16384，num_predict 8192 |
| 必备指标 | JSON 解析率、schema 合法率、per-task 合法率、reasons 分布、macro valid |
| 可选指标（语义） | 与金标准 patch 的相似度 reward（`lib_dawcoder_reward.py`），0~1 |
| 可选指标（闭环） | 通过 `daw-mcp-server` 的 `verify_patch`（apply → render → analyze → score） |

## 3. 评测命令

```bash
# 单模型 schema 评测
D:\train\venv\Scripts\python.exe training\eval_dawcoder.py \
  --model dawcoder-dpo-v3 --limit 60 --out training\eval-report-dpo-v3.json

# 批量评测
D:\train\venv\Scripts\python.exe training\eval_all_models.py \
  --models dawcoder-preview,dawcoder-dpo-v3 --limit 60

# 生成对比报告（eval 报告 + reward 对比）
D:\train\venv\Scripts\python.exe training\compare_models.py
```

## 4. 交付报告（评测侧 → 用户/GPTastra）

每次评测输出：

1. `training/eval-report-<model>.json`：原始评测数据
2. `training/COMPARISON-REPORT.md`：对比表（schema 合法率、per-task、reward、与基线的增减）+ 异常/回归标注
3. 结论：是否达到"可发布"标准（见 §5）

## 5. 可发布标准（预览版）

- JSON 解析率 ≥ 99%
- schema 合法率 ≥ 98%（macro，按任务均衡）
- 无单任务合法率 < 95%
- 相对基线（`dawcoder-preview`）不得出现任务级退化 > 5 个百分点
- 语义 reward 不低于基线 - 0.01（可选指标，有则要求）

## 6. 已知问题（转交 GPTastra 执行时注意）

1. **DPO 偏好对太容易**：上一轮 3,143 对中 SFT 已能选对 → acc 0.97、loss 恒 0.693、无有效梯度。需要"接近正确但有细微错误"的 rejected（±1.5dB、邻近频率、错一个 op）。
2. **texture 退化**：GRPO 未把长输出 texture 纳入（max_new 不足），导致 bad-bar；需要单独 max_new 2048 或按任务多 adapter。
3. **GRPO 奖励饱和**：合成数据使 policy 几乎总是满分（reward≈1.0，组内方差 0）→ 无优势信号；需要更难/未见过的 prompt 或闭环奖励。
4. **数据必须可复现**：提交 manifest + 数据 sha256；训练脚本/超参写进 notes.md。
5. **命名/路径**：adapter 必须是标准 PEFT 目录；导出的 Ollama 模型名写进 manifest。

## 7. 分工

- **GPTastra**：数据构造、DPO/GRPO 训练、导出 adapter/GGUF/Ollama 模型、提交产物包
- **评测侧（本会话）**：固定评测、批量评测脚本、对比报告、回归标注、验收结论

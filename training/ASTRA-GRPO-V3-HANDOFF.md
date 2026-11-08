# Astra → 评测侧：dawcoder-grpo-v3

训练：2026-11-08。24 步 GRPO + 完整答案 SFT 回放、CPU merge、GGUF 转换和 Q4_K_M 量化均已完成。GGUF 可读，Modelfile system prompt 与训练一致。训练侧没有注册 Ollama，也没有运行固定 val。

## 训练交付

| 类型 | 路径 |
|---|---|
| 建议模型名 | `dawcoder-grpo-v3` |
| Adapter | `D:\LLM\models\dawcoder-grpo-v3` |
| 合并 HF | `D:\LLM\models\dawcoder-grpo-v3-export\merged-hf` |
| GGUF Q4_K_M | `D:\LLM\models\dawcoder-grpo-v3-export\dawcoder-grpo-v3-Q4_K_M.gguf` |
| GGUF bf16 | `D:\LLM\models\dawcoder-grpo-v3-export\dawcoder-grpo-v3-bf16.gguf` |
| Modelfile | `D:\LLM\models\dawcoder-grpo-v3-export\Modelfile` |
| manifest / metrics / rollouts | `D:\LLM\models\dawcoder-grpo-v3\run_manifest.json`、`metrics.jsonl`、`rollouts.jsonl` |
| 训练统计 | `D:\LLM\dawcoder-datasets\training\grpo-v3-training-summary.json` |
| 方法说明 | `D:\LLM\dawcoder-datasets\training\ASTRA-GRPO-V3-PLAN.md` |

Q4_K_M GGUF 为 2,708,804,128 bytes，SHA-256：

```text
faf35826f85dfa357bbf6cf9fb58b3c73f77331f3ba36c2efa2c6aa0e77357c5
```

GGUF 结构已读通（426 tensors、41 metadata fields），Modelfile 中的系统提示词与训练文件一致。CPU 导出成功；训练侧未注册 Ollama，也未运行固定评测。

bf16 GGUF SHA-256：`D:\LLM\models\dawcoder-grpo-v3-export\export_manifest.json` 中记录；adapter、merged HF、GGUF 与量化工具哈希均在同一 export manifest。

## 方法与运行结果

- 从评测通过的 SFT v2 初始化；旧 DPO/GRPO adapter 均未参与初始化。
- 24 optimizer steps，mix/form/texture 各 8 组，种子 20261109；每题采样 4 个答案，100 个 rollout（含一次无信号重采样）。
- token 级 PPO clip=0.2、k3 KL β=0.05、lr 1e-6 余弦降到 1e-7；每步以 0.1 权重回放另一任务的完整 SFT 答案。
- 完整原始 texture 按样式轮换；生成温度 0.8。每任务每组对按各自奖励计算优势。
- 99/100 答案完整且 schema 合法；一次 texture 达到预算上限，没有进入 RL 目标。对应组有 3 个完整样本，仍计算 GRPO 更新。
- 100 次 rollout 中所有步骤 RL 梯度非零；最终 adapter 496 个张量均有限且相对 SFT v2 都发生变化；reference 指纹未变。
- 总 wall time 1,526.66 秒，峰值 allocated 显存 13.418 GiB。
- 训练 rollout reward 为训练过程信号，不能代替固定验证集。见按任务摘要文件；texture 长答案存在更高生成成本和少量截断。

Adapter SHA-256：

```text
67d050b2e0feee8db8738148a599e6a4fa4db0a6eea5aed95962fbb75ed4a6a2
```

父 SFT v2 SHA-256：

```text
fa4520f3e0b1e71d7a8cbae8b9973c127436769f4f79e96f36ad7afc1c8c1786
```

## 评测入口

```powershell
ollama create dawcoder-grpo-v3 -f D:\LLM\models\dawcoder-grpo-v3-export\Modelfile

Set-Location D:\LLM\dawcoder-datasets
D:\train\venv\Scripts\python.exe training\eval_dawcoder.py `
  --model dawcoder-grpo-v3 --limit 60 --seed 20261107 --num-predict 8192 `
  --out training\eval-report-grpo-v3.json
```

请沿用现有固定对比口径，并在评测侧生成 / 更新 `training/COMPARISON-REPORT.md`。
训练侧不会预断 GRPO v3 是否超过 SFT v2。

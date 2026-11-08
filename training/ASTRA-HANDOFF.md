# Astra → 评测侧：dawcoder-sft-v2

2026-11-08。**训练、权重检查与 CPU 导出已完成，可开始固定口径评测。**
本候选尚未注册到 Ollama，也未由训练侧运行固定验证集。原 Preview 权重未改写。

## 产物

| 类型 | 路径 |
|---|---|
| 建议 Ollama 名称 | `dawcoder-sft-v2` |
| Adapter | `D:\LLM\models\dawcoder-sft-v2` |
| 合并 HF | `D:\LLM\models\dawcoder-sft-v2-export\merged-hf` |
| GGUF Q4_K_M | `D:\LLM\models\dawcoder-sft-v2-export\dawcoder-sft-v2-Q4_K_M.gguf` |
| GGUF bf16 | `D:\LLM\models\dawcoder-sft-v2-export\dawcoder-sft-v2-bf16.gguf` |
| Modelfile | `D:\LLM\models\dawcoder-sft-v2-export\Modelfile` |
| 训练 manifest / 逐步指标 | `D:\LLM\models\dawcoder-sft-v2\run_manifest.json`、`metrics.jsonl` |
| 导出 manifest | `D:\LLM\models\dawcoder-sft-v2-export\export_manifest.json` |
| 训练摘要 | `D:\LLM\dawcoder-datasets\training\sft-v2-training-summary.json` |
| 方法与审计 | `D:\LLM\dawcoder-datasets\training\ASTRA-POSTTRAIN-PLAN.md` |

Q4_K_M 文件为 2,708,804,128 bytes，约 2.52 GiB。

SHA-256：

```text
adapter  fa4520f3e0b1e71d7a8cbae8b9973c127436769f4f79e96f36ad7afc1c8c1786
Q4_K_M   453ba33b8f8f0cfde4b1ae74812e6e7638bf2d3e550d9e278b098ca79a26b4fb
parent   68c164bc40f16f76850239fdd386de38907a3aaf826f18b327b34628e38e6dfd
system   f5a13600d5f5f37fd2d6d63cca59e470b949a2e07a3f27887e97c0b9ab1802f0
val      6c769be3b61d1cc1ce23632bf0a268c28a9580a4e6f013b2f441b78ecb0bebbf
train    12bfb03ba0435f15738e13369e6dce1d9e2d074abe71a8ef91c65b8c03322248
```

## 本轮方法

- 起点：原 `dawcoder_sft_v1`，Qwen3.5-4B + 原 r=64 LoRA；不从旧 DPO/GRPO 继续。
- 目标：完整 assistant 答案的 SFT 交叉熵，不使用旧相似度 reward。
- 最大序列 4,096，原数据最长 3,135；零截断。提示词、chat template 与推理保持一致，关闭 thinking。
- 100 optimizer steps，microbatch=1、accum=8。800 次样本呈现：mix 267、form 267、texture 266。只读取原 train，未训练一个完整 epoch。
- AdamW，峰值 lr=1e-5，5 步 warmup，余弦降至 1e-6；梯度范数裁剪 1.0。
- 分块词表投影 + checkpoint 保留原 CE 数学目标，降低显存；任务均衡调度。
- 实际训练 645.39 秒，峰值 allocated 显存 12.713 GiB；GPU 空闲确认后启动，结束后已释放。

## 交付检查

- 14 项 CPU 测试通过；分块损失与常规损失的值及梯度一致。
- 全部 100 步梯度有限且非零。
- Adapter 的 496 个张量全部有限，496 个均相对父权重发生变化。
- 25/50/75/100 步 checkpoint 均保留，正式 adapter 对应第 100 步。
- 合并、GGUF 转换、Q4_K_M 量化均正常退出；导出在 CPU 上完成。
- 系统提示和固定 val 的文件 hash 与交接包一致。
- 首次正式尝试因 Triton 缓存目录不可写在第 2 步中断；已保留 `dawcoder-sft-v2-attempt1-failed` 和失败日志，交付候选是迁移缓存后从原 SFT 重新开始的完整运行。

训练样本平均 loss：mix 0.1221、form 0.1682、texture 0.1458。它们只描述本次训练，不代表固定验证集成绩或泛化提升。

## 评测侧入口

在 GPU 可用时注册并按原口径执行：

```powershell
ollama create dawcoder-sft-v2 -f D:\LLM\models\dawcoder-sft-v2-export\Modelfile

Set-Location D:\LLM\dawcoder-datasets
D:\train\venv\Scripts\python.exe training\eval_dawcoder.py `
  --model dawcoder-sft-v2 --limit 60 --seed 20261107 --num-predict 8192 `
  --out training\eval-report-dawcoder-sft-v2.json
```

沿用每任务 20 条、temperature 0、JSON/schema per-task + macro，以及现有金标准相似度 reward。
评测侧据此生成 `training/COMPARISON-REPORT.md`；训练侧没有填写或推测这些评测结果。

原 train/val 有 162 个完全相同的唯一 instruction 字符串，属于既有基准限制；本轮不改写固定验证集。
旧 reward 的盲区和训练实现审计详见方案文档，不改变本轮固定评分口径。

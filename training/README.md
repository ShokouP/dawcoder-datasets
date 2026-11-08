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

评测器现在按任务内固定种子抽样，再轮流抽取三类任务。默认 `--limit 60`
选取 mix / form / texture 各 20 条；`--limit 0` 评测完整验证集；不足 3 条或
验证集缺少任一任务时会报错。报告含各任务失败原因、总体和宏平均合法率、输入文件 SHA-256。

只核对覆盖率，使用下面的 CPU 命令，不调用模型：

```bash
python training/eval_dawcoder.py --dry-run
python -m unittest discover -s training -p "test_*.py"
```

`training/patch_validation.py` 供评测器与合成数据校验器共用，检查目标轨道、
发送两端与反馈回路、必需字段、有限数值及单位范围、段落连续性与 marker 内容、
音符音域/力度/整数网格/重复音符/结尾越界。当前 IR 支持 4/4，EQ 为 1–7 段；
不支持的字段会被拒绝。参数合法率只代表当前 IR 的约束通过，不能证明音频质量
或真实 DAW 的插件映射正确，也不衡量自然语言意图是否被完全满足。

新增训练材料见 `../cpt/COLLECTION-REPORT.md`。`cpt/data-expanded/` 已准备统一
`text` 列的 CPT 文件；`data/symbolic/` 是带来源记录的真实演奏/结构标注，
需要相应训练任务与模型输入格式，不能直接混入当前三任务的 SFT 文件。

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

## Astra：完整答案 SFT 续训

2026-11-08 的审计与新方案见 [ASTRA-POSTTRAIN-PLAN.md](ASTRA-POSTTRAIN-PLAN.md)。
新训练入口为 `train_sft_complete.py`，不截断答案，三任务均衡，采用数值等价的
分块交叉熵减少显存占用。旧 DPO/GRPO 的问题及证据保存在该方案和
`posttrain-audit.json` 中。固定验证集和评测口径保持原样。

```powershell
# CPU：核对完整长度与系统提示
D:\train\venv\Scripts\python.exe training\train_sft_complete.py --prepare-only --output D:\LLM\models\dawcoder-sft-v2

# 单 GPU：入口会先检查显存与利用率；输出必须是新的运行目录
D:\train\venv\Scripts\python.exe training\train_sft_complete.py --output D:\LLM\models\dawcoder-sft-v2 --steps 100 --accum 8 --lr 1e-5

# CPU：训练完成后导出，不自动注册 Ollama，不运行固定验证集
D:\train\venv\Scripts\python.exe training\export_candidate.py --adapter D:\LLM\models\dawcoder-sft-v2 --out D:\LLM\models\dawcoder-sft-v2-export
```

具体运行结果与交付路径以 `ASTRA-HANDOFF.md` 为准；训练 loss 不能替代独立评测。

GRPO v3（从已评测 SFT v2 初始化）方法、奖励、组内采样及边界见
[ASTRA-GRPO-V3-PLAN.md](ASTRA-GRPO-V3-PLAN.md)。训练完成摘要见
`grpo-v3-training-summary.json`，评测侧交付见 `ASTRA-GRPO-V3-HANDOFF.md`。

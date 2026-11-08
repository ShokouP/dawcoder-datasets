# DAWcoder：Astra 后训练方案与审计

日期：2026-11-08。训练方案、实现和产物由本侧负责；固定验证集、评测脚本和评测口径由评测侧负责。本轮交付独立 adapter，建议导出模型名 `dawcoder-sft-v2`。

执行结果：100 步训练和 CPU 导出均已完成。实际用时、检查结果、adapter / HF / GGUF 路径与哈希见 [ASTRA-HANDOFF.md](ASTRA-HANDOFF.md)。固定质量评测由评测侧执行，当前不宣称优于 Preview。

## 决策

从 `D:\train\models\dawcoder_sft_v1` 做一轮保守的 **完整答案 SFT 续训**。先跑 3 步独立冒烟，再从原 SFT 起点跑 100 个 optimizer steps。冒烟权重不混入正式候选。

这轮主要修复完整答案监督缺失，保留三任务能力。现有结果不足以支持直接延长旧 DPO/GRPO，也不足以判断复杂算法是否有收益。额外 CPT 暂不进入这一轮。

## 已验证的依据

CPU 审计产物为 `posttrain-audit.json`；可用 `audit_posttraining.py` 重跑。原训练脚本位于 `D:\train\scripts`，本侧只读取，新的实现保存在本仓库。

1. **DPO policy 没有变化。** SFT adapter 与 DPO policy 的文件 SHA-256 完全一致，496 个张量均无变化：`68c164bc40f16f76850239fdd386de38907a3aaf826f18b327b34628e38e6dfd`。因此该次 DPO 导出不能作为偏好学习有效的证据。
2. **反向传播时 adapter 状态有误。** 旧 DPO 在 policy forward 后切到 ref，随后直接 backward；本机 PEFT 的 `set_adapter` 同时切换 `requires_grad`，checkpoint 重算还会使用当时的活动 adapter。微型 CPU 网络复现得到 policy 梯度为零；恢复 policy 后梯度与权重更新恢复，结果见 `dpo-gradient-probe.json`。这是机制复现，不冒充一次完整 Qwen 训练。
3. **reference 的文件差异有精度原因。** reference 的 496 个张量全部等于 SFT 张量经 FP32→BF16→FP32 的结果，不能把这些差异解释成 reference 被训练了。
4. **旧 GRPO 没有实际组成 G=4 的同题组。** 当前脚本 `group` 只用于损失除数；每个 prompt 调用一次单返回序列生成。日志 v1 为 30 steps / 30 rollouts，v2 为 40 / 40。默认每步一个 prompt 时，`reward - mean(rewards)` 为零；剩余更新来自其 KL 项，不能把 reward 均值变化直接归因于有效的组相对优化。
5. **旧 SFT 截断了大多数 texture 答案。** 本地 tokenizer 实测：1,330 / 1,620 条 texture 完整序列超过 1,536 tokens；657 条超过 2,048；最大 3,135。上下文 4,096 足以容纳当前所有完整训练样本。
6. **旧 DPO 输入也有截断。** 1,045 条 mix 偏好对中，838 条 prompt 被限制到前 512 tokens；1,571 条 texture 偏好对中，1,290 条 chosen 被截断，114 对截断后 token 序列相同。不可据此直接扩大步数或学习率。
7. **现有相似度 reward 有盲区。** CPU 反例中，EQ 从 400 Hz / -2.1 dB 改为 20 kHz / +2.1 dB、压缩 ratio 从 3 改为 20、send 从 -19.2 改为 -60 dB，仍得 1.0。form energy、texture velocity 改动也未被该相似度计入。评测侧继续用原口径；本侧不会把该 reward 直接用作训练目标。

GRPO v2 旧报告的请求失败属于服务可用性问题，须与输出质量分开解释。审计保存的是当时文件的 hash；评测侧可能更新原报告，应按对应版本追溯。

此外，原 train/val 存在 **162 个完全相同的 instruction 字符串**（唯一 prompt 交集数，不是重复行数）。这是一项既有数据划分限制；固定评测仍照交接口径执行，结果不能当作全新 prompt 的泛化分数。训练器仅读取原 train 文件，此轮不改写固定 val。

方法核对依据：[PEFT adapter 切换文档](https://huggingface.co/docs/peft/package_reference/peft_model)、[PyTorch 2.11 checkpoint 文档](https://docs.pytorch.org/docs/2.11/checkpoint.html)。DPO 指标须使用相对 reference 的偏好 margin，不能把原始 chosen/rejected logp 排序当作 DPO reward accuracy；见 [TRL DPO](https://huggingface.co/docs/trl/dpo_trainer)。GRPO 应对同题多个答案计算优势，KL 与截断处理按明确公式实现，见 [TRL GRPO](https://huggingface.co/docs/trl/grpo_trainer)。

## 本轮参数

| 项 | 选择 |
|---|---|
| 基座 | 本地 Qwen3.5-4B，bf16 |
| 初始 adapter | `D:\train\models\dawcoder_sft_v1` |
| 数据 | 原 3,240 条 train；不读固定 val 用于训练 |
| 系统提示 | 与 `preview/system_prompt.txt` 的正文完全一致；文件 hash 写入 manifest |
| 训练格式 | 原 chat template，`enable_thinking=False`，只监督完整 assistant 答案及结束符 |
| 样本处理 | 不截断；超出上限直接报错；验证训练/推理的 prompt token 前缀一致 |
| 最大序列 | 4,096；实际逐样本 padding 到 64 的倍数 |
| Loss | 每个答案的 token 平均交叉熵；分块计算词表投影，数学目标不变 |
| 分块大小 | 128 tokens；checkpoint 重算投影，降低峰值显存 |
| LoRA | 继承原 r=64 / alpha=128 / dropout=0.05 / 原 target modules |
| 优化器 | AdamW，betas=(0.9, 0.95)，weight_decay=0，clip_grad_norm=1 |
| 学习率 | 峰值 1e-5，前 5 步 warmup，余弦降至 1e-6 |
| batch / 累积 | 单卡 microbatch=1，accum=8 |
| 步数 | 100，即 800 次样本呈现；不是一个完整 epoch |
| 任务配比 | mix 267 / form 267 / texture 266；各任务独立洗牌，无需因答案长删除任务 |
| 随机种子 | 20261108 |
| Checkpoint | 每 25 步；保留 adapter、optimizer 与 RNG 状态 |
| 正式输出 | `D:\LLM\models\dawcoder-sft-v2` |
| 冒烟输出 | `D:\LLM\models\dawcoder-sft-v2-smoke` |

当前数据每个任务都足够，800 次呈现的计划不会在任务内部重复抽样。manifest 记录实际 input hash 顺序，便于复现。

## 运行前后的检查

- GPU 启动条件：连续两次读取利用率 ≤5%、显存占用 ≤1,024 MiB；检查失败时不加载模型。该检查不提供跨进程资源锁。此次外部观察也已从 80% 利用率下降至 0%、约 86 MiB。
- 不终止其他工作，不改写旧权重；新产物全部写入 `D:\LLM\models`。
- CPU 检查：分块 CE 与普通 CE 的 loss、hidden gradient、head gradient 数值一致；任务调度可复现且均衡。
- 准备阶段：3,240 条样本全部可编码，最大 3,135 tokens，零截断，系统提示匹配。
- GPU 冒烟：覆盖 mix/form/texture，检查有限非零梯度、首步 adapter 更新、完整保存、峰值显存。
- 正式运行：逐步记录任务 loss、梯度范数、学习率、显存峰值；非有限 loss/梯度、零梯度或首步无更新立即失败。
- 最终交付检查：adapter 与父权重不同，文件可读，记录完整 SHA-256、实际步数、用时和产物路径。训练 loss 不作为泛化提升的证明。

首次正式尝试在第 2 步因用户目录下 Triton 缓存不可写中断，已保留失败记录。运行缓存随后移到本仓库 `_tmp/posttrain/runtime-cache`，正式候选从原始 SFT adapter 重新初始化。

## 评测交接

评测侧使用原固定口径：val 60 均衡（每任务 20），seed 20261107，temperature 0，num_predict 8192；保持系统提示和校验器一致。交回 adapter、manifest 和训练 notes 后，由评测侧生成 `eval-report-<model>.json` 与 `COMPARISON-REPORT.md`。

本轮训练不改写旧评测报告，不依据固定 val 调训练样本，也不将 schema 合法率等同于音乐语义或听感改善。

若继续做偏好训练，前置工作是冻结可验证的 reference、确认 policy 梯度流向、消除截断/同对样本、建立明确意图约束的负例与分任务语义奖励。若再用 GRPO，必须先验证每题确有多个 rollout、非零组内 reward 方差、正确的逐 token 目标，以及三任务均被覆盖。真实 DAW 音频奖励须先统一 IR 映射并确认真实渲染；当前 mock 闭环仅能验证管线。

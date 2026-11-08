# Astra：GRPO v3

2026-11-08。起点为评测已完成的 `dawcoder-sft-v2`，不继承旧 GRPO adapter。
固定评测脚本、数据和评分口径保持原样。本文件描述训练目标，不是质量评测结果。

## 方法

- 同一个 prompt 实际采样 4 个答案，`num_return_sequences=4`，逐题计算组内优势；禁止用不同题目的答案拼成一组。
- 生成批次可调整，但同题总样本数始终为 4。显式启用 KV cache 和 `logits_to_keep=1`，逐次断言 prefill 后只输入 1 个新 token。每 256 tokens 记录进度并释放过多的闲置 CUDA 缓存，避免长序列预留缓存挤占显存。
- 采样 temperature=0.8、top_p=1、top_k=0、repeat_penalty=1；old/current/reference logp 都先把 logits 除以相同温度，与实际采样分布对齐。
- token 级 clipped surrogate，clip=0.2；loss 以本组有效 completion token 总数归一化（BNPO）。
- KL 使用非负 k3 估计 `exp(ref_logp - policy_logp) - (ref_logp - policy_logp) - 1`，系数 0.05。
- 组内标准差下限 0.02，避免把随机力度等微小分数差放大。无组内信号时重选同任务 prompt，至多 3 次；不伪造有效 GRPO 更新。
- 超过生成预算且没有 EOS 的答案不进入 loss；至少两个完整答案且 reward 标准差 >1e-6 才更新。
- 参考 adapter 从 SFT v2 初始化，并在加载后逐张量从 policy 精确复制，消除 BF16 中转误差。全部 ref 打分在 policy backward 图建立前完成；backward 期间保持 policy 活动。
- reference 不进优化器、不接收梯度，训练前后比较全部参考参数的 SHA-256。
- policy/ref/old 打分都关闭 dropout。逐次检查 current 与 old token logp 的差异，避免训练和行为概率不一致。
- 每次 GRPO 更新额外做一条其他任务的完整答案 SFT 回放，权重 0.1，防止已有任务能力漂移。

公式及归一化实现核对本机 TRL 0.24.0 源码和 [该版本官方 GRPO 文档](https://huggingface.co/docs/trl/v0.24.0/en/grpo_trainer)。训练实现使用本仓库的显存受控分块 token logp，不更换环境依赖。

## 数据与奖励

只读取原 train（mix 1,080 / form 540 / texture 1,620），不读取固定 val。

三类任务均使用原始完整训练样本。texture 覆盖 5 个样式：16 分琶音、8 分分解、柱式、固定音型、长音，按样式轮换。
完整答案 SFT 回放也使用原任务。

首次三任务冒烟曾试用新构造的两小节 texture，发现该组 4 个答案只有 1 个 schema 合法、2 个被生成预算截断。
虽然三步均有真实的非零 RL 梯度且 reference 未变，短片段任务与现有模型能力分布仍不匹配。
因此正式候选撤回该变换，改回原始完整 texture，并将采样温度从 1.0 降至 0.8；增加一个完整 texture 的专项 GPU 冒烟。
实验代码仍保留 `--compact-texture`，默认关闭，正式运行不启用。

完整 texture 的首次四路试跑曾观察到显存接近 24 GB、明显减速，因此主动停止并保留日志。
随后以两路生成验证缓存：约 3,000 tokens 时实际分配约 9.1 GiB，而预留缓存约 16 GiB，说明闲置缓存累积显著。
新实现增加缓存有效性检查、闲置缓存释放与 token 进度记录；正式阶段仍保证同题 4 个样本，不把批次大小当作组大小。

新的 `grpo_reward.py` 只用于训练：先检查 JSON 和共享 schema，再按任务计算相似度。
mix 显式计入 EQ 的 band/type/freq/gain/q、压缩参数、send 两端与 gain，以及多余/缺失操作；
form 计入段落顺序、起点、长度、能量/密度与 tempo；texture 计入音符位置/音高、时值，给力度较低权重。
JSON 错误得 0、schema 错误得 0.05，合法答案得 `0.3 + 0.7 × similarity`。

这仍然是相对金标准的训练代理目标，不代表听感或真实 DAW 音频质量，也不与固定评测的旧 reward 数值混报。

## 配置与阶段

| 项 | 值 |
|---|---|
| 基座 | Qwen3.5-4B bf16，原 r=64 LoRA |
| 初始化 | `D:\LLM\models\dawcoder-sft-v2` |
| 冒烟 | 3 steps，mix/form/texture 各 1，G=4 |
| 正式训练 | 从未改动的 SFT v2 重新开始，24 optimizer steps，每任务 8 组 |
| Rollouts | 正式至少 96；无信号重选会额外采样，全部落盘 |
| 学习率 | 峰值 1e-6，3 步 warmup，余弦降至 1e-7 |
| 优化器 | AdamW betas=(0.9,0.95)，weight_decay=0，grad clip=1 |
| 最大上下文 | 4,096；prompt、gold 均不截断 |
| 生成预算 | 每题按完整 gold token 长度加 256，向上取 128 倍数，受总上下文约束 |
| 分块 logp | 128 tokens，checkpoint 重算；计算目标不变 |
| 种子 | 20261109 |
| Checkpoint | 每 6 步保存 policy、optimizer 和 RNG |
| 正式候选 | `D:\LLM\models\dawcoder-grpo-v3` |
| 导出候选名 | `dawcoder-grpo-v3` |

用户再次明确授权使用 GPU 后，已确认残余进程为 QQ 和 Codex 桌面程序。启动检查允许 ≤25% 的桌面利用率，仍要求显存占用 ≤1,024 MiB，连续两次满足才加载模型；不终止其他进程。运行文件和缓存全部放在 `D:\LLM`。

## 验收与交付

CPU 测试检查金标准满分、参数错误降分、全部 texture 样式裁剪后仍合法、组内优势、KL 非负、策略梯度方向、分块 logp/梯度等价性。
GPU 冒烟必须证实每题确有 4 个 rollout、非零组内优势、非零独立 RL 梯度、policy 权重变化、reference 保持不变。
逐步保存 reward、优势、KL、RL 梯度、回放 loss、显存、完整采样文本。

最终交付 adapter、CPU 合并 HF、Q4_K_M GGUF、原系统提示的 Modelfile、manifest 和交接说明。
评测侧按既定协议评测，不预先认定 GRPO 优于 SFT v2。

## 正式运行记录（2026-11-08）

24 步已完成，wall time 1,526.66 秒，峰值 allocated 显存 13.418 GiB。三任务各 8 步，共 25 个同题组 / 100 次 rollout（其中一次 mix 因无组内差异重采样）。99/100 rollout 完整且 schema 合法；1 次 texture 输出到预算上限仍未结束，因此排除在该组 RL loss 外。texture 更新仍由 3 个完整有效答案计算，并配合完整 SFT 回放。全部 24 步有非零 RL 梯度，采样策略与训练策略 token logp 差为 0，reference 首尾指纹一致。

训练候选 SHA-256：`67d050b2e0feee8db8738148a599e6a4fa4db0a6eea5aed95962fbb75ed4a6a2`；parent 为评测通过的 SFT v2。各任务训练时组平均 reward、有效率和 adapter 路径写入 `grpo-v3-training-summary.json`。这些是优化过程记录，不是 val 结果，也不能代替独立评测。完整 GGUF 与交评测侧命令将在 `ASTRA-GRPO-V3-HANDOFF.md`。

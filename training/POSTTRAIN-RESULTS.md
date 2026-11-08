# DAWcoder 后训练（DPO + GRPO）结果

日期：2026-11-08 | 基座：Qwen3.5-4B (LoRA r=64) | 起点：`dawcoder-preview` 的 SFT adapter (`dawcoder_sft_v1`)

## 1. DPO

| 项 | 值 |
|---|---|
| 数据 | `D:\train\data\dpo-dawcoder\dpo_train.jsonl`：3,143 对偏好样本（chosen = 金标准 patch；rejected = 合理但错误：错轨 / 越界值 / 反向 / 错 op / 截断） |
| 参考策略 | 冻结的 SFT adapter（同初始权重） |
| 配置 | seq 1024，lr 5e-6，β=0.1，accum 8，150 steps，约 40 分钟（17.3s/step） |
| 训练曲线 | loss 稳定在 ~0.693，偏好准确率 acc 0.925–1.0（均值 ≈0.97） |
| 产物 | `D:\train\models\dpo_dawcoder_v1\policy`；Ollama `dawcoder-dpo`（Q4_K_M 2.5GB） |
| Schema 评测（60 条均衡） | **60/60 合法（100%）**，与 SFT 相同 |

## 2. GRPO

| 项 | 值 |
|---|---|
| 起点 | DPO adapter（policy），冻结同权重 reference，KL β=0.02 |
| 奖励 | 0.2 JSON 解析 + 0.35 schema 合法 + 0.45 与金标准 patch 相似度（mix 值距离 / form 段名+bars / texture note 重合） |
| Prompt 池 | 423 条（mix 218 / form 205；texture 因金标准输出过长未纳入） |
| 配置 | 30 steps × G=4 rollouts，max_new 512，lr 5e-6，约 7 分钟（14s/step） |
| 训练曲线 | reward 0.968–1.0（均值 **0.968**），valid_rate 1.0 |
| 产物 | `D:\train\models\grpo_dawcoder_v1\policy`；Ollama `dawcoder-grpo`（Q4_K_M 2.5GB） |
| Schema 评测（60 条均衡） | **54/60 合法（90%）**：mix 20/20，form 20/20，texture **14/20（bad-bar 6）** |

## 3. 三模型对比（Ollama 实跑，val 60 条均衡，reward = JSON+schema+金标准相似度，temperature 0）

| 模型 | mix valid / reward | form valid / reward | texture valid / reward | overall valid / reward |
|---|---|---|---|---|
| **dawcoder-preview（SFT）** | 100% / 0.9097 | 100% / 0.9933 | 100% / 0.9940 | **100% / 0.9657** |
| dawcoder-dpo | 100% / 0.9097 | 100% / 0.9933 | 100% / 0.9940 | **100% / 0.9657** |
| dawcoder-grpo | 100% / **0.9240** ↑ | 100% / 0.9915 ≈ | **55% / 0.6393** ↓ | 85% / 0.8516 ↓ |

（数值与 `training/compare-posttrain.json` 一致；schema 合法率来自 `eval-report-{preview,dpo,grpo}.json`）

## 4. 结果记录

- **DPO**：训练对为 SFT 模型已能正确回答的样本，chosen/rejected 已高度分离；本轮 loss 恒 ~0.693、偏好 acc 0.97；导出后 schema 与 SFT 相同。
- **GRPO（v1）**：prompt 池未含 texture（金标准输出远超 max_new 512）；导出后 mix reward +0.014、texture 出现 bad-bar（schema 90%）。
- **结论（仅针对本轮模型）**：`dawcoder-preview`（SFT）仍是当前最佳可用版本；DPO/GRPO 作为实验分支保留。

## 5. 边界说明

以上仅为**本次运行的评测事实**。后续训练方案（数据、算法、超参、导出）由 Astra 决定，评测侧不做训练建议。

## 6. 产物清单

| 产物 | 路径 |
|---|---|
| DPO adapter | `D:\train\models\dpo_dawcoder_v1\policy` |
| DPO merged / GGUF | `D:\train\models\dawcoder-dpo_merged`、`dawcoder-dpo-Q4_K_M.gguf` |
| GRPO adapter | `D:\train\models\grpo_dawcoder_v1\policy` |
| GRPO merged / GGUF | `D:\train\models\dawcoder-grpo_merged`、`dawcoder-grpo-Q4_K_M.gguf` |
| DPO 评测 | `training/eval-report-dpo.json` |
| GRPO 评测 | `training/eval-report-grpo.json` |
| 对比数据 | `training/compare-posttrain.json` |
| 日志 | `D:\train\runs\dawcoder_dpo.log`、`dawcoder_grpo.log`、`dawcoder_compare.log` |

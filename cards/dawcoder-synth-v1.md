# DAWcoder Synthetic Starter v0.1

## 概览
- 3,600 条合成训练样本（mix 1,200 / form 600 / texture 1,800），train 90% / val 10%。
- 两种格式：结构化 JSONL（state/intent/patch/expected）与 chat JSONL（system/user/assistant）。
- 生成器：`synthetic/generate.py`（seed=20261107，可逐字节复现）；校验器：`synthetic/check.py`。

## 许可
- **CC0-1.0**：自建、无第三方素材，可商用、可再分发、无需署名。
- 证据：本仓库（captured 2026-11-07，reviewer: shokoup）
- 注意：仅数据本体 CC0；生成器/校验器代码为 Apache-2.0。

## 引用
DAWcoder contributors, "DAWcoder Synthetic Starter Dataset v0.1", 2026.

## 已知问题
- 合成数据只覆盖"格式 + 任务映射"，不代表真实混音审美与音频分布。
- 意图模板有限（每类 1–3 句），需要真实用户语料补充。
- texture 的和弦外音比例恒为 0（规则生成），后续版本会加入经过音。
- 不能替代 L1–L5 真实/授权数据；商用训练集只能用 T0/T1 数据。

# DAWcoder 模型对比报告

生成时间：2026-11-08 17:50

评测协议：`training/EVAL-PROTOCOL.md`（val 60 条均衡，seed 20261107，temperature 0，num_predict 8192）

| 模型 | 报告 | 可靠 | JSON 解析 | schema 合法 | macro | mix | form | texture | reward(overall) |
|---|---|---|---|---|---|---|---|---|---|
| dawcoder-dpo | eval-report-dpo.json | ✅ | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.9657 |
| dawcoder-grpo-v3 | eval-report-grpo-v3.json | ✅ | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.9710 |
| dawcoder-preview | eval-report-preview.json | ✅ | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.9657 |
| dawcoder-sft-v2 | eval-report-sft-v2.json | ✅ | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.9710 |
| dawcoder-grpo | eval-report-grpo.json | ✅ | 100.0% | 90.0% | 90.0% | 100.0% | 100.0% | 70.0% | 0.8516 |
| dawcoder-grpo-v2 | eval-report-grpo-v2.json | ⚠️ 请求错误多 | 35.0% | 30.0% | 30.0% | 40.0% | 35.0% | 15.0% | - |

## 回归检查（相对基线 `dawcoder-preview`）

- **dawcoder-dpo**：无退化，通过
- **dawcoder-grpo-v3**：无退化，通过
- **dawcoder-sft-v2**：无退化，通过
- **dawcoder-grpo**：schema 合法率下降 10.0 个百分点；texture 合法率下降 30.0 个百分点；reward 下降 0.1141

## 说明

- 标 ⚠️ 的报告存在 >10% request-error（Ollama 服务中断），数据不可用于对比，需重跑。
- reward 来自 `compare-posttrain*.json`（如有），为与金标准 patch 的相似度（0~1）。
- 可发布标准：JSON 解析 ≥99%、schema ≥98%、无单任务 <95%、相对基线无 >5pp 退化。

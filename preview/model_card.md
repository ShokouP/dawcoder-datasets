# DAWcoder Preview — Model Card（草稿，发布前填充评测结果）

## 摘要

- **模型**：`dawcoder-preview`（DAWcoder Preview v0.1）
- **基座**：Qwen3.5-4B（Apache 2.0）
- **类型**：音乐制作参数生成（不是音频生成）
- **输入**：`{"task":"mix|form|texture","state":{...},"intent":"..."}`
- **输出**：JSON patch（`ops` / `sections`+`markers` / `notes`）
- **许可**：Apache 2.0（基于 Qwen3.5-4B，保留原许可与版权声明）

## 训练

| 阶段 | 数据 | 配置 |
|---|---|---|
| CPT | DAWcoder CPT Corpus v0.3 curated（~24.2M tokens：SE sound/music/avp + 精选公版乐理/声学书 + arXiv 摘要 + 自建手册） | 4B LoRA r=64, seq 1024, 400 steps, bf16, 单卡 5090 24GB |
| SFT | DAWcoder Synthetic v0.1（3,240 条 chat：mix 1,080 / form 540 / texture 1,620） | LoRA r=64, seq 1536, 1 epoch, lr 5e-5 |

## 使用

```bash
ollama create dawcoder-preview -f preview/modelfile
```

system prompt 见 `preview/system_prompt.txt`；采样参数 temperature 0 / top_p 0.95 / num_ctx 16384 / num_predict 2048。

## 评测（待填）

| 指标 | 结果 |
|---|---|
| JSON 解析率 | __% |
| mix schema 合法率 | __% |
| form schema 合法率 | __% |
| texture schema 合法率 | __% |
| 平均输出 tokens | __ |

## 已知限制

- 预览版：仅合成任务数据 SFT，真实工程泛化有限；
- 参数建议需人工确认；第三方插件参数映射未覆盖；
- 中文意图支持有限；
- 不生成音频，不替代混音师判断。

## 数据与许可

- 训练数据：`synthetic/`（CC0）+ `cpt/`（CC BY-SA 4.0 / 公版 / MIT），逐源署名见 `cpt/data/ATTRIBUTIONS.md`；
- 模型权重：衍生自 Qwen3.5-4B，按 Apache 2.0 发布并保留声明。

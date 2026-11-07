# DAWcoder Preview — Model Card（v0.1 预览版）

## 摘要

| 项 | 内容 |
|---|---|
| 模型 | `dawcoder-preview`（DAWcoder Preview v0.1） |
| 基座 | Qwen3.5-4B（Apache 2.0） |
| 类型 | 音乐制作参数生成（**不是**音频生成） |
| 输入 | `{"task":"mix\|form\|texture","state":{...},"intent":"..."}`（JSON） |
| 输出 | JSON patch：`{"ops":[...]}` / `{"sections":[...],"markers":[...]}` / `{"notes":[...]}` |
| 产物 | LoRA adapter、merged bf16 HF、GGUF bf16 / **Q4_K_M (2.5GB)**、Ollama 模型 `dawcoder-preview` |
| 许可 | Apache 2.0（继承 Qwen3.5-4B，保留原许可与版权声明） |

## 训练

| 阶段 | 数据 | 配置 | 结果 |
|---|---|---|---|
| **CPT** | Open Music Production & Audio Engineering Corpus **v1.0**：72,080 docs / 37.1M tokens（Stack Exchange sound/music/avp、公版乐理/和声/对位/配器/总谱分析教材、Grove 词典、中文维基音乐条目、arXiv 摘要、开放音频工程文档） | Qwen3.5-4B + LoRA r=64 all-linear，seq 1024，400 steps，lr 1e-4，accum 16，bf16，单卡 5090 24GB | train_loss **2.67 → 2.57**（78 分钟，12 s/step） |
| **SFT** | DAWcoder Synthetic v0.1：3,240 条 chat（mix 1,080 / form 540 / texture 1,620） | 从 CPT adapter 初始化（`--init-adapter`），LoRA r=64，seq 1536，1 epoch（200 optimizer steps），lr 5e-5，accum 16 | train_loss **0.153**（51 分钟，15.3 s/step） |

导出链路：merge LoRA → bf16 GGUF（7.9GB）→ **Q4_K_M（2.5GB）** → `ollama create dawcoder-preview`（system prompt + num_ctx 16384 / temp 0 / top_p 0.95 / num_predict 2048）。

## 评测（验证集 60 条，mix/form/texture 各 20，balanced round-robin）

| 指标 | 结果 |
|---|---|
| JSON 解析率 | **100%** |
| patch schema 合法率 | **100%** |
| macro valid rate | **100%** |
| mix / form / texture | **20/20 · 20/20 · 20/20** |
| coverage | validation 任务覆盖完整 |

> 评测口径：`training/eval_dawcoder.py`（Ollama 实跑、`--limit 60`），校验 JSON 解析 + 任务 schema/参数范围。**不等于**混音语义质量；语义/听感需人工 A/B 与工程闭环验证。

### 手动样例（temperature 0）

- **mix**：输入「Drum Bus 音量 -0.3」类意图 → `{"ops":[{"op":"set_track","track":"Drum Bus","fields":{"volume_db":-0.4}}]}`（期望 -0.3，误差 0.1dB）
- **form**：EDM 意图 → Intro/Build/Drop/Break/Drop 结构，bars 与 energy/density 合理，schema 合法
- **texture**：琶音织体 → 每步 note 序列，bar/step/key/len_steps/vel 均在范围内

## 使用

```bash
ollama create dawcoder-preview -f preview/modelfile   # 如未创建
ollama run dawcoder-preview
```

必须带 `preview/system_prompt.txt` 作为 system prompt（模型在该 prompt 下训练，缺失会导致输出格式漂移）。
采样：temperature 0.0 / top_p 0.95 / num_ctx 16384 / num_predict 2048。

## 已知限制

- 预览版仅用**合成任务数据** SFT，真实工程泛化有限；参数建议需人工确认；
- 第三方插件参数映射未覆盖（当前为抽象 ops：set_track / set_eq / set_comp / set_send / add_marker）；
- 中文意图支持有限（SFT 以英文/JSON 为主，中文语料只进 CPT）；
- 不会生成音频，也不替代混音师判断；
- 评测只覆盖 schema 合法性，未做语义/听感评测。

## 数据与许可

- 训练数据：`synthetic/`（CC0）+ `cpt/` 语料（CC BY-SA 4.0 / 公版 / MIT），逐源署名见 `cpt/data/ATTRIBUTIONS.md`；
- 模型权重：衍生自 Qwen3.5-4B，按 Apache 2.0 发布并保留声明；
- 受版权内容（REAPER/FL Studio 手册等）不在训练语料中。

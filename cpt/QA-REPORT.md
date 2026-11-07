# CPT 语料质量评估报告（v0.2 broad → v0.3 curated）

> 结论：**v0.2（55M tokens）是"大而不精"的宽口径音乐语料；v0.3 curated（24.2M tokens）才适合作为 DAWcoder 预览版的 CPT 语料。**
> 质量提升：DAW/制作关键词（严格）覆盖率 **37.0% → 46.7%**，Gutenberg 版权页残留 **7.6% → 0.5%**，Stack Exchange 占比 **44% → 64%**。

## 1. 评估方法

- 对 `corpus_train.jsonl` 全量扫描（106,119 docs），统计：来源分布、语言、长度、DAW/制作关键词（严格词表：equaliz/compressor/reverb/plugin/DAW/MIDI/LUFS/headroom/sidechain 等，去掉 track/sound 等泛词）、boilerplate（Project Gutenberg/CC 声明/链接）、重复 12-gram。
- 抽样人工阅读每源 3 条。
- 对照 Gutenberg 官方目录 `pg_catalog.csv` 核对匹配依据。

## 2. 发现的问题（v0.2）

| 问题 | 证据 |
|---|---|
| **Gutenberg 匹配严重跑偏** | 关键词 `opera/music/song/sound` 命中了 Bookshelves 的 "Opera"、"Category: Music"、"Songs"；实际下载到 *War and Peace*、*Jean-Christophe*（"Musicians -- Fiction"）、*The Modern Scottish Minstrel*、Byron 诗集等。30.35M tokens（占 55%）大多与制作无关。 |
| **Stack Exchange 结构偏** | music SE 16.34M tokens 主要是演奏/乐理问题（翻谱页、钢琴调律），制作类只占一部分；sound SE 4.67M、avp 3.11M 才更贴生产。 |
| **arXiv 噪声** | 短语搜索未真正生效，混入 "Automatic Mixed-Precision Quantization of BERT" 等 ML 论文。 |
| **Boilerplate** | Gutenberg 7.6% 文档含 PG 版权页/校对者文本；SE 7.5–13.6% 文档含 CC 声明/外链。 |
| **近似去重缺失** | full 规模（>2 万文档）时 SimHash 被跳过，仅有精确去重（105 条）。 |
| **中文≈0** | 中文仅 32 docs（<0.1%）；zhwiki/维基文库 429 限速导致无法扩充。 |
| **缺现代工程文档** | REAPER/FL 手册受版权限制无法入库；无插件文档、无真实工程/参数数据。 |

## 3. 修复（curate.py）

1. **Gutenberg 严格过滤**：用目录元数据排除 fiction/novel/poetry/song-texts/libretto（`-- Fiction`、`Poetry`、`Songs ... -- Texts`），要求乐理/和声/对位/声学/录音/乐器教学/调律等非虚构主题；每本书字符上限 50 万；剔除含 PG 版权页的块。
2. **SE 清洗**：丢弃 <400 字符短帖；链接 >4 的丢弃；music SE 只保留制作关键词（mix/record/master/EQ/compress/reverb/plugin/DAW/MIDI…）帖。
3. **arXiv 过滤**：要求音频/混音关键词，剔除 quantization/BERT/LLM/NLP 噪声。
4. **HTML 清洗**：DAWproject Reference.html 等去标签。
5. **分块与 doc_type**：Gutenberg 3k–12k 字符块；来源标签保留 `source/license/url`。

## 4. 修复前后对比（train split）

| 指标 | v0.2 broad | v0.3 curated |
|---|---|---|
| docs | 106,119 | 57,728 |
| chars | 216.0M | 94.7M |
| 估算 tokens | 54.0M | 23.7M |
| DAW/制作关键词覆盖（严格） | 37.0% | **46.7%** |
| Gutenberg docs / tokens | 10,013 / 30.3M | 2,619 / 8.0M |
| SE sound+music+avp tokens | 24.1M（44%） | 15.6M（**64%**） |
| Gutenberg boilerplate 占比 | 7.6% | **0.5%** |
| SE music docs 的 DAW 覆盖 | 20.7% | 32.6% |

**v0.3 curated 实际构成（24.24M tokens）**：SE sound 5.04M + music 7.02M + avp 3.51M + Gutenberg（音乐理论/声学/教学）8.01M + arXiv 0.35M + 自建手册 0.24M + zh 0.05M。

## 5. 结论与建议

- ✅ **v0.3 curated 适合预览版 CPT**：现代制作语料占 64%，理论/声学补充合理，boilerplate 已清。
- ⚠️ 仍缺"现代 DAW 操作细节"：受版权手册不能入库；建议后续用**私有语料**（本地手册、工作室操作日志）补，公开版靠 SE/arXiv/OER。
- ⚠️ 中文仍是硬缺口：需要 zhwiki dumps 或授权中文教材（v0.4 处理）。
- 📌 策略：**v0.2 broad 保留为公开宽口径 release**；**v0.3 curated 用于训练预览版**；后续版本再扩现代文档与中文。
- 训练决策：以 curated 24M tokens 做 4B LoRA CPT（seq 1024，400 步预览），再 SFT 3,600 条 synthetic 数据，评测后导出 GGUF。

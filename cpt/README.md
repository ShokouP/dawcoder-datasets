# DAWcoder CPT 语料（继续预训练数据库）v0.1

面向 **Qwen3.5-4B 继续预训练（CPT）** 的领域语料：音频工程 / 混音 / DAW 工程格式 / 乐理 / 编曲。

## 当前构建（v0.1，2026-11-07）

- 3,295 篇文档 / 4,040,546 字符 / 估算 **1,030,857 tokens**
- 来源分布：Stack Exchange sound 1,494 篇 + music 708 篇 + avp 236 篇、arXiv 摘要 237 篇、DAWproject 规范 3 篇、自建参数手册 617 篇
- Wikipedia：本次因 429 限速跳过（`wikipedia-audio` 为 optional 源），后续用 dumps 或分批补充

## 设计原则

1. **只收录可再分发来源**（T0/T1）进公开语料；REAPER/FL 手册等受版权内容只做 fetch-only 私有源，不进仓库。
2. 每个文档保留 `source` / `license` / `tier` / `url` 字段，语料自带溯源。
3. 可复现：`fetch.py` 抓原始 → `build.py` 清洗/去重/切分 → `check.py` 校验，manifest 带 sha256。
4. 与 SFT 数据（`synthetic/`）分开：本目录是**无监督文本**，用于 CPT；SFT 是 `state/intent/patch` 对齐样本。

## 源与许可

| 源 | 许可 | 内容 |
|---|---|---|
| `wikipedia-audio` | CC BY-SA 4.0 | 音频工程/效果器/压缩/EQ/混响/混音/DAW/乐理条目全文 |
| `stackexchange-sound` | CC BY-SA 4.0 | 录音/混音/母带/EQ/压缩/混响问答（问题+答案正文） |
| `stackexchange-music` | CC BY-SA 4.0 | 乐理/作曲/编曲问答 |
| `dawproject-spec` | MIT | DAWproject 规范、XSD、示例 |
| `dawcoder-ir-handbook` | CC0 1.0 | 自建：任务说明 + patch 语义 + 示例转写 |

仅本地/私有（需自行获取，不入公开语料）：`reaper-user-guide`、`flstudio-manual`（T2）。

## 用法

```bash
pip install pyyaml
python cpt/fetch.py --source all        # 抓公开源（约几分钟，受 API 限速）
python cpt/build.py                     # 构建公开语料
python cpt/check.py                     # 校验（CI 会跑）
```

产出：

```
cpt/data/corpus_train.jsonl   # 98%
cpt/data/corpus_val.jsonl     # 2%
cpt/data/manifest.json        # 版本、sha256、计数、估算 tokens
cpt/data/stats.md             # 分布统计
cpt/data/ATTRIBUTIONS.md      # 逐源署名与许可声明
```

## 接入 CPT（Qwen3.5-4B LoRA）

- 训练前用 Qwen 分词器实测 tokens（`manifest.est_tokens` 只是估算）；
- 建议 domain : general replay ≈ 1 : 0.1–0.3，防止灾难性遗忘；
- 文档级拼接后 `max_seq_len=2048`，packing 会改变样本边界，注意与定长 padding 的兼容；
- 每轮用 `synthetic/` 的 SFT 验证集 + 通用回放评测守门。

## 已知问题

- v0.1 是**管道验证版**，规模有限（见 `data/stats.md`）；正式 CPT 前需要扩展 fetch-only 私有源（手册、论坛、教材）或采购授权语料。
- CC BY-SA 4.0 有**相同方式共享**要求，公开语料按 CC BY-SA 分发；模型权重是否受 SA 约束存在法律争议，商用发布前请法务确认。
- Stack Exchange 内容按 CC BY-SA 使用，语料中保留帖子 URL 与作者字段。
- Wikipedia 为英文条目；中文术语覆盖需补充中文源（后续版本）。
- `dawcoder-ir-handbook` 由 SFT 样本转写，与 SFT 有重叠，CPT 时可按需降采样。

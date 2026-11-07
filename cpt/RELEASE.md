# DAWcoder CPT Corpus v0.2

继续预训练（CPT）语料完整版，作为本 Release 的附件发布（仓库内只保留 lite 版）。

## 规模

| 指标 | 值 |
|---|---|
| 文档数 | **108,353**（train 106,119 / val 2,234） |
| 字符数 | **220,616,427** |
| 估算 tokens | **~55,194,118**（约 5500 万） |
| 语言分布 | 英文 107,998 / 中英混合 323 / 中文 32 |
| 长度分位 | p50 805 / p90 5,302 / p99 11,998 字符 |
| 去重 | 精确重复 105（近似去重因规模跳过） |

## 来源与贡献

| 源 | 许可 | 文档 | 估算 tokens |
|---|---|---|---:|---:|
| stackexchange-music | CC BY-SA 4.0 | 61,743 | 16.34M |
| stackexchange-sound | CC BY-SA 4.0 | 21,783 | 4.67M |
| stackexchange-avp | CC BY-SA 4.0 | 12,735 | 3.11M |
| gutenberg-music | 公版（Project Gutenberg） | 10,225 | 30.35M |
| arxiv-audio | CC0（元数据） | 1,209 | 0.37M |
| dawcoder-ir-handbook | CC0 | 617 | 0.24M |
| zh-wikipedia-audio | CC BY-SA 4.0 | 32 | 0.05M |
| zh-wikisource-music | 公版 | 6 | 0.07M |
| dawproject-spec | MIT | 3 | 0.01M |

## 下载

```bash
gh release download cpt-v0.2 -R ShokouP/dawcoder-datasets -D cpt/data-full
cd cpt/data-full && for f in *.gz; do gunzip -k "$f"; done
```

或直接用 URL：
`https://github.com/ShokouP/dawcoder-datasets/releases/download/cpt-v0.2/corpus_train.jsonl.gz`

## 校验和

| 文件 | 大小 | sha256 |
|---|---|---|
| corpus_train.jsonl.gz | 90.7 MB | `fcf46e5da365105bd2c840e8ce919329ca36e5bb55ea35369f194e0a6d8365ec` |
| corpus_val.jsonl.gz | 2.0 MB | `020979e00d04f112bc83e64ee5ccce04cfb9a990ee97cdae538448dbd6cc56f1` |
| manifest.json.gz | 779 B | `9bc42fe2e81344800b5253c9d693fed9839730e65f7231fbd73bb750a251ad22` |
| stats.md.gz | 761 B | `ed50692f6c3d6d82ba64978911f7d131333351daad9251dd8397e7441769fdf5` |
| ATTRIBUTIONS.md.gz | 880 B | `8b9c1a73472a4329eadc0703154a3176db604d35dbf46a15683841ef3449fc9a` |

## 许可

- **CC BY-SA 4.0**（Stack Exchange / Wikipedia 部分）+ **公版**（Gutenberg / Wikisource）+ **MIT**（DAWproject）+ **CC0**（自建手册）。
- Stack Exchange 内容版权归各贡献者，语料记录保留帖子 URL 与作者；Wikipedia 保留条目链接。
- 受版权内容（REAPER / FL Studio 手册）**不在**本语料中。
- CC BY-SA 的相同方式共享是否传导到模型权重存在争议，商用前请法务确认。

## 用法（Qwen3.5-4B CPT）

- 文档按块（3k–12k 字符）组织，可直接按行读取、自行 `max_seq_len` 截断/打包；
- full 版约 5,500 万 tokens，4B LoRA 在单卡 5090 24GB 上按 1,500 tok/s 估算约 **10 小时/epoch**；
- 建议 domain : general replay ≈ 1 : 0.1–0.3，防止灾难性遗忘；
- 训练前用 Qwen 分词器实测 token 数（manifest 里是估算）。

## 已知限制

- **中文占比过低**（<0.1%）：中文维基/维基文库限速严重，本轮未能扩展；建议 v0.3 用 zhwiki dumps 或授权中文教材补齐。
- Gutenberg 语料偏 19 世纪及以前，与现代 DAW 实践有代差，靠 Stack Exchange / arXiv 平衡。
- Stack Exchange 为问答体，建议与教材/文档类按 1:1 配比使用。
- 英文 Wikipedia 因 429 限速本次跳过。

# DAWcoder CPT Corpus v0.7（含中文维基补充）

继续预训练语料完整版（含中文），作为本 Release 附件发布。仓库内只保留 lite 语料与构建脚本。

## 规模

| 指标 | 值 |
|---|---|
| 文档数 | **71,627**（train 70,231 / val 1,396） |
| 字符数 | **120,729,147** |
| 估算 tokens | **~32,083,379** |
| 语言分布 | 英文 69,982 / 中文 1,263 / 中英混合 382（**中文 token 约 11.2%**） |
| 许可分类 | share-alike 65,644 docs（CC BY-SA）/ permissive 5,983 docs（CC0/PD/MIT/ISC） |
| 去重 | 移除 64,950 条重复；无重复、无同源跨集 |

## 构成

| 源 | 许可 | 说明 |
|---|---|---|
| stackexchange-sound / music / avp | CC BY-SA 4.0 | 混音/母带/录音/乐理问答（官方数据转储） |
| gutenberg-music | 公版 | 乐理/声学/乐器/歌唱类公版书（精选） |
| **zh-wikipedia-dump** | CC BY-SA 4.0 | **中文维基百科音频/音乐条目（1,294 docs / 3.58M tokens）** |
| zh-wikipedia-audio | CC BY-SA 4.0 | 中文维基音频术语条目 |
| arxiv-audio | CC0（元数据） | 混音/分离/响度/空间音频等论文摘要 |
| 11 个开放文档仓库 | MIT / ISC / CC0 | sfz / librosa / mido / pretty-midi / pyloudnorm / sounddevice / audioflux / pyroomacoustics / clap / windows-midi / sonic-pi 教程 |
| dawproject-spec | MIT | DAWproject 规范 |
| dawcoder-ir-handbook | CC0 | 自建参数语义手册 |

## 文件与校验和

| 文件 | 大小 | sha256 |
|---|---|---|
| corpus_train.jsonl.gz | 56.5 MB | `9c77f0e9f96c62ca6018d7929de31b72f22b04a0ecd3fb083a0a49fcd22c5dd4` |
| corpus_val.jsonl.gz | 1.1 MB | `2466827fc434664697fdc34c39912af74efe60a134ca4f0ba9360569df72a7b1` |
| cpt_train_text.jsonl.gz | 49.3 MB | `ab6b6784011dec6b3fd18986b010c8efb2170f86266bc6cf2c9601ac40e38684` |
| cpt_val_text.jsonl.gz | 0.9 MB | `80f0942a8efcb249501c581ef8276c61a3765fb72d93c118f8ede94ac7a1acc9` |
| manifest.json.gz | 1.5 KB | `b008ef263b29e7cee472980362431842a544860c8258d2dd54a0972e70b04c15` |
| stats.md.gz | 1.1 KB | `d7773bae9fbf3bb0f85f2103735daaaa44b1ad6b4aea6eed6e7d1b45437406fa` |
| ATTRIBUTIONS.md.gz | 1.8 KB | `5bc0abb26eb6ce7b604c17ad08013bec5528de5059b201d4ce38ca8585374721` |
| MERGE-REPORT.md.gz | 1.2 KB | `a1a7349468b09e06bf7b01e8ee8670be71caebdc61100568e52f8120f32d081b` |
| ZHWIKI-REPORT.md.gz | 2.0 KB | `ab045e1a7d09ef9c5976a461a6ee533fce5c7dece81dd9c73da4d65d9330cf52` |
| licenses.tar.gz | 5.3 KB | `5162917753a4ad78136cb4a07d4de50ef4aa8834f7d0295c8292ed06bd4fe5f0` |

下载与解压：

```bash
gh release download cpt-v0.7 -R ShokouP/dawcoder-datasets -D cpt/data-v0.7
cd cpt/data-v0.7 && for f in *.gz; do gunzip -k "$f"; done
```

## 构建与复现（全部开源）

- 中文维基下载/解析：`cpt/fetch_zhwiki_dump.py`
- 中文二次清洗与相关性筛选：`cpt/clean_zhwiki_raw.py`
- 中文语料转统一格式：`cpt/zhwiki_to_corpus.py`
- 多方语料合并（去重/分组切分）：`cpt/merge_corpora.py`
- 质量报告：`cpt/ZHWIKI-REPORT.md`、`cpt/MERGE-REPORT.md`、`cpt/QA-REPORT.md`

## 许可

- **CC BY-SA 4.0**（Stack Exchange / Wikipedia / Sonic Pi 教程）+ **公版**（Gutenberg）+ **MIT/ISC/CC0**（开放文档与自建手册）。
- 逐源署名见 `ATTRIBUTIONS.md` 与 `licenses.tar.gz`；中文维基每篇保留标题与永久链接。
- 商用训练请使用 permissive 子集（`data-permissive` 或在语料上按 `license_class` 过滤）。
- 受版权内容（REAPER / FL Studio 手册）**不在**本语料中。

## 已知限制

- 中文 token 占比 ~11%，以音乐领域文本（乐理/乐器/录音/音频技术/音乐人作品）为主，现代 DAW 操作细节仍缺；
- 中文维基只扫了 64 万页（全量约 150 万页），后续版本可继续扩；
- wikitext 清洗为启发式，仍有少量残缺句；
- Stack Exchange 为问答体，建议与教材/文档类按 1:1 配比使用。

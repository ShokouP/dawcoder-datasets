# CPT 语料统计

- 语料版本：`dawcoder-cpt-v0.2`（public，预算 56,000,000 tokens）
- 文档数：**108353**（train 106119 / val 2234）
- 字符数：**220,616,427**；估算 tokens：**55,194,118**
- 语言分布：中文 32 / 英文 107998 / 中英混合 323
- 长度分位（字符）：p50 805 / p90 5,302 / p99 11,998
- 去重：精确重复 105 / 近似重复 0（近似去重因规模跳过）

| 源 | 许可 | 文档 | 字符 | 估算 tokens |
|---|---|---:|---:|---:|
| arxiv-audio | CC0-1.0 | 1209 | 1,475,890 | 368,519 |
| dawcoder-ir-handbook | CC0-1.0 | 617 | 862,365 | 237,322 |
| dawproject-spec | MIT | 3 | 34,336 | 8,583 |
| gutenberg-music | Public-Domain | 10225 | 121,409,806 | 30,348,714 |
| stackexchange-avp | CC-BY-SA-4.0 | 12735 | 12,459,478 | 3,110,123 |
| stackexchange-music | CC-BY-SA-4.0 | 61743 | 65,448,789 | 16,339,129 |
| stackexchange-sound | CC-BY-SA-4.0 | 21783 | 18,700,768 | 4,667,029 |
| zh-wikipedia-audio | CC-BY-SA-4.0 | 32 | 101,989 | 47,727 |
| zh-wikisource-music | Public-Domain | 6 | 123,006 | 66,972 |

> 估算方式：CJK 字符 / 1.6 + 其他字符 / 4。正式训练前用 Qwen 分词器实测。

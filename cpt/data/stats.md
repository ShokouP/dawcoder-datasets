# CPT 语料统计

- 语料版本：`dawcoder-cpt-v0.2`（public，预算 3,000,000 tokens）
- 文档数：**6736**（train 6591 / val 145）
- 字符数：**12,826,927**；估算 tokens：**3,269,259**
- 语言分布：中文 15 / 英文 6400 / 中英混合 321
- 长度分位（字符）：p50 761 / p90 3,263 / p99 11,998
- 去重：精确重复 6 / 近似重复 0（近似去重已启用）

| 源 | 许可 | 文档 | 字符 | 估算 tokens |
|---|---|---:|---:|---:|
| arxiv-audio | CC0-1.0 | 60 | 79,859 | 19,942 |
| dawcoder-ir-handbook | CC0-1.0 | 617 | 862,365 | 237,322 |
| dawproject-spec | MIT | 2 | 33,284 | 8,320 |
| gutenberg-music | Public-Domain | 549 | 6,514,247 | 1,628,363 |
| stackexchange-avp | CC-BY-SA-4.0 | 821 | 668,780 | 166,891 |
| stackexchange-music | CC-BY-SA-4.0 | 3458 | 3,505,678 | 875,122 |
| stackexchange-sound | CC-BY-SA-4.0 | 1210 | 1,003,772 | 250,481 |
| zh-wikipedia-audio | CC-BY-SA-4.0 | 13 | 35,936 | 15,846 |
| zh-wikisource-music | Public-Domain | 6 | 123,006 | 66,972 |

> 估算方式：CJK 字符 / 1.6 + 其他字符 / 4。正式训练前用 Qwen 分词器实测。

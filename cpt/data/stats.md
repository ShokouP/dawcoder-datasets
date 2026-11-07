# CPT 语料统计

- 语料版本：`dawcoder-cpt-v0.3-curated`（public，预算 3,000,000 tokens）
- 文档数：**7177**（train 7014 / val 163）
- 字符数：**11,695,803**；估算 tokens：**2,956,010**
- 语言分布：中文 17 / 英文 6838 / 中英混合 322
- 长度分位（字符）：p50 852 / p90 2,588 / p99 11,997
- 去重：精确重复 1 / 近似重复 2（近似去重已启用）

| 源 | 许可 | 文档 | 字符 | 估算 tokens |
|---|---|---:|---:|---:|
| arxiv-audio | CC0-1.0 | 146 | 176,358 | 44,036 |
| dawcoder-ir-handbook | CC0-1.0 | 617 | 862,365 | 237,322 |
| dawproject-spec | MIT | 2 | 59,924 | 14,981 |
| gutenberg-music | Public-Domain | 351 | 4,203,575 | 1,050,763 |
| stackexchange-avp | CC-BY-SA-4.0 | 1529 | 1,408,199 | 351,479 |
| stackexchange-music | CC-BY-SA-4.0 | 2172 | 2,813,323 | 702,525 |
| stackexchange-sound | CC-BY-SA-4.0 | 2338 | 2,111,385 | 526,956 |
| zh-wikipedia-audio | CC-BY-SA-4.0 | 22 | 60,674 | 27,948 |

> 估算方式：CJK 字符 / 1.6 + 其他字符 / 4。正式训练前用 Qwen 分词器实测。

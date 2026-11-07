# CPT 语料统计

- 语料版本：`dawcoder-cpt-v0.1`（public）
- 文档数：**3295**（train 3233 / val 62）
- 字符数：**4,040,546**；估算 tokens：**1,030,857**

| 源 | 许可 | 文档 | 字符 | 估算 tokens |
|---|---|---:|---:|---:|
| arxiv-audio | CC0-1.0 | 237 | 284,128 | 70,946 |
| dawcoder-ir-handbook | CC0-1.0 | 617 | 862,365 | 237,322 |
| dawproject-spec | MIT | 3 | 34,336 | 8,583 |
| stackexchange-avp | CC-BY-SA-4.0 | 236 | 232,417 | 58,013 |
| stackexchange-music | CC-BY-SA-4.0 | 708 | 1,156,029 | 288,738 |
| stackexchange-sound | CC-BY-SA-4.0 | 1494 | 1,471,271 | 367,255 |

> 估算方式：CJK 字符 / 1.6 + 其他字符 / 4。正式训练前用 Qwen 分词器实测。

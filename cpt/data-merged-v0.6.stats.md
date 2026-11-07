# 合并语料统计

- 语料版本：`dawcoder-cpt-v0.6-merged`
- 输入：zhwiki-corpus, data-expanded, data-curated, data-permissive
- 文档数：**74,198**（train 72,748 / val 1,450）
- 字符数：**138,925,803**；估算 tokens：**41,351,261**
- 语言分布：中文 3411 / 英文 70010 / 中英混合 777
- 许可分类：{'share-alike': 68215, 'permissive': 5983}
- 去重：移除重复 64,950 条（按 text_sha256）
- 长度分位：p50 946 / p90 3,672 / p99 11,997

| 源 | 文档 | 字符 | 估算 tokens | 许可 |
|---|---:|---:|---:|---|
| arxiv-audio | 1169 | 1,405,757 | 351,004 | CC0-1.0 |
| audioflux-docs | 186 | 244,774 | 61,162 | MIT |
| clap-docs | 1 | 8,588 | 2,147 | MIT |
| dawcoder-ir-handbook | 617 | 862,365 | 237,322 | CC0-1.0 |
| dawproject-spec | 2 | 59,924 | 14,981 | MIT |
| gutenberg-music | 2683 | 32,036,091 | 8,008,046 | Public-Domain |
| librosa-docs | 295 | 563,246 | 140,693 | ISC |
| mido-docs | 16 | 8,679 | 2,164 | MIT |
| pretty-midi-docs | 37 | 26,382 | 6,584 | MIT |
| pyloudnorm-docs | 7 | 8,647 | 2,159 | MIT |
| pyroomacoustics-docs | 243 | 254,210 | 63,460 | MIT |
| sfz-format-docs | 222 | 435,977 | 108,913 | CC0-1.0 |
| sonic-pi-tutorial | 90 | 341,376 | 90,429 | CC-BY-SA-4.0 |
| sounddevice-docs | 5 | 13,466 | 3,365 | MIT |
| stackexchange-avp | 12645 | 14,089,846 | 3,517,761 | CC-BY-SA-4.0 |
| stackexchange-music | 30821 | 41,185,035 | 10,284,739 | CC-BY-SA-4.0 |
| stackexchange-sound | 20762 | 20,206,646 | 5,043,929 | CC-BY-SA-4.0 |
| windows-midi-docs | 500 | 2,070,491 | 517,444 | MIT |
| zh-wikipedia-audio | 32 | 101,989 | 47,727 | CC-BY-SA-4.0 |
| zh-wikipedia-dump | 3865 | 25,002,314 | 12,847,232 | CC-BY-SA-4.0 |

> tokens 为字符估算（CJK/1.6 + 其他/4），训练前请用 Qwen 分词器实测。

# 语料合并报告（MERGE-REPORT）

- 输出：`D:\train\data\dawcoder-merged-v0.7`
- 版本：`dawcoder-cpt-v0.7-merged`
- 结果：**71,627 docs / 120,729,147 chars / ~32,083,379 tokens**（train 70,231 / val 1,396）
- 输入规模：zhwiki-corpus-v2: 1,294 docs / ~3.6M tok；data-expanded: 70,333 docs / ~28.5M tok；data-curated: 58,972 docs / ~24.2M tok；data-permissive: 5,978 docs / ~9.5M tok
- 去重移除：64,950 条重复（含 permissive 与 expanded 的重叠部分）
- 语言：{'zh': 1263, 'mixed': 382, 'en': 69982}
- 许可分类：{'share-alike': 65644, 'permissive': 5983}

## 输入对照

| 输入 | docs | ~tokens |
|---|---:|---:|
| zhwiki-corpus-v2 | 1,294 | 3.58M |
| data-expanded | 70,333 | 28.50M |
| data-curated | 58,972 | 24.24M |
| data-permissive | 5,978 | 9.51M |

## 合并后逐源

| 源 | docs | ~tokens | 许可 |
|---|---:|---:|---|
| arxiv-audio | 1,169 | 0.351M | CC0-1.0 |
| audioflux-docs | 186 | 0.061M | MIT |
| clap-docs | 1 | 0.002M | MIT |
| dawcoder-ir-handbook | 617 | 0.237M | CC0-1.0 |
| dawproject-spec | 2 | 0.015M | MIT |
| gutenberg-music | 2,683 | 8.008M | Public-Domain |
| librosa-docs | 295 | 0.141M | ISC |
| mido-docs | 16 | 0.002M | MIT |
| pretty-midi-docs | 37 | 0.007M | MIT |
| pyloudnorm-docs | 7 | 0.002M | MIT |
| pyroomacoustics-docs | 243 | 0.063M | MIT |
| sfz-format-docs | 222 | 0.109M | CC0-1.0 |
| sonic-pi-tutorial | 90 | 0.090M | CC-BY-SA-4.0 |
| sounddevice-docs | 5 | 0.003M | MIT |
| stackexchange-avp | 12,645 | 3.518M | CC-BY-SA-4.0 |
| stackexchange-music | 30,821 | 10.285M | CC-BY-SA-4.0 |
| stackexchange-sound | 20,762 | 5.044M | CC-BY-SA-4.0 |
| windows-midi-docs | 500 | 0.517M | MIT |
| zh-wikipedia-audio | 32 | 0.048M | CC-BY-SA-4.0 |
| zh-wikipedia-dump | 1,294 | 3.579M | CC-BY-SA-4.0 |

## 使用建议

- **预览版 CPT / 研究**：用合并版（share-alike 为主，含 SE/Wikipedia/Sonic Pi 教程）。
- **商用训练**：用 `cpt/data-permissive`（仅 CC0/PD/MIT/ISC 等白名单），或在合并版上按 `license_class` 过滤掉 share-alike。
- 中文仍偏少（见语言分布）；待 zhwiki dump 完成后补入。


# PDMX（Public Domain MusicXML）

## 概览
- 25 万+ 首公有领域 MusicXML（来自 MuseScore 公有领域条目），含 MIDI、PDF、MusicRender JSON；14.4GB。
- 用途：织体/编曲/声部写作的**商用安全**主力符号数据。

## 许可
- **公有领域**（作者按 public domain 发布；引用论文）。
- 证据：https://zenodo.org/records/15571083 （captured 2026-11-07，reviewer: shokoup）
- ⚠️ 12.29%（31,221 首）存在站点与文件内部许可不一致 → **只用 `no_license_conflict` 子集（222,856 首）**。

## 引用
Long, Novack, Berg-Kirkpatrick, McAuley, "PDMX: A Large-Scale Public Domain MusicXML Dataset for Symbolic Music Processing", ICASSP 2025.

## 已知问题
- 抓取自用户上传内容，个别条目仍可能有人工核查风险；商用前建议按 `license_conflict` 与评分再抽样复核。
- MusicXML 到 MIDI 的转换会丢失演奏法信息，训练时保留 MusicRender 的 annotations。
- 与流行歌 MIDI 数据集风格分布不同（古典/改编居多），需要做风格重加权。

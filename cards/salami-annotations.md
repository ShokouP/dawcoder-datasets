# SALAMI structural annotations

## 概览
- 约 2,000+ 首音乐的段落边界/标签标注（公开一半，另一半留作 MIREX 测试）。
- 用途：曲式结构训练/评测的标注基座。

## 许可
- **CC0 1.0**（公有领域贡献，可自由使用、可商用、无需署名，但请引用）。
- 证据：https://ddmal.ca/research/salami/annotation/ （captured 2026-11-07，reviewer: shokoup）

## 引用
Smith, Burgoyne, Fujinaga, De Roure, Downie, "Design and creation of a large-scale database of structural annotations", ISMIR 2011.

## 已知问题
- **只含标注，不含音频**；音频需从 Internet Archive 逐条获取并核对权利（多为可公开访问的历史录音，但权利状态不一）。
- 标注有少量笔误/格式不一致；用官方解析脚本。
- 隐藏一半数据，公开部分做训练、自建测试集要用独立来源。

## 本地采集与预处理（2026-11-07）

官方仓库：https://github.com/DDMAL/salami-data-public ，其 README 明确数据采用 CC0。

`python tools/collect_symbolic.py --source salami-annotations` 下载固定 commit 的官方快照，
将公开的 functions 层时间边界解析为 `data/symbolic/salami-annotations/sections_{train,val,test}.jsonl`。
同一 song ID 的所有标注者保持在同一切分；采用固定 SHA-256 的 90/5/5 分组切分。
快照 commit、压缩包 SHA-256 与输出校验和记录在 `registry/symbolic.lock.json`。
时间保留为秒；没有推断音频、BPM、小节或自然语言意图。

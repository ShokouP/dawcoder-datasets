# Lakh MIDI Dataset v0.1

## 概览
- 176,581 个去重 MIDI（LMD-full）；matched 45,129 个对齐到 Million Song Dataset。
- 用途：织体/风格统计、参数先验、MIDI 侧的合成数据种子。

## 许可
- **CC BY 4.0**（可再分发、可商用，需署名，数据集级）。
- 证据：https://colinraffel.com/projects/lmd/ （captured 2026-11-07，reviewer: shokoup）

## 引用
Colin Raffel, "Learning-Based Methods for Comparing Sequences, with Applications to Audio-to-MIDI Alignment and Matching", PhD Thesis, Columbia University, 2016.

## 已知问题
- 上游是受版权歌曲的网页转录：数据集许可覆盖数据集本身，但**生成端要防复现旋律**（加 MIDI n-gram 指纹过滤）。
- 含少量损坏文件，加载前做有效性校验。
- Slakh、MidiCaps 均派生自本数据集 → 必须统一 song-level split（`md5`）。

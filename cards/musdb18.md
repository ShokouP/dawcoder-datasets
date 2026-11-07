# MUSDB18

## 概览
- 150 首完整歌曲，含 stereo mixture 与 4 个 stems（drums/bass/other/vocals），Native Instruments stems 格式；train 100 / test 50。
- 用途：**只做评测基准**（混音指标、分轨质量、参考匹配）。

## 许可
- **Other (Non-Commercial)**：仅教育/研究用途，未经版权方许可不得商用。
- 组成：100 首来自 Cambridge-MT "Mixing Secrets"；46 首来自 MedleyDB（CC BY-NC-SA 4.0）；2 首 Native Instruments；2 首 The Easton Ellises（CC BY-NC-SA 3.0）。
- 证据：https://zenodo.org/records/1117372 （captured 2026-11-07，reviewer: shokoup）

## 引用
Rafii, Liutkus, Stöter, Mimilakis, Bittner, "The MUSDB18 corpus for music separation", 2017. DOI: 10.5281/zenodo.1117372

## 已知问题
- **不可商用、不可再分发**；fetch 时须 `--accept-license`。
- 与 MedleyDB 有 46 首重叠；跨库切分要合并 `group_key`。
- 4-stem 粒度不足以评估"织体/编曲"，只适合混音指标。
- 由压缩格式（AAC 256k）封装，不要拿它当无损训练源。

## 预处理建议
- 用 `stempeg` 解码；评测前统一响度对齐（EBU R128）。
- 评测结果与训练数据严格隔离：构建 `--profile commercial` 时必须过滤掉本数据集。

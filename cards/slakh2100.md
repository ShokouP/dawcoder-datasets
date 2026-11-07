# Slakh2100

## 概览
- 2,100 首合成多轨（由 Lakh MIDI 用专业音源渲染），105GB FLAC，44.1kHz/16bit，每首至少 4 个 source，覆盖 187 个音色/34 类乐器。
- 用途：混音任务的主力合成数据、参数-指标闭环、MIDI-音频对齐评测。
- 获取：`python tools/fetch.py slakh2100 --dest D:/data --accept-license`（也可直接从 Zenodo 下载）。

## 许可
- **CC BY 4.0**（可再分发、可商用，需署名）。
- 证据：https://zenodo.org/records/4599666 （captured 2026-11-07，reviewer: shokoup）
- 署名：Manilow, Wichern, Seetharaman, Le Roux, "Cutting Music Source Separation Some Slakh", WASPAA 2019。

## 引用
```
@inproceedings{manilow2019cutting,
  title={Cutting Music Source Separation Some {Slakh}: A Dataset to Study the Impact of Training Data Quality and Quantity},
  author={Manilow, Ethan and Wichern, Gordon and Seetharaman, Prem and Le Roux, Jonathan},
  booktitle={Proc. IEEE WASPAA},
  year={2019}
}
```

## 已知问题
- `omitted/` 目录含重复 MIDI 的曲目，训练转谱模型时不要用。
- 与 Lakh MIDI、MidiCaps 同源（Lakh MD5）：切分必须按 `group_key: lakh_md5` 合并分组，避免 train/test 泄漏。
- 由采样器渲染，**不是真实录音**：真实混音分布需要补 Cambridge-MT / MedleyDB（T2，仅研究）。
- 渲染混音是自动混合，不是专业混音参考。

## 预处理建议
- 统一转 48kHz/24bit 或 44.1kHz/32float 再进镜像渲染链。
- 保留 `metadata.yaml`（乐器、音色、MIDI 路径），作为参数先验与条件标签。
- 只取 `train/` 与 `test/` 官方划分前，先按 `group_key` 重新分组。

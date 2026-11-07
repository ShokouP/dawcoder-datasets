# DAWcoder Synthetic Starter v0.1

**可直接用于 SFT 的合成训练集**（CC0-1.0），由 `generate.py` 可复现生成。

## 规模

| 文件 | 行数 | 说明 |
|---|---|---|
| `data/{task}_{split}.jsonl` | 3600 | 结构化样本（train 90% / val 10%） |
| `data/sft_{task}_{split}.jsonl` | 3600 | chat 格式（system / user / assistant），直接喂 SFT |
| `data/manifest.json` | — | 版本、种子、sha256、行数 |

- mix：1080 train / 120 val
- form：540 / 60
- texture：1620 / 180
- 随机种子：`20261107`；重跑生成器可得到逐字节一致的结果

## 三类任务格式

### mix（工程状态 + 意图 → 混音参数补丁）

```json
{"task":"mix","state":{"genre":"pop","tempo":120,"tracks":[{"name":"Lead Vocal","role":"vocal","volume_db":-8.0,"pan":0.0,"sends":[{"to":"Plate Reverb","gain_db":-14.0}]}],"buses":[...]},
 "intent":"Lead Vocal 被鼓盖住了，帮我推出来一点，别太亮",
 "patch":{"ops":[{"op":"set_track","track":"Lead Vocal","fields":{"volume_db":-7.0}},
                 {"op":"set_eq","track":"Pad","band":2,"type":"bell","freq":315,"gain_db":-1.5,"q":1.0}]}}
```

patch ops 只有四类：`set_track`（volume_db/pan）、`set_eq`、`set_comp`、`set_send`。

### form（风格/时长约束 → 曲式结构方案）

```json
{"task":"form","state":{"genre":"house","tempo":124,"target_seconds":248},
 "intent":"做一首 house，速度约 124 BPM，总长约 248 秒；需要 drop 段落……",
 "patch":{"tempo":124,"time_signature":"4/4",
          "sections":[{"name":"Intro","start_bar":1,"bars":16,"energy":0.3,"density":0.3}, ...],
          "markers":[{"bar":1,"name":"Intro"}, ...]}}
```

### texture（和弦进行 + 织体意图 → MIDI 音符补丁）

```json
{"task":"texture","state":{"progression":["Cmaj7","G","Am7","F"],"style":"arp_16","range":["C3","C5"]},
 "intent":"Cmaj7 - G - Am7 - F 进行，用 16 分音符上行琶音，音域 C3–C5……",
 "patch":{"notes":[{"bar":1,"step":0,"key":60,"len_steps":1,"vel":82}, ...]}}
```

`step` 为 1/16 音符序号（0–15），`len_steps` 以 16 分音符为单位，`key` 为 MIDI 音高。

## 直接训练

见仓库根目录 [`training/README.md`](../training/README.md)：把 `data/sft_*_train.jsonl` 直接接入 LLaMA-Factory / ms-swift 等，assistant loss mask，LoRA 即可。

## 许可

- **CC0-1.0**（自建合成数据，无第三方素材，可商用、可再分发，无需署名）。
- 生成器与校验器代码：Apache-2.0。

## 已知问题（务必阅读）

- 这是**格式与流程的合成数据**，用来让模型学会"输出合法 patch/plan/notes"和任务映射；**不代表真实混音审美**。
- 真实音频/工程数据（L1–L5）必须按 `registry/datasets.yaml` 与 `DATASETS.md` 的许可规则另行获取，且不得混入商用训练集。
- 意图模板是有限的（每类问题 1–3 句）；真实用户语料需要 L5 操作日志补充。
- texture 的 `chord_tone_ratio` 恒为 1.0（生成规则限定），真实织体允许经过音，后续版本会加入。

## 复现

```bash
python synthetic/generate.py --seed 20261107   # 生成
python synthetic/check.py                     # 校验（CI 会跑）
```

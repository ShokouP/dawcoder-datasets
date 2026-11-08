# 2026-11-07 训练资料扩充与评测修复

全部采集、解析、构建与检查仅使用 CPU；未启动模型训练或模型推理。原有模型训练输入与新增版本使用独立目录。

## 评测修复

- 默认 60 条按固定种子均衡抽取 mix / form / texture 各 20 条；`--limit 0` 使用全量验证集。
- 共享补丁校验器覆盖轨道、发送两端与反馈回路、完整字段、有限数值与范围、段落连续性与 marker 内容、音符网格/音域/力度/重复/结尾边界。
- 输出逐任务失败原因、宏平均合法率、验证集 SHA-256；`--dry-run` 无需模型即可查看覆盖。
- 当前 IR 为 4/4；合法率衡量支持的参数契约，不等于音频质量、意图满足率或真实插件兼容性。

## 实际新增与构建结果

| 材料 | 本地规模 | 位置 |
|---|---:|---|
| 新采集开放文档 | 11 个官方仓库 / 1,637 篇 | `cpt/raw/<source>.jsonl` |
| 扩充版 CPT | 70,333 篇 / 28,504,029 估算 tokens | `cpt/data-expanded/` |
| 许可白名单 CPT | 5,978 篇 / 9,512,944 估算 tokens | `cpt/data-permissive/` |
| Groove MIDI | 1,150 段原始演奏，去重后 1,149 段 / 445,949 次击打 / 10,208 个两小节片段 | `data/symbolic/groove-midi/` |
| SALAMI | 1,359 首歌曲 / 2,243 份标注 / 30,336 个功能边界 | `data/symbolic/salami-annotations/` |

扩充版相对原本地 curated full（58,972 篇 / 24,237,576 估算 tokens）增加 11,361 篇，约 17.6% 估算 tokens。增长同时来自新文档与对已有清洗语料的更大构建预算；不是全部来自新抓取。11 个新源经清洗/去重后实际纳入 1,602 篇 / 998,520 估算 tokens。

两个 CPT 目录均包含 `corpus_{train,val}.jsonl`、`cpt_{train,val}_text.jsonl`、`manifest.json`、统计和署名文件。token 数按字符估算，未启动模型分词或训练。许可白名单只筛选 CC0 / Public-Domain / MIT / ISC / BSD / Apache 声明，不是额外的法律保证。

## 开放文档快照

| 官方来源 | 采集文档 | 许可 | 固定版本 |
|---|---:|---|---|
| [sfz-format-docs](https://github.com/sfz/sfz.github.io) | 235 | CC0-1.0 | `2f933f593895` |
| [librosa-docs](https://github.com/librosa/librosa) | 297 | ISC | `51a1c911c230` |
| [mido-docs](https://github.com/mido/mido) | 17 | MIT | `5bc189bdee90` |
| [pretty-midi-docs](https://github.com/craffel/pretty-midi) | 41 | MIT | `286326f165c1` |
| [pyloudnorm-docs](https://github.com/csteinmetz1/pyloudnorm) | 8 | MIT | `b8d67bfd3ce5` |
| [sounddevice-docs](https://github.com/spatialaudio/python-sounddevice) | 5 | MIT | `283f40d6ebde` |
| [audioflux-docs](https://github.com/libAudioFlux/audioFlux) | 190 | MIT | `0c3f55b409b0` |
| [pyroomacoustics-docs](https://github.com/LCAV/pyroomacoustics) | 253 | MIT | `08d16968f8db` |
| [clap-docs](https://github.com/free-audio/clap) | 1 | MIT | `a47f6badb49d` |
| [windows-midi-docs](https://github.com/microsoft/MIDI) | 500 | MIT | `d3947a3c3732` |
| [sonic-pi-tutorial](https://github.com/sonic-pi-net/sonic-pi) | 90 | CC-BY-SA-4.0 | `d1393a06266f` |

完整版本、逐文件 Git blob/SHA-256 与采集状态见 `cpt/open_docs.lock.json`。原始许可文本在 `cpt/licenses/`，构建时复制到输出目录。只采集配置白名单内的文本；Python 源码仅用 AST 读取 docstring，不导入或执行。Sonic Pi 教程按文档专用 CC BY-SA 4.0 许可处理。

## 真实数据的使用边界

- [Groove 官方数据与许可](https://magenta.tensorflow.org/datasets/groove)：CC BY 4.0。校验官方压缩包 SHA-256，保留官方 performance split、原始 tick、力度和 Roland TD-11 鼓音高映射；去除 1 段完全重复演奏。同一演奏的窗口保持在同一切分。
- [SALAMI 官方标注与许可](https://github.com/DDMAL/salami-data-public)：CC0。固定 commit `8e4f95d18a3ab628c53011fa5a43e9d3be27965d`；按 song ID 分组，使用固定 90/5/5 切分；同曲多标注者不会跨切分。
- `registry/symbolic.lock.json` 记录压缩包与输出文件哈希。原始数据及派生 JSONL 仅存放在被忽略的 `data/`，没有把第三方 MIDI 二进制提交到仓库。
- 这些材料可用于鼓序列与结构标注任务。没有虚构自然语言意图、音频、BPM 或小节标签，也没有将其直接并入三任务 SFT；当前 `texture` 是有音高音符 IR，鼓事件需要单独的训练任务/适配器。

## 复现与检查

```powershell
python -m pip install -r requirements.txt
python cpt/collect_open_docs.py --source all
python tools/collect_symbolic.py
python cpt/curate.py
python cpt/build.py --max-tokens 60000000 --raw-dir cpt/raw-curated --out cpt/data-expanded --corpus-name dawcoder-cpt-v0.4-expanded
python cpt/make_cpt_text.py cpt/data-expanded
python cpt/check.py --data cpt/data-expanded
python cpt/build.py --profile permissive --max-tokens 60000000 --raw-dir cpt/raw-curated --out cpt/data-permissive --corpus-name dawcoder-cpt-v0.4-permissive
python cpt/make_cpt_text.py cpt/data-permissive
python cpt/check.py --data cpt/data-permissive
python tools/check_symbolic.py
python tools/validate.py --strict
python synthetic/check.py
python training/eval_dawcoder.py --dry-run
python -m unittest discover -s training -p "test_*.py"
python -m unittest discover -s cpt -p "test_*.py"
python -m unittest discover -s tools -p "test_*.py"
```

命令会重用文档的已锁定版本与本地下载缓存。原有 Stack Exchange / Gutenberg 等原始语料的获取流程仍见 `cpt/README.md`；在干净机器复现完整扩充版前需要这些旧源，不能仅用新增文档重建全部语料。新脚本不调用 GPU。

## 校验与当前局限

- 回归测试覆盖抽样、畸形 JSON、范围/类型/发送回路、marker、音符边界、现有 3,600 条样本兼容性、文档分组、无执行提取、MIDI 微时序、数据泄漏和文件篡改。检查记录见 `training/verification-report.json`。
- 扩充版按原文档/书籍/帖子线程分组切分；保留翻译与源章节的分组关系。已做精确去重，70k 规模下现有近似去重仍按原逻辑跳过，已在 manifest 标记。
- 中文仍偏少：扩充版以字符占比判定有 28 篇中文、325 篇混合文档。正在其他任务中下载的维基 dump 未计入这次结果。
- MuseScore Handbook 的程序化抓取返回 HTTP 403；Ardour/Mixxx 候选手册缺少已确认的文档再利用许可，未收入。
- 此次没有跑模型推理，因此没有新模型准确率或听感提升的结论。


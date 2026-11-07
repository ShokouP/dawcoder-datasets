# dawcoder-datasets

DAWcoder 的数据仓库：**第三方数据不进仓库**（走 fetch 脚本），仓库里放的是**许可治理 + 可直接训练的自建合成数据**。

- 代码：Apache-2.0（`LICENSE`）
- 自建数据/标注：CC0-1.0（`LICENSE-data`）
- 第三方数据：一律 `tools/fetch.py`，按许可分档（T0–T3）

## 训练就绪的数据（本仓库内置）

| 文件 | 行数 | 说明 |
|---|---|---|
| `synthetic/data/sft_{mix,form,texture}_{train,val}.jsonl` | 3,600 | **chat 格式，直接喂 SFT** |
| `synthetic/data/{mix,form,texture}_{train,val}.jsonl` | 3,600 | 结构化样本（state/intent/patch/expected） |
| `synthetic/data/manifest.json` | — | 版本、种子、sha256、行数 |

三种任务：**mix**（工程状态+意图→混音参数 patch）、**form**（风格/时长→曲式结构）、**texture**（和弦进行→MIDI 音符）。  
训练教程见 [`training/README.md`](training/README.md)；数据卡见 [`synthetic/README.md`](synthetic/README.md)。

```bash
python synthetic/generate.py --seed 20261107   # 复现
python synthetic/check.py                     # 校验
```

## 继续预训练语料（CPT）

`cpt/` 提供 **Qwen3.5-4B 继续预训练**的领域文本语料（音频工程/混音/DAW 格式/乐理）：

| 版本 | 规模 | 位置 |
|---|---|---|
| lite（仓库内置） | 6,736 docs / ~3.27M tokens | `cpt/data/` |
| full（Release 附件） | ~108,000 docs / **~55M tokens** | GitHub Releases → `cpt-v0.2` |

```bash
gh release download cpt-v0.2 -R ShokouP/dawcoder-datasets -D cpt/data-full
python cpt/check.py                # 校验 lite 语料（CI 会跑）
```

构建方式：`cpt/fetch.py` / `cpt/fetch_se_dumps.py` 抓取 → `cpt/build.py` 清洗/去重/切分 → `cpt/check.py` 校验。
许可：CC BY-SA 4.0 + 公版 + MIT + CC0；受版权的 REAPER/FL 手册只做私有源，不入仓库。

## 目录

```
registry/datasets.yaml   # 第三方/自建数据集的唯一事实源（许可、任务、fetch）
registry/licenses.yaml   # SPDX → 档位/商用/再分发 映射
cards/<id>.md            # 数据卡（许可、引用、已知问题）
synthetic/              # 自建合成训练集 + 生成器 + 校验器
training/               # 直接用数据训练的说明与配置
cpt/                    # 继续预训练语料（fetch → build → data + manifest）
tools/fetch.py           # 下载 + sha256 + 条款确认（T2 必须 --accept-license）
tools/validate.py        # CI 校验（结构/许可/文件守卫）
fixtures/               # 极小 CC BY 派生样本（仅 CI 冒烟）
```

## 许可四档

| 档 | 定义 | 入仓 | 商用 |
|---|---|---|---|
| T0 | 自建 / CC0 / 公有领域 | ✅ | 视来源 |
| T1 | 可再分发但体积大（Slakh、Lakh、PDMX…） | ❌（fetch） | ✅ |
| T2 | 非商用/研究许可（MUSDB18、MedleyDB、MoisesDB、Cambridge-MT） | ❌（fetch + 接受条款） | ❌ |
| T3 | 许可不明/禁止再分发（GitHub .flp、FL demo） | ❌ | ❌ |

## 校验

```bash
pip install pyyaml jsonschema
python tools/validate.py --strict     # 注册表 + 许可 + 文件守卫
python synthetic/check.py             # 训练数据完整性
```

## 相关文档

- `../DAWcoder-数据集治理方案.md`：完整许可裁定、遗漏数据集清单、双轨制（商用/研究）
- `../DAWcoder-方案.md`：DAWcoder 产品与技术方案
- `../DAWcoder-自建基座可行性.md`：从零预训练 vs CPT 的算力预算

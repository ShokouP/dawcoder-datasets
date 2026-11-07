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

## DAWcoder 预览版（进行中）

`preview/` 存放预览版打包与 demo（参照 3DCoder 的发布范式：专用小模型 + GGUF + 明确 system prompt/采样参数 + 可直接使用的产物）：

- `preview/README.md`：快速开始（Ollama）、system prompt、采样参数、prompt 思路、限制
- `preview/system_prompt.txt`：模型训练时使用的 system prompt（必须设置）
- `preview/modelfile`：Ollama Modelfile 模板
- `preview/demo.html`：本地网页 demo（意图 → patch JSON 可视化预览）
- `preview/examples.md`：mix / form / texture 示例输入
- `preview/REFERENCE-3DCODER.md`：3DCoder 使用方式与可复用经验

模型：`dawcoder-preview`（基于 Qwen3.5-4B 的 CPT + SFT，Q4_K_M），训练与导出记录见 `cpt/TRAINING.md`、`training/README.md`。

## 继续预训练语料（CPT）

`cpt/` 提供 **Qwen3.5-4B 继续预训练**的领域文本语料（音频工程/混音/DAW 格式/乐理/声学）：

| 版本 | 规模 | 位置 |
|---|---|---|
| **curated lite**（仓库内置） | 7,177 docs / ~2.96M tokens | `cpt/data/` |
| **curated full**（训练用，本地构建） | 58,972 docs / **~24.24M tokens** | `cpt/data-curated/`（`python cpt/build.py --raw-dir cpt/raw-curated ...`） |
| broad full（v0.2，宽口径公开版） | 108,353 docs / ~55.19M tokens | GitHub Releases → `cpt-v0.2` |

质量评估与清洗：见 [`cpt/QA-REPORT.md`](cpt/QA-REPORT.md)。管道：`fetch` → `curate`（Gutenberg 严格过滤 / SE 去噪 / arXiv 去 ML 噪声）→ `build` → `check`。
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

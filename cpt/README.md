# DAWcoder CPT 语料（继续预训练数据库）v0.3-curated

新增 v0.4 扩充版的实际采集量、许可与复现命令见 [COLLECTION-REPORT.md](COLLECTION-REPORT.md)。
本地新增 `data-expanded/`（公开混合许可）与 `data-permissive/`（许可白名单，排除 SA）；
两者均在 `.gitignore` 中。原有语料与训练输入文件保持独立，构建、转换和校验仅使用 CPU。

面向 **Qwen3.5-4B 继续预训练（CPT）** 的领域语料：音频工程 / 混音 / DAW 工程格式 / 乐理 / 声学。

质量评估与清洗过程见 [`QA-REPORT.md`](QA-REPORT.md)：**v0.2 broad 大而不精 → v0.3 curated 用于训练预览版**。

## 三个版本

| 版本 | 规模 | 位置 | 用途 |
|---|---|---|---|
| **curated lite**（仓库内置） | 7,177 docs / 11.7M 字符 / **~2.96M tokens** | `cpt/data/` | CI 校验、快速实验 |
| **curated full** | 58,972 docs / 96.9M 字符 / **~24.24M tokens** | `cpt/data-curated/`（不入库，可复现构建） | **预览版 CPT 训练** |
| broad full（v0.2） | 108,353 docs / 220.6M 字符 / ~55.19M tokens | GitHub Release `cpt-v0.2` | 宽口径公开语料（含较多音乐文学，未精选） |

## 当前 curated 构成（24.24M tokens）

| 源 | 许可 | docs | tokens | 占比 |
|---|---|---|---:|---:|
| stackexchange-sound | CC BY-SA 4.0 | 20,762 | 5.04M | 21% |
| stackexchange-music | CC BY-SA 4.0 | 21,086 | 7.02M | 29% |
| stackexchange-avp | CC BY-SA 4.0 | 12,621 | 3.51M | 14% |
| gutenberg-music（精选：乐理/声学/教学） | 公版 | 2,683 | 8.01M | 33% |
| arxiv-audio（过滤后） | CC0（元数据） | 1,169 | 0.35M | 1.4% |
| dawcoder-ir-handbook | CC0 | 617 | 0.24M | 1.0% |
| dawproject-spec | MIT | 2 | 0.015M | — |
| zh-wikipedia-audio | CC BY-SA 4.0 | 32 | 0.048M | — |

> 现代制作语料（SE 三站）占 **64%**；Gutenberg 仅保留非虚构音乐理论/声学/教学书。

## 管道（fetch → curate → build → check）

```bash
pip install pyyaml

# 1) 抓取（Stack Exchange 官方转储 + 公版书 + arXiv）
python cpt/fetch_se_dumps.py --site all
python cpt/fetch.py --source gutenberg-music
python cpt/fetch.py --source arxiv-audio
python cpt/fetch.py --source dawproject-spec
python cpt/fetch.py --source zh-wikipedia-audio

# 2) 清洗 / 重平衡（Gutenberg 严格过滤、SE 去短帖、arXiv 去 ML 噪声）
python cpt/curate.py

# 3) 构建
python cpt/build.py --max-tokens 3000000  --raw-dir cpt/raw-curated --out cpt/data           --corpus-name dawcoder-cpt-v0.3-curated
python cpt/build.py --max-tokens 30000000 --raw-dir cpt/raw-curated --out cpt/data-curated  --corpus-name dawcoder-cpt-v0.3-curated-full

# 4) 转 CPT 训练格式（统一 text 列）
python cpt/make_cpt_text.py cpt/data-curated

# 5) 校验
python cpt/check.py
```

## 接入 CPT（Qwen3.5-4B LoRA，已实际使用）

```powershell
D:\train\venv\Scripts\python.exe D:\train\scripts\train_cpt.py `
  --model D:\train\models\Qwen3.5-4B `
  --data cpt/data-curated/cpt_train_text.jsonl `
  --output D:\train\models\dawcoder_cpt_v1 `
  --seq 1024 --max-steps 400 --max-samples 24000 --lr 1e-4 --accum 16
```

- 400 步 × (1024×16) ≈ 655 万 tokens（约 1 小时量级，预览版）；
- 正式版建议 1 epoch（24M tokens，约 4.5–5 小时）+ replay 1:0.1–0.3；
- 训练后用 `synthetic/` SFT 数据做指令微调，再做 mix/form/texture 评测。

## 许可与署名

- **CC BY-SA 4.0**（SE / Wikipedia）+ **公版**（Gutenberg）+ **MIT**（DAWproject）+ **CC0**（自建手册）。
- 逐源署名见 `cpt/data/ATTRIBUTIONS.md`；SE 保留帖子 URL/作者；受版权手册（REAPER/FL）不入库。
- CC BY-SA 的 SA 条款是否传导到模型权重存在争议，商用前请法务确认。

## 已知问题

- **中文仍≈0**（18 docs）：zhwiki/维基文库限速严重，需用 dumps 或授权中文教材补齐。
- Gutenberg 精选后仍偏理论/声学，现代 DAW 操作细节不足（受版权手册无法入库）。
- 无插件文档、无真实工程/参数数据（这部分留给 SFT 合成数据 + 私有遥测）。
- 近似去重仅在小规模启用；clean 后 exact 重复 1–2 条。

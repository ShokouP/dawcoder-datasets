# DAWcoder CPT Corpus v0.3 (curated)

## 概览
- **继续预训练（CPT）语料**，面向 DAWcoder 预览版：音频工程/混音/DAW 工程格式/乐理/声学。
- curated lite（仓库）：7,177 docs / 11.7M 字符 / **~2.96M tokens**，位于 `cpt/data/`。
- curated full（训练用，本地构建）：58,972 docs / 96.86M 字符 / **~24.24M tokens**，由 `cpt/build.py --raw-dir cpt/raw-curated` 生成。
- broad v0.2（55.19M tokens）保留在 GitHub Release `cpt-v0.2`，仅作宽口径公开版。
- 质量评估与清洗规则：见 `cpt/QA-REPORT.md`；构建脚本：`cpt/curate.py` → `cpt/build.py` → `cpt/make_cpt_text.py`。

## 许可
- **混合许可**：CC BY-SA 4.0（Stack Exchange / Wikipedia）、公版（Project Gutenberg）、MIT（DAWproject）、CC0（自建参数手册）。
- 语料整体按 **CC BY-SA 4.0** 分发；每个文档保留 `source` / `license` / `url` 字段，逐源署名见 `cpt/data/ATTRIBUTIONS.md`。
- 证据：本仓库 `cpt/`（captured 2026-11-07，reviewer: shokoup）。
- 受版权内容（REAPER/FL 手册）仅作 T2 私有源，**不进入**公开语料。

## 引用
DAWcoder contributors, "DAWcoder CPT Corpus v0.3 curated", 2026.

## 已知问题
- 中文占比仍≈0（18 docs）：zhwiki/维基文库 429 限速，需 dumps 或授权中文教材。
- Gutenberg 精选后以乐理/声学/教学为主，现代 DAW 操作细节不足（手册受版权限制）。
- 无插件文档与真实工程/参数数据（留给 SFT 合成数据与私有遥测）。
- 近似去重只在 ≤2 万文档时启用；curated 已做精确去重。
- CC BY-SA 的相同方式共享要求是否传导到模型权重存在法律争议，商用前需法务确认。

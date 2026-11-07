# DAWcoder CPT Corpus v0.1

## 概览
- 继续预训练（CPT）语料：音频工程 / 混音 / DAW 工程格式 / 乐理 / 编曲。
- 覆盖源：Wikipedia（CC BY-SA 4.0）、Sound Design SE（CC BY-SA 4.0）、Music SE（CC BY-SA 4.0）、
  DAWproject 规范（MIT）、DAWcoder 参数语义手册（CC0）。
- 构建方式：`cpt/fetch.py` 抓取 → `cpt/build.py` 清洗/去重/切分 → `cpt/check.py` 校验。
- 产物：`cpt/data/corpus_{train,val}.jsonl`、`manifest.json`、`stats.md`、`ATTRIBUTIONS.md`。

## 许可
- **混合许可**：CC BY-SA 4.0（Wikipedia / Stack Exchange）、MIT（DAWproject）、CC0（自建手册）。
- 语料整体按 **CC BY-SA 4.0** 分发；每个文档保留 `source` / `license` / `url` 字段，逐源署名见 `cpt/data/ATTRIBUTIONS.md`。
- 证据：本仓库 `cpt/` 目录（captured 2026-11-07，reviewer: shokoup）
- 受版权内容（REAPER 手册、FL Studio 手册）仅作 T2 私有源，**不进入**公开语料。

## 引用
DAWcoder contributors, "DAWcoder CPT Corpus v0.1", 2026.

## 已知问题
- v0.1 是管道验证版，规模有限（3,313 docs / ~105 万 tokens，见 `cpt/data/stats.md`）；正式 CPT 前需扩展私有/授权语料。
- **中文覆盖不足**：中文维基仅 18 篇，中文术语与教学语料需要专门补充。
- Wikipedia 英文源本次因限速跳过，后续用 dumps 或分批抓取。
- Stack Exchange 内容为问答体，风格与工程文档不同，CPT 时注意配比。
- CC BY-SA 的相同方式共享要求是否传导到模型权重存在法律争议，商用前需法务确认。
- 与 `synthetic/` 的 SFT 数据有少量重叠（参数语义手册），CPT 时可降采样。

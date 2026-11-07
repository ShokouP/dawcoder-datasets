# Changelog

## v0.2 — 2026-11-07

- CPT 语料扩量：**108,353 docs / 220.6M 字符 / ~55.19M tokens**（此前 3,313 docs / ~1.05M）
- 新增源：
  - Stack Exchange 官方数据转储（sound 2.98 万 / music 8.47 万 / avp 1.80 万 posts，CC BY-SA 4.0）
  - Project Gutenberg 音乐/声学公版书 500 本，分块为 10,225 docs（公版）
  - arXiv 摘要扩展到 1,438 条（14 个查询，CC0 元数据）
  - 中文维基音频条目 32 篇（CC BY-SA 4.0）、中文维基文库 6 篇（公版）
- 新增 `cpt/fetch_se_dumps.py`（7z → Posts.xml → JSONL）、Gutenberg 并发抓取 + 分块、维基文库搜索抓取
- `cpt/build.py` 支持 token 预算（lite 3M / full 56M）、流式处理、语言/长度统计
- full 语料以 GitHub Release 附件发布（`cpt-v0.2`，train 90.7MB + val 2.0MB gzip）
- 仓库内保留 lite 语料（~3.27M tokens）以保证 CI 可校验、可复现
- CI 增加 CPT 语料校验（manifest / 许可 / 溯源 / 去重）

## v0.1 — 2026-11-07

- 新增 `cpt/`：继续预训练语料管道（`sources.yaml` → `fetch.py` → `build.py` → `check.py`）
- 语料源：Stack Exchange（sound / music / avp，CC BY-SA 4.0）、arXiv 摘要（CC0 元数据）、
  DAWproject 规范（MIT）、中文维基音频条目（CC BY-SA 4.0）、自建参数语义手册（CC0）
- 构建产物：3,313 docs / 4,089,786 chars / ~1,054,447 tokens

## 2026-11-07（SFT 数据）

- 新增 `synthetic/`：3,600 条可训练样本（mix / form / texture），chat 格式 + 结构化格式
- 修复 Windows CRLF 导致 manifest sha256 在 Linux CI 不匹配的问题（强制 LF）

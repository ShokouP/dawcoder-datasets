# Changelog

## v0.1 — 2026-11-07

- 新增 `cpt/`：继续预训练语料管道（`sources.yaml` → `fetch.py` → `build.py` → `check.py`）
- 语料源：Stack Exchange（sound / music / avp，CC BY-SA 4.0）、arXiv 摘要（CC0 元数据）、
  DAWproject 规范（MIT）、中文维基音频条目（CC BY-SA 4.0）、自建参数语义手册（CC0）
- 构建产物：3,313 docs / 4,089,786 chars / ~1,054,447 tokens；train 3,249 / val 64
- 新增去重（精确 + SimHash 近似）、语言分布、长度分位统计
- 新增 `ATTRIBUTIONS.md` 逐源署名；T2 源（REAPER/FL 手册）仅 fetch-only，不入公开语料
- CI 增加 `cpt/check.py` 校验（manifest / 许可 / 溯源 / 去重）

## 2026-11-07（SFT 数据）

- 新增 `synthetic/`：3,600 条可训练样本（mix / form / texture），chat 格式 + 结构化格式
- 修复 Windows CRLF 导致 manifest sha256 在 Linux CI 不匹配的问题（强制 LF）

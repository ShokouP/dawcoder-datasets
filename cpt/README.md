# DAWcoder CPT 语料（继续预训练数据库）v0.2

面向 **Qwen3.5-4B 继续预训练（CPT）** 的领域语料：音频工程 / 混音 / DAW 工程格式 / 乐理 / 音频信号处理。

## 两个版本

| 版本 | 规模 | 位置 |
|---|---|---|
| **lite**（仓库内置） | 6,736 docs / 12.8M 字符 / **~3.27M tokens** | `cpt/data/` |
| **full**（GitHub Release 附件） | 约 108,000 docs / 220M 字符 / **~55M tokens** | Releases → `cpt-v0.2`（`.jsonl.gz`） |

下载 full：

```bash
gh release download cpt-v0.2 -R ShokouP/dawcoder-datasets -D cpt/data-full
```

## 设计原则

1. **只收录可再分发来源**（T0/T1）进公开语料；REAPER/FL 手册等受版权内容只做 fetch-only 私有源，不进仓库。
2. 每个文档保留 `source` / `license` / `tier` / `url` / `author` 字段，语料自带溯源。
3. 可复现：`fetch` → `build` → `check` 三段式，manifest 带 sha256 / token 估算 / 逐源统计。
4. 与 SFT 数据（`synthetic/`）分开：本目录是**无监督文本**（CPT），SFT 是 `state/intent/patch` 对齐样本。

## 源与许可

| 源 | 许可 | 内容 | 规模贡献（full） |
|---|---|---|---|
| `stackexchange-sound` | CC BY-SA 4.0 | Sound Design SE 全量（官方数据转储） | ~4.6M tokens |
| `stackexchange-music` | CC BY-SA 4.0 | Music Practice & Theory SE 全量 | ~16M tokens |
| `stackexchange-avp` | CC BY-SA 4.0 | Audio/Video Production SE 全量 | ~3M tokens |
| `gutenberg-music` | 公版（Project Gutenberg） | 音乐/声学/乐器/歌唱类公版书全文（分块） | ~30M tokens |
| `arxiv-audio` | CC0（元数据） | 混音/效果/分离/响度/空间音频等论文摘要 | ~0.4M tokens |
| `dawproject-spec` | MIT | DAWproject 规范、XSD、示例 | 极小 |
| `dawcoder-ir-handbook` | CC0 | 自建：任务说明 + patch 语义 + 示例转写 | ~0.24M tokens |
| `zh-wikipedia-audio` | CC BY-SA 4.0 | 中文维基音频/音乐制作条目 | 小 |
| `zh-wikisource-music` | 公版 | 中文维基文库古代音乐文献（乐记/琴论/曲论） | 小 |
| `wikipedia-audio` | CC BY-SA 4.0 | 英文维基（可选，429 限速时跳过） | 0（本次跳过） |

仅本地/私有（T2，需自行获取）：`reaper-user-guide`、`flstudio-manual`。

## 用法

```bash
pip install pyyaml

# 1) Stack Exchange 全量转储（~158MB）
python -c "import urllib.request as u;[open(f'cpt/raw/dumps/{s}.stackexchange.com.7z','wb').write(u.urlopen(f'https://archive.org/download/stackexchange/{s}.stackexchange.com.7z').read()) for s in ['sound','music','avp']]"
python cpt/fetch_se_dumps.py --site all

# 2) 其他源
python cpt/fetch.py --source gutenberg-music
python cpt/fetch.py --source arxiv-audio
python cpt/fetch.py --source dawproject-spec
python cpt/fetch.py --source zh-wikipedia-audio
python cpt/fetch.py --source zh-wikisource-music

# 3) 构建
python cpt/build.py --max-tokens 3000000                          # 仓库 lite
python cpt/build.py --max-tokens 56000000 --out cpt/data-full    # 完整版

# 4) 校验
python cpt/check.py
```

## 接入 CPT（Qwen3.5-4B LoRA）

- 训练前用 Qwen 分词器实测 tokens（`manifest.est_tokens` 只是估算）；full 版约 55M tokens，按 4B LoRA 1,500 tok/s 估算约 **10 小时/epoch**（本地 5090 24GB）。
- 建议 domain : general replay ≈ 1 : 0.1–0.3，防灾难性遗忘。
- 文档按块（3k–12k 字符）组织，切分与 packing 时注意保持块内完整，max_seq_len=2048。
- 每轮用 `synthetic/` 的 SFT 验证集 + 通用回放评测守门。

## 许可与署名

- 语料整体按 **CC BY-SA 4.0** 分发（Stack Exchange / Wikipedia 部分）+ 公版（Gutenberg / Wikisource）+ MIT（DAWproject）+ CC0（自建手册）。
- 逐源署名与要求见 `cpt/data/ATTRIBUTIONS.md`；SE 内容保留帖子 URL 与作者，Wikipedia 保留条目链接。
- 受版权内容（REAPER/FL 手册）**不进入**公开语料。
- CC BY-SA 的相同方式共享要求是否传导到模型权重存在法律争议，商用发布前请法务确认。

## 已知问题

- **中文占比仍低**（lite 约 0.2%）：中文维基限速严重、文库文献有限；正式版建议用 zhwiki dumps 或采购中文教材补齐。
- Gutenberg 语料偏 19 世纪及以前，术语与现代 DAW 实践有代差，靠 Stack Exchange / arXiv 平衡。
- Stack Exchange 是问答体，CPT 时建议与教科书/文档类按 1:1 配比。
- 近似去重（SimHash）只在 ≤2 万文档时启用；full 版只做精确去重。
- `wikipedia-audio`（英文）因 429 限速本次跳过，可用 dumps 补。

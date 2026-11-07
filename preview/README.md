# DAWcoder Preview

**DAWcoder** 是一个 4B 音乐制作参数模型：输入「工程状态 + 自然语言制作意图」，输出**可执行的 DAW 参数补丁 JSON**（混音参数 / 曲式结构 / 织体音符）。模型不生成音频，只生成可校验、可编辑、可回滚的工程参数。

- 基座：Qwen3.5-4B（Apache 2.0）
- 训练：curated 语料 CPT（24.2M tokens）+ 3,240 条任务 SFT 样本（mix / form / texture）
- 形态：`dawcoder-preview`（Ollama，Q4_K_M）+ bf16 GGUF
- 状态：**预览版**，用于验证「意图 → patch」链路；不保证真实混音审美

> 参照 3DCoder（ccore/Qwen3.5-4B-GLB-3D-Coder）的发布方式：专用小模型 + GGUF + 明确 system prompt / 采样参数 + 可直接使用的产物（他们输出 standalone HTML，我们输出 JSON patch / patch 预览页）。

## 快速开始

### 1) 加载模型（Ollama）

```bash
ollama create dawcoder-preview -f preview/modelfile
ollama run dawcoder-preview
```

### 2) 设置 system prompt（必须）

内容见 [`system_prompt.txt`](system_prompt.txt)。模型是在该 system prompt 下训练的，缺了它输出格式会漂。

### 3) 输入示例

user 消息是 JSON：

```json
{"task":"mix","state":{"genre":"pop","tempo":120,"tracks":[{"name":"Lead Vocal","role":"vocal","volume_db":-8.0,"pan":0.0,"sends":[{"to":"Plate Reverb","gain_db":-14.0}]}],"buses":[{"name":"Drum Bus","volume_db":-2.0}]},"intent":"人声被鼓盖住了，帮我推出来一点，别太亮"}
```

模型输出：

```json
{"ops":[{"op":"set_track","track":"Lead Vocal","fields":{"volume_db":-6.5}},{"op":"set_eq","track":"Pad","band":2,"type":"bell","freq":315,"gain_db":-1.5,"q":1.0}]}
```

### 4) 网页 demo

```bash
python -m http.server 8000 --directory preview
# 浏览器打开 http://localhost:8000/demo.html
```

先设置 CORS（浏览器直连 Ollama 需要）：

```powershell
$env:OLLAMA_ORIGINS = "*"
ollama serve
```

demo 页会调用 `http://127.0.0.1:11434/api/chat`，展示生成的 JSON 与逐条 patch 预览。

## 采样参数（与发布一致）

| 参数 | 值 |
|---|---|
| temperature | 0.0（确定性输出） |
| top_p | 0.95 |
| repeat_penalty | 1.0 |
| num_ctx | 16384 |
| num_predict | 2048 |

3DCoder 的启发：输出要允许足够长（他们平均 20K tokens、限制 8K 会截断）；我们的 patch 短，但 `num_predict` 给 2048 足够覆盖复杂 form/texture。

## 任务与 prompt 思路

| 任务 | 示例意图 |
|---|---|
| mix | "人声再靠前 1 dB，320Hz 收 3 dB" / "鼓组做 glue 压缩" / "整体更亮但别刺" |
| mix（总线） | "鼓总线推 1.5 dB" / "人声混响发送降 4 dB" |
| form | "做一首 3 分钟 house，8 小节 intro、16 小节 build、drop 要冲击力" |
| form | "流行歌：主歌-副歌-主歌-副歌-桥段-副歌，总长 3 分半" |
| texture | "Cmaj7 上做 16 分上行琶音，音域 C3-C5，力度 70-95" |
| texture | "Am7-F-Cmaj7-G 进行，8 分分解和弦，钢琴中音区" |

更多见 [`examples.md`](examples.md)。

## 已知限制

- **预览版**：只在 3,600 条合成任务数据上做过 SFT，真实工程泛化有限；
- 输出是**参数建议**，应用到 FL Studio/其他 DAW 前必须人工确认（尤其第三方插件参数映射）；
- 中文制作意图支持有限（CPT 语料中文≈0，SFT 意图为中文模板）；
- 无音频生成能力；不替代混音师判断；
- 第三方插件参数语义未覆盖，默认只支持轨道/发送/通用 EQ/压缩参数。

## 许可与署名

- 模型：基于 Qwen3.5-4B（Apache 2.0），保留原许可与版权声明；
- 训练数据：CC0（synthetic/）+ CC BY-SA 4.0 / 公版（cpt/），见 `cpt/data/ATTRIBUTIONS.md`；
- 代码：Apache-2.0。

## 相关

- 数据集：https://github.com/ShokouP/dawcoder-datasets
- 语料质量报告：`cpt/QA-REPORT.md`
- 训练记录：`cpt/TRAINING.md`、`training/README.md`

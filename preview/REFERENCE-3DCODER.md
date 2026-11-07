# DAWcoder 参考：3DCoder 是怎么用的（ccore/Qwen3.5-4B-GLB-3D-Coder）

> 来源：Hugging Face 模型卡 + 社区评测文章。记录其**产品化/使用方式**，用于 DAWcoder 预览版的打包。

## 1. 它是什么

- **专用 4B 代码模型**：基于 Qwen3.5-4B 微调，输入一句描述，输出**完整的 Three.js HTML 页面**（含预览 + Export GLB 按钮），可导出 GLB 到 Godot/Blender/Unity。
- Apache 2.0；发布 GGUF（Q4_K_M、Q8_0）+ 原始 Safetensors + 可选视觉投影器。
- 同时发布训练数据集：3,918 条已渲染验证的示例（40 个领域）。

## 2. 使用链路（可直接照搬的范式）

1. **加载 GGUF**（LM Studio / Ollama / llama.cpp 等支持 Qwen3.5 的运行时）。
2. **设置 system prompt**（模型卡给出完整一段，明确"输出一个 standalone HTML，含 Export GLB 按钮"）。
3. **设采样参数**：temperature 0.8、top_k 40、top_p 0.95、min_p 0、repeat 1.0；thinking 开启。
4. **输出长度不限**（可用时 `-1`）：平均输出约 20K tokens，训练样本最长 72K；模型卡明确"8K 上限会截断，生成不可用"。
5. **用户侧动作**：保存完整 HTML → 浏览器打开 → 点 Export GLB → 导入 Godot。
6. **展示**：官方用生成资产做了可玩网页游戏 RIFTWARD（HF Space），另附"给 coding agent 的 starter prompt"，让别人把本地模型接进 agent 工作流。

## 3. 关键经验（对 DAWcoder 的启发）

| 3DCoder 做法 | DAWcoder 对应 |
|---|---|
| 输出是**可直接运行的 standalone HTML**（浏览器即预览） | 输出**可直接应用的 JSON patch**；再配一个独立 HTML 预览页（`preview/demo.html`）展示并模拟 patch |
| system prompt 写成**完整规范**（目标格式 + 必须包含的元素） | 已写 `preview/system_prompt.txt`：只输出 JSON、三任务各自结构、工程单位 |
| 明确**采样参数**与**输出长度**（宁长勿截断） | temperature 0、top_p 0.95、num_ctx 16384、num_predict 2048（patch 短） |
| 发布 **Q4_K_M + Q8_0 + Safetensors** 三档 | Q4_K_M（Ollama 默认）+ bf16 GGUF；如需可加 Q8_0 |
| 同时发布**训练数据集**与**验证样例** | 已发布 synthetic SFT 数据 + curated CPT 语料；预览版附评测报告 |
| **showcase 先行**（可玩 demo + 社区作品） | demo.html + 预设示例 + （后续）FL/REAPER adapter 演示 |
| 诚实标注 limitations（需要重试/人工检查） | 预览版 README 的"已知限制"（泛化有限、需 DAW 人工确认、插件映射未覆盖） |
| 独立开发者自筹、Ko-fi/加密捐赠、社区支持 | 开源 + 后续数据/模型发布节奏参考 |

## 4. 它没有做、我们要做的

- 3DCoder 输出的是**视觉产物**（HTML/GLB），可"打开即见"；DAWcoder 的输出是**工程参数**，必须靠 DAW 执行才有反馈 → 我们用 `preview/demo.html` 做"参数补丁可视化"，并在正式版里接 FL/REAPER adapter 实现真正应用 + 渲染指标验证。
- 3DCoder 有**数据集闭环**（3918 条渲染验证样本）；我们当前 SFT 是合成数据，下一步需要用 Slakh/真实工程做**渲染验证数据引擎**（L4 管道）。

## 5. 参考链接

- 模型卡：https://huggingface.co/ccore/Qwen3.5-4B-GLB-3D-Coder
- 数据集：https://huggingface.co/datasets/ccore/ThreeJS-3D-GLB-Assets
- Showcase：https://huggingface.co/spaces/ccore/RIFTWARD
- 社区评测（Ollama 用法）：https://mobdome.com/blog/qwen-3d-coder-tutorial/

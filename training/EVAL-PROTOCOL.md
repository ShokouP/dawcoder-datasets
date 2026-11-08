# DAWcoder 评测协议（Evaluation Protocol）

本协议只约定**评测侧**的固定设置与产物接口。**训练方案（数据、算法、超参、导出）由 Astra 全权决定**，评测侧不做训练方案设计或改进建议。

## 1. 评测所需的提交信息（Submission interface）

评测侧需要拿到可加载的模型和最小复现信息。请按下面组织提交：

```
submission/
├─ manifest.json      # 模型名、基座、阶段、Ollama 模型名、系统提示词路径
├─ adapter/           # 可选：标准 PEFT 目录（adapter_config.json + adapter_model.safetensors）
├─ merged/            # 可选：合并后的 bf16 HF 模型
├─ model-Q4_K_M.gguf  # 可选
└─ notes.md           # 可选：方法/数据/超参说明（内容由 Astra 决定）
```

`manifest.json` 最小字段：

```json
{
  "name": "dawcoder-<stage>-<version>",
  "base_model": "Qwen3.5-4B",
  "stage": "<stage>",
  "ollama_model": "<name>",
  "system_prompt": "preview/system_prompt.txt",
  "sampling": {"temperature": 0.0, "top_p": 0.95, "num_ctx": 16384, "num_predict": 8192}
}
```

- 模型名建议 `dawcoder-<stage>-<version>`，便于报告归档；命名最终由 Astra 决定。
- 系统提示词需与训练/推理一致（评测使用 `preview/system_prompt.txt`）。
- 只要能在 Ollama 中加载并用上述采样设置响应，即可进入评测；其余训练细节不影响评测。

## 2. 固定评测设置（评测侧执行，提交方无需修改训练）

| 项 | 值 |
|---|---|
| 验证集 | `training/data/dawcoder_sft_val.jsonl`（sha256 记录在报告中） |
| 采样 | balanced round-robin：mix 20 / form 20 / texture 20 = **60 条**，seed `20261107` |
| 解码 | temperature 0.0，top_p 0.95，num_ctx 16384，num_predict 8192 |
| 必备指标 | JSON 解析率、schema 合法率、per-task 合法率、reasons 分布、macro valid |
| 可选指标 | 与金标准 patch 的相似度 reward（`lib_dawcoder_reward.py`） |
| 可选指标 | `daw-mcp-server` 的 `verify_patch` 闭环（apply → render → analyze → score） |

## 3. 评测命令

```bash
D:\train\venv\Scripts\python.exe training\eval_dawcoder.py --model <名字> --limit 60 --out training\eval-report-<名字>.json
D:\train\venv\Scripts\python.exe training\eval_all_models.py --models <名字1>,<名字2> --limit 60
D:\train\venv\Scripts\python.exe training\compare_models.py
```

## 4. 交付物

1. `training/eval-report-<model>.json`：原始评测数据
2. `training/COMPARISON-REPORT.md`：对比表（schema、per-task、reward）+ 相对基线回归标注
3. 事实性结论：各模型是否满足下列评测阈值（不代表对训练方案的评价）

## 5. 评测阈值（仅为评测口径）

- JSON 解析率 ≥ 99%
- schema 合法率 ≥ 98%（macro，按任务均衡）
- 无单任务合法率 < 95%
- 相对基线（`dawcoder-preview`）无任务级退化 > 5 个百分点

## 6. 边界

- **Astra**：数据、训练算法、超参、导出与命名，全部自主决定。
- **评测侧**：按本协议固定评测、生成报告与回归标注；不修改、不建议 Astra 的训练方案。
- 若评测出现异常（如请求错误、服务中断），评测侧只报告事实并重跑，不改动模型或训练配置。

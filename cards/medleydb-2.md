# MedleyDB 2.0

## 概览
- 196 首真实多轨（原 122 + 2.0 新增 74），含 mix + processed stems + 原始音频 + metadata、旋律 f0、乐器激活标注。
- 用途：混音评测、乐器识别辅助、真实录音分布校准。

## 许可
- **CC BY-NC-SA 4.0**（非商用、相同方式共享；以 Zenodo 条款为准）。
- 证据：https://zenodo.org/records/1715175 （captured 2026-11-07，reviewer: shokoup）
- 注：官网自称 royalty-free，但 MUSDB 文档与 Zenodo 标注为 NC-SA，按更严格者执行。

## 引用
Bittner, Salamon, Tierney, Mauch, Cannam, Bello, "MedleyDB: A Multitrack Dataset for Annotation-Intensive MIR Research", ISMIR 2014；MedleyDB 2.0, ISMIR 2016.

## 已知问题
- 需向 NYU 提交申请（Zenodo 许可请求），不是直接下载。
- 与 MUSDB18 有 46 首重叠 → 切分合并 `group_key`。
- 非商用：不得进入商用训练集；派生音频不得发布。

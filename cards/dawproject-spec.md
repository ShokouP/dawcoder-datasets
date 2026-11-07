# DAWproject open exchange format

## 概览
- 开放工程交换格式：ZIP（project.xml + metadata.xml），包含音频/音符/自动化/插件状态/内置 EQ-压缩-门-限制器。
- 支持：Bitwig 5、Studio One 6.5、Cubase 14、Cubasis、VST Live、n-Track；另有 DawVert/ProjectConverter 转换器。
- 用途：DAWcoder 的跨 DAW 中间表示（IR）与适配器规范。

## 许可
- **仓库 MIT**（规范、XSD、示例代码可自由使用）。
- 证据：https://github.com/bitwig/dawproject （captured 2026-11-07，reviewer: shokoup）
- 注意：示例工程内嵌的音频/采样需逐文件核对，不可默认整仓音频可用。

## 引用
Bitwig, DAWproject 1.0 (https://github.com/bitwig/dawproject).

## 已知问题
- 不是 DAW 原生格式；插件状态（VST3 state）跨机器不可移植，需要语义参数映射层。
- 示例工程含第三方音频素材，只取结构做测试。
- FR/版本演进快，adapter 要锁版本并跑回归。

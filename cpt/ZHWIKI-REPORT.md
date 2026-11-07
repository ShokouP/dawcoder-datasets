# 中文维基 dump 采集与合并报告（v0.6）

## 目的
补上 CPT 语料的中文缺口：此前合并语料（v0.5）中文仅 28 篇（<0.1%），无法支撑中文制作意图。

## 数据获取
- 来源：`https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-pages-articles.xml.bz2`
- 大小：3,452,366,696 bytes（3.45GB）
- 下载：分块续传（8MB Range，单连接）约 32 分钟，规避 Wikipedia 的 429 限速与长连接降速
- 解析：`cpt/fetch_zhwiki_dump.py`（bz2 流式 + ElementTree iterparse + wikitext 清洗）

## 抽取规则
- 命名空间 0（正文）、非重定向、清洗后长度 800–150,000 字符；
- 关键词命中（标题或正文）：混音/母带/均衡器/压缩器/混响/效果器/音频/录音/音乐制作/声学/音色/和声/对位/编曲/配器/采样率/调音台/麦克风/监听/频率响应/动态范围/失真/噪声/分贝/滤波器/频谱/数字音频/插件/合成器/录音室/立体声/环绕声/声像/响度/信噪比/音频接口/MIDI/音轨/总线 等 60+ 词；
- 长条目按 800–12,000 字符分块（短条目整篇保留）；
- 上限：5,000 docs / 25M 字符（避免全量 dump 无限膨胀）。

## 结果
- 解析页数：109,238（在达到上限前扫描）
- **3,865 docs / 25,002,314 字符 / ~12,847,232 tokens**
- 训练/验证切分按 `group_key = zhwiki:<title>` 分组（同条目分块不跨集）

## 合并（v0.6）
输入：zhwiki-corpus + data-expanded + data-curated + data-permissive
- **74,198 docs / 138,925,803 字符 / ~41,351,261 tokens**
- train 72,748 / val 1,450
- 语言分布：中文 3,411 docs / 中英混合 777 / 英文 70,010
- 许可分类：share-alike 68,215 docs / permissive 5,983 docs
- 去重移除 64,950 条；无重复、无同源跨集
- 中文 token 占比：约 **31%**（12.85M / 41.35M）

## 许可与署名
- 维基百科文本：**CC BY-SA 4.0**；每篇保留标题与永久链接（`https://zh.wikipedia.org/wiki/<title>`）；
- 合并语料整体按 CC BY-SA 4.0 分发；商用训练请使用 `cpt/data-permissive` 或按 `license_class` 过滤。

## 已知问题
- wikitext 清洗为启发式（模板/引用/表格/文件链接已去除），仍有少量残留标记；
- 关键词过滤会带入一部分泛音乐条目，未做进一步领域打分；
- 只取了 25M 字符上限（全 dump 中相关条目更多），后续可扩到 50M+ 字符；
- `zh-wikipedia-dump` 尚未在 `cpt/sources.yaml` 注册（等另一路提交同步后补），当前以独立 corpus 输入方式合并。

# DAWcoder 示例输入（可直接贴进 demo / Ollama）

user 消息永远是 JSON：`{"task": "...", "state": {...}, "intent": "..."}`。

## mix 混音

```json
{"task":"mix","state":{"genre":"rock","tempo":110,"tracks":[
 {"name":"Kick","role":"kick","volume_db":-4.0,"pan":0.0,"fx":[],"sends":[]},
 {"name":"Snare","role":"snare","volume_db":-6.0,"pan":0.0,"fx":[],"sends":[]},
 {"name":"Bass","role":"bass","volume_db":-6.0,"pan":0.0,"fx":[],"sends":[]},
 {"name":"Rhythm Gtr","role":"gtr","volume_db":-12.0,"pan":-0.2,"fx":[],"sends":[{"to":"Plate Reverb","gain_db":-16.0}]},
 {"name":"Lead Vocal","role":"vocal","volume_db":-8.0,"pan":0.0,"fx":[{"type":"comp","params":{"threshold_db":-18,"ratio":3.0,"attack_ms":5,"release_ms":80}}],"sends":[{"to":"Plate Reverb","gain_db":-14.0}]}],
 "buses":[{"name":"Drum Bus","volume_db":-2.0},{"name":"Plate Reverb","volume_db":-6.0}],
 "master":{"target_lufs":-8.0,"headroom_db":-6.0}},"intent":"底鼓太轰，50-70Hz 收一下；鼓组听起来散，加个 glue 压缩"}
```

```json
{"task":"mix","state":{"genre":"pop","tracks":[{"name":"Lead Vocal","role":"vocal","volume_db":-8.0,"pan":0.0,"sends":[{"to":"Plate Reverb","gain_db":-12.0}]}],"buses":[{"name":"Plate Reverb","volume_db":-6.0}]},"intent":"人声混响太湿了，收一点"}
```

## form 曲式

```json
{"task":"form","state":{"genre":"house","tempo":124,"time_signature":"4/4","target_seconds":248},"intent":"做一首 house，124 BPM，总长约 248 秒；16 小节 intro、16 小节 build、32 小节 drop、16 小节 break、32 小节 drop、16 小节 outro，能量要有对比"}
```

```json
{"task":"form","state":{"genre":"pop","tempo":100,"time_signature":"4/4","target_seconds":210},"intent":"流行歌结构：主歌-副歌-主歌-副歌-桥段-最后副歌-尾声，总长 3 分半，副歌要有记忆点"}
```

## texture 织体

```json
{"task":"texture","state":{"tempo":100,"time_signature":"4/4","progression":["Cmaj7","G","Am7","F"],"style":"arp_16","range":["C3","C5"]},"intent":"16 分音符上行琶音，音域 C3–C5，力度 70–95，不要和弦外音"}
```

```json
{"task":"texture","state":{"tempo":90,"time_signature":"4/4","progression":["Am7","F","Cmaj7","G"],"style":"pad","range":["C3","C5"]},"intent":"长音铺底，声部要开一点，力度 40-65"}
```

```json
{"task":"texture","state":{"tempo":120,"time_signature":"4/4","progression":["Cm","Ab","Eb","Bb"],"style":"ostinato","range":["C3","C5"]},"intent":"8 分音符固定音型，低音区为主，要有推动感"}
```

## 提示词写法（参考 3DCoder 的"图纸语言"经验）

- **先给工程状态**：轨道名、角色、当前参数越完整，patch 越准；
- **意图要可度量**：说"推 1–2 dB / 320Hz 收 3dB"比"好听一点"有效；
- **一次只做一档事**：复杂需求拆成多次生成-验证；
- **要求格式**：明确 `task` 字段，模型才知道输出 ops / sections / notes。

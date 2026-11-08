# Groove MIDI Dataset (MIDI-only)

## 许可

- SPDX: CC-BY-4.0; retain attribution and mark preprocessing changes.
- license_url: https://magenta.tensorflow.org/datasets/groove
- Publisher: Google LLC. Only the official MIDI-only archive is collected.
- Published SHA-256: `651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e`.

## 引用

Gillick, Roberts, Engel, Eck and Bamman. *Learning to Groove with Inverse Sequence Transformations*. ICML 2019.

## 预处理

`python tools/collect_symbolic.py --source groove-midi` downloads 1,150 performances,
checks the official archive hash and writes ignored `data/symbolic/groove-midi/`:

- `performances_{train,val,test}.jsonl`: positive-velocity note-on hits as `[tick, pitch, velocity]`.
- `windows_{train,val,test}.jsonl`: complete two-bar windows from 4/4 performances.
- Original microtiming, velocity, pitch mapping and official splits are retained.
- Exact duplicate performances prefer test, then validation, then train copies.
- `ATTRIBUTIONS.md` and `manifest.json` record transformations and file hashes.

## 已知问题

- Drum pitches use Roland TD-11 mapping; do not interpret every pitch as General MIDI.
- These are drum event records, not the pitched-note `texture` IR and not intent/patch SFT pairs.
- No audio or note duration labels are inferred. Only complete 4/4 windows are produced.
- The official split is performance-based, not a strict unseen-drummer benchmark.

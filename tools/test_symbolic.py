import io
import json
from pathlib import Path
import tempfile
import unittest

import mido
from check_symbolic import check
from collect_symbolic import dump_rows, midi_hits


class SymbolicTests(unittest.TestCase):
    def test_preserves_microtiming_and_ignores_note_off(self):
        midi = mido.MidiFile(ticks_per_beat=480)
        midi.tracks.append(mido.MidiTrack([
            mido.Message("note_on", note=36, velocity=91, channel=9, time=3),
            mido.Message("note_on", note=36, velocity=0, channel=9, time=100),
            mido.Message("note_on", note=38, velocity=87, channel=9, time=380),
            mido.Message("note_off", note=38, velocity=0, channel=9, time=1),
        ]))
        buffer = io.BytesIO()
        midi.save(file=buffer)
        ppq, ticks, hits = midi_hits(buffer.getvalue())
        self.assertEqual((ppq, ticks), (480, 484))
        self.assertEqual(hits, [[3, 36, 91], [483, 38, 87]])

    def test_checker_rejects_song_leakage_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            row = {"group_key": "salami:1", "split": "train", "song_id": "1", "annotator": "1", "license": "CC0-1.0", "source_sha256": "abc", "boundaries": [{"time_seconds": 0.0, "label": "intro"}]}
            files = {"sections_train.jsonl": dump_rows(directory, "sections_train.jsonl", [row]), "sections_val.jsonl": dump_rows(directory, "sections_val.jsonl", [{**row, "split": "val", "annotator": "2"}])}
            (directory / "manifest.json").write_text(json.dumps({"files": files, "license": "CC0-1.0", "songs": 1, "annotations": 2, "boundaries": 2}), encoding="utf-8")
            errors, _ = check(directory)
            self.assertTrue(any("Cross-split" in error for error in errors))
            with (directory / "sections_train.jsonl").open("a") as fh:
                fh.write("\n")
            errors, _ = check(directory)
            self.assertTrue(any("Hash mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

"""Regression tests for coverage, malformed model output and real fixtures."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch as mock_patch

from eval_dawcoder import extract_json, main, select_rows
from patch_validation import validate

ROOT = Path(__file__).resolve().parent.parent


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.state = {"tracks": [{"name": "Vocal"}], "buses": [{"name": "Reverb"}]}
        self.comp = {"op": "set_comp", "track": "Vocal", "params": {"threshold_db": -18, "ratio": 3, "attack_ms": 5, "release_ms": 80}}
        self.send = {"op": "set_send", "from": "Vocal", "to": "Reverb", "gain_db": -12}
        self.form = {"tempo": 120, "time_signature": "4/4", "sections": [{"name": "Intro", "start_bar": 1, "bars": 4, "energy": 0.3, "density": 0.2}], "markers": [{"bar": 1, "name": "Intro"}]}
        self.note = {"bar": 1, "step": 0, "key": 60, "len_steps": 2, "vel": 80}

    def rows(self):
        return [{"instruction": json.dumps({"task": task}), "id": f"{task}-{i}"} for task, size in (("mix", 120), ("form", 60), ("texture", 180)) for i in range(size)]

    def test_balanced_default(self):
        selected = select_rows(self.rows())
        self.assertEqual(Counter(json.loads(r["instruction"])["task"] for r in selected), {"mix": 20, "form": 20, "texture": 20})
        self.assertEqual(selected, select_rows(self.rows()))
        self.assertNotEqual(selected, select_rows(self.rows(), seed=7))

    def test_limits_and_missing_tasks(self):
        for limit in (3, 4, 59, 61, 360, 999, 0):
            with self.subTest(limit=limit):
                selected = select_rows(self.rows(), limit)
                self.assertEqual(len(selected), min(limit or 360, 360))
                self.assertEqual(len({r["id"] for r in selected}), len(selected))
                self.assertEqual({json.loads(r["instruction"])["task"] for r in selected}, {"mix", "form", "texture"})
        for limit in (-1, 1, 2):
            with self.assertRaises(ValueError):
                select_rows(self.rows(), limit)
        with self.assertRaises(ValueError):
            select_rows(self.rows()[:120])

    def test_all_existing_samples_pass_contract(self):
        count = 0
        for task in ("mix", "form", "texture"):
            for split in ("train", "val"):
                for line in (ROOT / "synthetic" / "data" / f"{task}_{split}.jsonl").read_text(encoding="utf-8").splitlines():
                    row = json.loads(line)
                    self.assertEqual(validate(task, row["state"], row["patch"]), (True, "ok"), row["id"])
                    count += 1
        self.assertEqual(count, 3600)

    def test_unknown_compressor_track_and_required_fields(self):
        self.assertTrue(validate("mix", self.state, {"ops": [self.comp]})[0])
        self.comp["track"] = "Ghost"
        self.assertFalse(validate("mix", self.state, {"ops": [self.comp]})[0])
        self.comp["track"] = "Vocal"
        for key in tuple(self.comp["params"]):
            op = deepcopy(self.comp)
            del op["params"][key]
            self.assertFalse(validate("mix", self.state, {"ops": [op]})[0])

    def test_comp_numeric_types_and_ranges(self):
        for value in ("3", True, None, {}, [], float("nan"), float("inf"), -1, 21):
            op = deepcopy(self.comp)
            op["params"]["ratio"] = value
            self.assertFalse(validate("mix", self.state, {"ops": [op]})[0], repr(value))

    def test_send_endpoints_ranges_and_cycles(self):
        self.assertTrue(validate("mix", self.state, {"ops": [self.send]})[0])
        for key, value in (("from", "Ghost"), ("to", "Ghost"), ("from", []), ("gain_db", 100), ("gain_db", True)):
            op = {**self.send, key: value}
            self.assertFalse(validate("mix", self.state, {"ops": [op]})[0])
        reverse = {**self.send, "from": "Reverb", "to": "Vocal"}
        self.assertFalse(validate("mix", self.state, {"ops": [self.send, reverse]})[0])
        state = deepcopy(self.state)
        state["tracks"][0]["sends"] = [{"to": "Reverb"}]
        self.assertFalse(validate("mix", state, {"ops": [reverse]})[0])
        self.assertFalse(validate("mix", self.state, {"ops": [{**self.send, "to": "Vocal"}]})[0])

    def test_track_and_eq_fields(self):
        for fields in ({}, {"volume_db": 12}, {"pan": 2}, {"pan": True}, {"bypass": True}):
            self.assertFalse(validate("mix", self.state, {"ops": [{"op": "set_track", "track": "Vocal", "fields": fields}]})[0])
        self.assertTrue(validate("mix", self.state, {"ops": [{"op": "set_track", "track": "Vocal", "fields": {"pan": -0.5}}]})[0])
        eq = {"op": "set_eq", "track": "Vocal", "band": 2, "type": "bell", "freq": 300, "gain_db": -3, "q": 1}
        self.assertTrue(validate("mix", self.state, {"ops": [eq]})[0])
        for key, value in (("band", 0), ("type", []), ("freq", 0), ("gain_db", 20), ("q", None)):
            self.assertFalse(validate("mix", self.state, {"ops": [{**eq, key: value}]})[0])

    def test_form_checks_values_and_marker_content(self):
        self.assertTrue(validate("form", {"tempo": 120}, self.form)[0])
        for path, value in (("markers", [{"bar": 4, "name": "Outro"}]), ("tempo", True), ("tempo", 0), ("sections", [None])):
            self.assertFalse(validate("form", {"tempo": 120}, {**self.form, path: value})[0])
        for key, value in (("energy", 2), ("density", "0.3"), ("start_bar", True), ("bars", 4.0), ("name", [])):
            broken = deepcopy(self.form)
            broken["sections"][0][key] = value
            self.assertFalse(validate("form", {}, broken)[0])

    def test_texture_range_velocity_duplicates_and_end(self):
        state = {"progression": ["C"], "range": ["C4", "C5"]}
        self.assertTrue(validate("texture", state, {"notes": [self.note]})[0])
        for key, value in (("key", 59), ("key", 60.0), ("vel", 0), ("vel", 128), ("step", True), ("bar", 3)):
            self.assertFalse(validate("texture", state, {"notes": [{**self.note, key: value}]})[0])
        self.assertFalse(validate("texture", state, {"notes": [self.note, self.note]})[0])
        self.assertFalse(validate("texture", state, {"notes": [{**self.note, "bar": 2, "step": 15, "len_steps": 2}]})[0])
        self.assertFalse(validate("texture", state, {"notes": [None]})[0])

    def test_arbitrary_json_does_not_crash(self):
        values = (None, [], True, 1, "bad", {}, {"ops": [None]}, {"notes": [1]}, {"sections": [True]})
        for task in ("mix", "form", "texture"):
            for value in values:
                self.assertFalse(validate(task, {}, value)[0])

    def test_extract_json(self):
        self.assertEqual(extract_json('```json\n{"ops": []}\n```'), {"ops": []})
        self.assertIsNone(extract_json("broken"))

    def test_mocked_evaluation_reports_all_tasks_and_failures(self):
        rows = []
        examples = [("mix", self.state, {"ops": [self.comp]}), ("form", {"tempo": 120}, self.form), ("texture", {}, {"notes": [self.note]})]
        for task, state, output in examples:
            rows.append({"system": "test", "instruction": json.dumps({"task": task, "state": state}), "output": json.dumps(output)})
        with tempfile.TemporaryDirectory() as tmp:
            val, out = Path(tmp) / "val.jsonl", Path(tmp) / "report.json"
            val.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            with mock_patch("sys.argv", ["eval", "--limit", "3", "--val", str(val), "--out", str(out)]), mock_patch("eval_dawcoder.chat", side_effect=[rows[0]["output"], OSError("offline"), '{"notes": [{"bar": 1}]}']):
                main()
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(report["coverage_complete"])
            self.assertEqual(report["per_task"]["form"]["reasons"], {"request-error": 1})
            self.assertEqual(report["per_task"]["texture"]["valid"], 0)
            self.assertEqual(report["per_task"]["mix"]["valid"], 1)


if __name__ == "__main__":
    unittest.main()
